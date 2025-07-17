from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from github import Auth, GithubIntegration
from github.GithubException import GithubException
from config import get_settings
import google.generativeai as genai
from github_access.utils.diff_checker import find_line_info
from github_access.utils.static_analyzer import perform_static_analysis, StaticAnalysisResult 
import logging
import json
import os
import subprocess
import re 
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential
from fastapi import HTTPException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini API
genai.configure(api_key=get_settings().GEMINI_API_KEY)

supported_languages_ext = {".py", ".go", ".js", ".java", ".ts"} 

try:
    auth = Auth.AppAuth(get_settings().GITHUB_APP_ID, get_settings().get_private_key())
    gi = GithubIntegration(auth=auth)
    installations = gi.get_installations()
    if not installations:
        logger.error("No installations found for GitHub App ID: %s", get_settings().GITHUB_APP_ID)
        raise Exception("No installations found for the GitHub App. Please ensure the app is installed on a repository.")
    
    installation = installations[0]
    g = installation.get_github_for_installation()
    logger.info("GitHub App authenticated successfully.")
except Exception as e:
    logger.error(f"GitHub authentication failed: {str(e)} at {datetime.now().strftime('%I:%M %p IST on %B %d, %Y')}", exc_info=True)
    raise

class ReviewComment(BaseModel): 
    path: str
    body: str
    line: str
    severity: str 
    rationale: Optional[str] = None 

class PullRequest(BaseModel):
    id: int
    number: int
    repository: Dict[str, Any]

    @classmethod
    def from_github_event(cls, event: Dict[str, Any]):
        """
        Creates a PullRequest instance from a GitHub webhook event payload.
        """
        payload = event.get("pull_request")
        if not payload:
            raise ValueError("Payload does not contain pull_request data.")
        return cls(
            id=payload["id"],
            number=payload["number"],
            repository=event.get("repository"),
        )

    def gemini_review_request(self, commit_ref: Optional[str] = None, project_wide: bool = False, static_analysis_enabled: bool = True):
        """
        Initiates a code review using Gemini for a pull request or specific files.
        Args:
            commit_ref (str, optional): If provided, review only files changed in this commit.
            project_wide (bool): If True, review all files in the project.
            static_analysis_enabled (bool): If True, perform static analysis with external tools.
        """
        repo = g.get_repo(self.repository["full_name"])
        pull_request = repo.get_pull(self.number)

        files_to_review = []
        if commit_ref:
            files_to_review = self.get_commit_files(repo, commit_ref)
            logger.info(f"Reviewing {len(files_to_review)} files from commit {commit_ref}")
        elif project_wide:
            files_to_review = self.get_project_files(repo)
            logger.info(f"Reviewing {len(files_to_review)} files project-wide.")
        else:
            files_to_review = pull_request.get_files()
            logger.info(f"Reviewing {len(files_to_review)} files from pull request #{self.number}")
        
        dependencies = self.parse_dependencies(repo)
        self.create_and_post_review(files_to_review, pull_request, dependencies, static_analysis_enabled)

    def create_and_post_review(self, files, pull_request, dependencies: Dict[str, Any], static_analysis_enabled: bool):
        """
        Generates review comments for given files and posts them to the pull request.
        """
        review_comments_for_pr = []
        for file_data in files:
            ext = os.path.splitext(file_data.filename)[1].lower()
            if ext not in supported_languages_ext: 
                logger.info(f"Skipping unsupported file: {file_data.filename}")
                continue
            
            try:
                file_content = file_data.decoded_content.decode('utf-8')
            except UnicodeDecodeError:
                logger.warning(f"Could not decode {file_data.filename} with utf-8, trying latin-1.")
                file_content = file_data.decoded_content.decode('latin-1', errors='ignore')
            static_result = StaticAnalysisResult(cyclomatic_complexity=0, cognitive_complexity=0, halstead_metrics={}, issues=[], ast_sexp="")
            if static_analysis_enabled:
                static_result = perform_static_analysis(file_content, ext)
            
            gemini_generated_comments = self.generate_review(
                file_data.patch, file_data.filename, dependencies, static_result
            )
            
            for review_comment in gemini_generated_comments:
                line_to_comment_on = review_comment.line
                
                line_info = find_line_info(file_data.patch, line_to_comment_on)
                
                if line_info and "line" in line_info:
                    review_comments_for_pr.append(
                        {
                            "path": file_data.filename,
                            "body": f"**Severity**: {review_comment.severity}\n**Rationale**: {review_comment.rationale or 'N/A'}\n\n{review_comment.body}",
                            "line": line_info["line"],
                            "start_line": line_info.get("start_line", line_info["line"]),
                            "start_side": line_info.get("start_side", "RIGHT"),
                            "side": line_info.get("side", "RIGHT")
                        }
                    )
                else:
                    logger.warning(f"Could not find line info for comment on line '{line_to_comment_on}' in file '{file_data.filename}'. Skipping comment.")

            if len(review_comments_for_pr) >= get_settings().REVIEW_LIMIT:
                logger.info(f"Reached review limit of {get_settings().REVIEW_LIMIT}. Stopping further comment generation.")
                break

        self.post_review_comments(pull_request, review_comments_for_pr)
        return review_comments_for_pr 

    def post_review_comments(self, pull_request, review_comments: List[Dict]):
        """
        Posts the generated review comments to the GitHub pull request.
        """
        if not review_comments:
            logger.info(f"No review comments to post for PR #{pull_request.number}.")
            return

        try:
            pull_request.create_review(
                body=f"Automated code review by Gemini at {datetime.now().strftime('%I:%M %p IST on %B %d, %Y')}",
                event="COMMENT", # Use 'COMMENT' to just add comments, 'APPROVE' or 'REQUEST_CHANGES' for final review state
                comments=review_comments,
            )
            logger.info(f"Successfully posted {len(review_comments)} review comments to PR #{pull_request.number}.")
        except Exception as e:
            logger.error(f"Error posting review comments to PR #{pull_request.number}: {str(e)}", exc_info=True)
            raise

    def generate_review(self, file_patch: str, filename: str, dependencies: Dict[str, Any], static_result: StaticAnalysisResult) -> List[ReviewComment]:
        """
        Generates code review comments using the Gemini API based on the patch, dependencies, and static analysis.
        """
        try:
            ext = os.path.splitext(filename)[1].lower()
            language = {'.py': 'Python', '.go': 'Go', '.js': 'JavaScript', '.java': 'Java', '.ts': 'TypeScript'}.get(ext, 'Unknown')

            prompt = f"""
                You are an intelligent code review assistant. Your goal is to provide actionable, constructive, and context-aware feedback on code changes.
                Analyze the provided code patch, considering the programming language, project dependencies, and static analysis results.

                **Programming Language**: {language}
                **File Name**: {filename}

                **Project Dependencies (if available)**:
                ```json
                {json.dumps(dependencies, indent=2)}
                ```

                **Code Patch (diff format)**:
                ```diff
                {file_patch}
                ```

                **Static Analysis Results**:
                - **AST (S-expression)**:
                  ```
                  {static_result.ast_sexp}
                  ```
                - **Cyclomatic Complexity**: {static_result.cyclomatic_complexity}
                - **Cognitive Complexity**: {static_result.cognitive_complexity}
                - **Halstead Metrics**: {json.dumps(static_result.halstead_metrics, indent=2)}
                - **Issues from Linters/Scanners**:
                ```json
                {json.dumps(static_result.issues, indent=2)}
                ```

                **Review Focus Areas**:
                1.  **Syntax & Style**: Adherence to language conventions, formatting, naming.
                2.  **Logic & Correctness**: Potential bugs, edge case handling, error handling, off-by-one errors.
                3.  **Architecture & Design**: Design pattern violations, SOLID principles, code duplication, modularity, maintainability.
                4.  **Performance**: Algorithm efficiency, potential bottlenecks, memory usage, async/await patterns.
                5.  **Security**: Common vulnerabilities (e.g., injection, XSS, insecure deserialization), insecure configurations.
                6.  **Readability & Maintainability**: Clarity, comments, complexity, documentation.
                7.  **Testability**: Suggestions for improving test coverage or structure.
                8.  **Type Safety**: For Python, Go, Java, JavaScript/TypeScript, validate type hints/annotations.
                9.  **Control Flow**: Analyze potential issues in the flow of execution, infinite loops, unreachable code.
                10. **Data Flow**: Identify potential issues with data propagation, uninitialized variables, data leaks.


                **Output Format**:
                Provide a JSON array of review comments. Each object in the array MUST have the following properties:
                -   `body`: (string) The detailed review comment, including code suggestions if applicable (use markdown code blocks for suggestions).
                -   `line`: (string) The exact line of code (from the `+` or context lines in the patch) that the comment applies to. This line MUST be present in the provided `file_patch`.
                -   `severity`: (string) The severity level of the issue. Choose one of: "Critical", "High", "Medium", "Low".
                -   `rationale`: (string) A concise explanation of *why* this change is suggested and its impact.

                **Constraints**:
                -   Ensure the `line` property refers to an *actual line* from the `file_patch` (either a `+` added line or a ` ` context line). Do NOT provide line numbers that are not in the diff.
                -   Keep comments concise but informative.
                -   Prioritize critical and high-severity issues.
                -   If no issues are found, return an empty array `[]`.
                -   Do not include any conversational text outside the JSON array.
                """

            response = genai.generate_content(
                model="gemini-1.5-flash", # Using flash for speed, can switch to pro if more complex reasoning needed
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
                generation_config={
                    "response_mime_type": "application/json",
                    "response_schema": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "body": {"type": "string"},
                                "line": {"type": "string"},
                                "severity": {"type": "string", "enum": ["Critical", "High", "Medium", "Low"]},
                                "rationale": {"type": "string"}
                            },
                            "required": ["body", "line", "severity", "rationale"]
                        }
                    }
                }
            )
            # Parse the JSON response and validate against ReviewComment model
            raw_comments = json.loads(response.candidates[0].content.parts[0].text)
            return [ReviewComment(**comment) for comment in raw_comments]
        except Exception as e:
            logger.error(f"Gemini API error for {filename}: {str(e)} at {datetime.now().strftime('%I:%M %p IST on %B %d, %Y')}", exc_info=True)
            # If Gemini fails, return an empty list of comments to avoid breaking the PR review
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def get_commit_files(self, repo, commit_ref: str) -> List[Any]:
        """
        Fetches files changed in a specific commit.
        """
        try:
            commit = repo.get_commit(commit_ref)
            return commit.files
        except Exception as e:
            logger.error(f"Error fetching commit files for {commit_ref}: {str(e)}", exc_info=True)
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def get_project_files(self, repo) -> List[Any]:
        """
        Fetches all files in the repository.
        Note: This can be very resource-intensive for large repositories.
        """
        files = []
        try:
            contents = repo.get_contents("")
            while contents:
                file_content = contents.pop(0)
                if file_content.type == "dir":
                    # Recursively get contents of directories
                    contents.extend(repo.get_contents(file_content.path))
                elif os.path.splitext(file_content.path)[1].lower() in supported_languages_ext: # Use the set for supported extensions
                    files.append(file_content)
            return files
        except Exception as e:
            logger.error(f"Error fetching project files: {str(e)}", exc_info=True)
            return []

    def parse_dependencies(self, repo) -> Dict[str, Any]:
        """
        Parses common dependency files (e.g., requirements.txt, package.json, go.mod, pom.xml)
        to provide context to the review engine.
        """
        dependencies = {
            "python": [],
            "go": [],
            "javascript": {},
            "java": []
        }
        
        # Python dependencies (requirements.txt)
        try:
            req_content = repo.get_contents("requirements.txt")
            req_text = req_content.decoded_content.decode()
            # Simple parsing for demonstration; a dedicated library like `requirements-parser` would be better
            dependencies["python"] = [{"name": line.strip(), "version": "unknown"} for line in req_text.splitlines() if line.strip() and not line.strip().startswith('#')]
        except GithubException as e:
            if e.status != 404: # Ignore 404 (file not found)
                logger.warning(f"Error parsing requirements.txt: {e}", exc_info=True)
        except Exception as e:
            logger.warning(f"Unexpected error parsing requirements.txt: {e}", exc_info=True)

        # Go dependencies (go.mod)
        try:
            go_mod_content = repo.get_contents("go.mod")
            go_mod_text = go_mod_content.decoded_content.decode()
            dependencies["go"] = [
                {"module": line.split()[0], "version": line.split()[1]}
                for line in go_mod_text.splitlines()
                if line.strip().startswith("require ") and len(line.split()) >= 2
            ]
        except GithubException as e:
            if e.status != 404:
                logger.warning(f"Error parsing go.mod: {e}", exc_info=True)
        except Exception as e:
            logger.warning(f"Unexpected error parsing go.mod: {e}", exc_info=True)

        # JavaScript dependencies (package.json)
        try:
            package_json = repo.get_contents("package.json")
            package_data = json.loads(package_json.decoded_content.decode())
            dependencies["javascript"] = package_data.get("dependencies", {})
            dependencies["javascript"].update(package_data.get("devDependencies", {})) # Include dev dependencies
        except GithubException as e:
            if e.status != 404:
                logger.warning(f"Error parsing package.json: {e}", exc_info=True)
        except Exception as e:
            logger.warning(f"Unexpected error parsing package.json: {e}", exc_info=True)

        try:
            pom_content = repo.get_contents("pom.xml")
            pom_text = pom_content.decoded_content.decode()
            root = ET.fromstring(pom_text)
            maven_ns = "{http://maven.apache.org/POM/4.0.0}"
            for dep in root.findall(f".//{maven_ns}dependency"):
                group_id = dep.findtext(f"{maven_ns}groupId")
                artifact_id = dep.findtext(f"{maven_ns}artifactId")
                version = dep.findtext(f"{maven_ns}version")
                dependencies["java"].append({
                    "groupId": group_id,
                    "artifactId": artifact_id,
                    "version": version
                })
        except GithubException as e:
            if e.status != 404:
                logger.warning(f"Error parsing pom.xml: {e}", exc_info=True)
        except Exception as e:
            logger.warning(f"Unexpected error parsing pom.xml: {e}", exc_info=True)

        return dependencies

    def commit_and_review_file(self, repo_full_name: str, filename: str, file_content: str, commit_message: str, branch: str = "main") -> List[Dict[str, Any]]:
        """
        Commits a file to a GitHub repository and generates review comments for it.
        This simulates a file upload and review process.
        Returns the review comments for the committed file.
        """
        try:
            repo = g.get_repo(repo_full_name)
            
            # Get the reference for the target branch
            ref = repo.get_git_ref(f"heads/{branch}")
            commit_sha = ref.object.sha

            # Create a new blob with the file content
            blob = repo.create_git_blob(file_content, "utf-8")
            
            # Get the base tree of the latest commit
            base_tree = repo.get_git_tree(commit_sha)
            
            # Create a new tree with the updated file
            # If the file exists, it will be updated; otherwise, it will be added.
            tree = repo.create_git_tree([
                {
                    "path": filename,
                    "mode": "100644", # Standard file mode
                    "type": "blob",
                    "sha": blob.sha
                }
            ], base_tree=base_tree) 

            # Create a new commit with the new tree
            commit = repo.create_git_commit(
                message=commit_message,
                tree=tree,
                parents=[repo.get_git_commit(commit_sha)] 
            )
            
            # Update the branch reference to point to the new commit
            ref.edit(commit.sha)
            logger.info(f"File '{filename}' committed to {repo_full_name}/{branch} with commit SHA: {commit.sha}")
            
            # --- Generate review comments for the committed file ---
            # Create a mock file object that mimics PyGithub's File object for review
            class MockFileForReview:
                def __init__(self, filename_param, content_param):
                    self.filename = filename_param
                    self.decoded_content = content_param.encode('utf-8')
                    lines = content_param.split('\n')
                    patch_lines = [f"--- a/{filename_param}", f"+++ b/{filename_param}", f"@@ -0,0 +1,{len(lines)} @@"]
                    patch_lines.extend([f"+{line}" for line in lines])
                    self.patch = '\n'.join(patch_lines)

            mock_file = MockFileForReview(filename, file_content)
            dependencies = self.parse_dependencies(repo)
            review_comments = self.create_and_post_review([mock_file], None, dependencies, static_analysis_enabled=True)
            return review_comments
        except GithubException as e:
            logger.error(f"GitHub API error during commit or review for {repo_full_name}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to commit file or generate review: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during commit or review for {repo_full_name}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


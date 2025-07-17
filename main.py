from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from config import CodeAnalysisRequest, GeminiReviewComment,CodeContextResult,CodeSubmission,get_settings,GeminiReviewResponse, GitHubDataRequest
from github_access.utils.static_analyzer import perform_static_analysis, StaticAnalysisResult, FunctionSignature, ClassHierarchy
import os
from github_access.utils.github_fetcher import get_repo_installation, fetch_file_content
from typing import Dict, Any, List, Optional
from tree_sitter import Parser
from tree_sitter_languages import get_language
import logging
from datetime import datetime
import json 
import google.generativeai as genai 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini API
genai.configure(api_key=get_settings().GEMINI_API_KEY)

try:
    PYTHON_LANGUAGE = get_language("python")
    GO_LANGUAGE = get_language("go")
    JAVASCRIPT_LANGUAGE = get_language("javascript")
    JAVA_LANGUAGE = get_language("java")
    
    supported_languages = {
        ".py": PYTHON_LANGUAGE,
        ".go": GO_LANGUAGE,
        ".js": JAVASCRIPT_LANGUAGE,
        ".java": JAVA_LANGUAGE,
    }
    logger.info("Tree-sitter languages loaded successfully in main.py.")
except Exception as e:
    logger.error(f"Failed to load Tree-sitter languages in main.py: {str(e)} at {datetime.now().strftime('%I:%M %p IST on %B %d, %Y')}. AST parsing might be limited.", exc_info=True)
    supported_languages = {} 

app = FastAPI(
    title="Code Analysis API",
    description="An API to analyze code snippets and AI-powered code reviews."
)


@app.post("/static-analyze-code", response_model=StaticAnalysisResult)
async def static_analyze_code(request: CodeAnalysisRequest) -> StaticAnalysisResult:
    """
    API endpoint to perform comprehensive static analysis on code content directly.
    Returns AST, complexity metrics (Cyclomatic, Cognitive, Halstead), issues
    from integrated linters/security scanners (pylint, ESLint, Bandit, Checkstyle, Reuse),
    and code structure context (function signatures, class hierarchies, module dependencies).

    Args:
        request (CodeAnalysisRequest): A Pydantic model containing:
            - filename (str): The name of the file (e.g., "my_script.py"). The extension is used to detect language.
            - code_content (str): The actual code as a string.

    Returns:
        StaticAnalysisResult: A Pydantic model containing detailed analysis results.
    
    Raises:
        HTTPException: If the file extension is unsupported or an error occurs during analysis.
    """
    current_time = datetime.now().strftime('%I:%M %p IST on %B %d, %Y')
    try:
        ext = os.path.splitext(request.filename)[1].lower()
        
        # Call the comprehensive static analysis function
        analysis_result = perform_static_analysis(request.code_content, ext)

        logger.info(f"Successfully performed comprehensive static analysis for {request.filename} at {current_time}")
        return analysis_result
    except HTTPException as e:
        logger.error(f"HTTP Error analyzing code: {e.detail} at {current_time}", exc_info=True)
        raise # Re-raise HTTPExceptions
    except Exception as e:
        logger.error(f"Unexpected error analyzing code: {str(e)} at {current_time}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error analyzing code: {str(e)}")

@app.post("/get-ast", response_model=Dict[str, str])
async def get_ast(request: CodeAnalysisRequest) -> Dict[str, str]:
    """
    API endpoint to extract and return only the Abstract Syntax Tree (AST)
    of the provided code content.

    Args:
        request (CodeAnalysisRequest): A Pydantic model containing:
            - filename (str): The name of the file (e.g., "my_script.py"). The extension is used to detect language.
            - code_content (str): The actual code as a string.

    Returns:
        Dict[str, str]: A dictionary containing the filename, detected language, and its AST in S-expression format.
    
    Raises:
        HTTPException: If the file extension is unsupported or an error occurs during AST parsing.
    """
    current_time = datetime.now().strftime('%I:%M %p IST on %B %d, %Y')
    try:
        ext = os.path.splitext(request.filename)[1].lower()
        if ext not in supported_languages:
            raise HTTPException(status_code=400, detail=f"Unsupported file extension: {ext}. Supported types: {', '.join(supported_languages.keys())}")

        analysis_result = perform_static_analysis(request.code_content, ext)

        logger.info(f"Successfully extracted AST for {request.filename} at {current_time}")
        return {
            "filename": request.filename,
            "language": {".py": "Python", ".go": "Go", ".js": "JavaScript", ".java": "Java"}.get(ext, "Unknown"),
            "ast": analysis_result.ast_sexp
        }
    except HTTPException as e:
        logger.error(f"HTTP Error getting AST: {e.detail} at {current_time}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting AST: {str(e)} at {current_time}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting AST: {str(e)}")

@app.post("/get-code-context", response_model=CodeContextResult)
async def get_code_context(request: CodeAnalysisRequest) -> CodeContextResult:
    """
    API endpoint to extract and return structural context information from the provided code.
    This includes function signatures, class hierarchies, and module dependencies.

    Args:
        request (CodeAnalysisRequest): A Pydantic model containing:
            - filename (str): The name of the file (e.g., "my_script.py"). The extension is used to detect language.
            - code_content (str): The actual code as a string.

    Returns:
        CodeContextResult: A Pydantic model containing the extracted code structure.
    
    Raises:
        HTTPException: If the file extension is unsupported or an error occurs during context extraction.
    """
    current_time = datetime.now().strftime('%I:%M %p IST on %B %d, %Y')
    try:
        ext = os.path.splitext(request.filename)[1].lower()
        if ext not in supported_languages:
            raise HTTPException(status_code=400, detail=f"Unsupported file extension: {ext}. Supported types: {', '.join(supported_languages.keys())}")

        analysis_result = perform_static_analysis(request.code_content, ext)

        logger.info(f"Successfully extracted code context for {request.filename} at {current_time}")
        return CodeContextResult(
            filename=request.filename,
            language={".py": "Python", ".go": "Go", ".js": "JavaScript", ".java": "Java"}.get(ext, "Unknown"),
            function_signatures=analysis_result.function_signatures,
            class_hierarchies=analysis_result.class_hierarchies,
            module_dependencies=analysis_result.module_dependencies
        )
    except HTTPException as e:
        logger.error(f"HTTP Error getting code context: {e.detail} at {current_time}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting code context: {str(e)} at {current_time}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting code context: {str(e)}")

@app.post("/get-code-context", response_model=CodeContextResult)
async def get_code_context(request: CodeAnalysisRequest) -> CodeContextResult:
    """
    API endpoint to extract and return structural context information from the provided code.
    This includes function signatures, class hierarchies, and module dependencies.

    Args:
        request (CodeAnalysisRequest): A Pydantic model containing:
            - filename (str): The name of the file (e.g., "my_script.py"). The extension is used to detect language.
            - code_content (str): The actual code as a string.

    Returns:
        CodeContextResult: A Pydantic model containing the extracted code structure.
    
    Raises:
        HTTPException: If the file extension is unsupported or an error occurs during context extraction.
    """
    current_time = datetime.now().strftime('%I:%M %p IST on %B %d, %Y')
    try:
        ext = os.path.splitext(request.filename)[1].lower()
        if ext not in supported_languages:
            raise HTTPException(status_code=400, detail=f"Unsupported file extension: {ext}. Supported types: {', '.join(supported_languages.keys())}")

        analysis_result = perform_static_analysis(request.code_content, ext)

        logger.info(f"Successfully extracted code context for {request.filename} at {current_time}")
        return CodeContextResult(
            filename=request.filename,
            language={".py": "Python", ".go": "Go", ".js": "JavaScript", ".java": "Java"}.get(ext, "Unknown"),
            function_signatures=analysis_result.function_signatures,
            class_hierarchies=analysis_result.class_hierarchies,
            module_dependencies=analysis_result.module_dependencies
        )
    except HTTPException as e:
        logger.error(f"HTTP Error getting code context: {e.detail} at {current_time}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting code context: {str(e)} at {current_time}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting code context: {str(e)}")


@app.post("/gemini-code-review", response_model=GeminiReviewResponse) # Changed response_model
async def gemini_code_review(request: CodeAnalysisRequest) -> GeminiReviewResponse:
    """
    API endpoint to perform a multi-level code review using Google Gemini.
    This includes analysis at the syntax, logic, and architecture levels,
    providing actionable feedback, including a PR-level summary.

    Args:
        request (CodeAnalysisRequest): A Pydantic model containing:
            - filename (str): The name of the file (e.g., "my_script.py"). The extension is used to detect language.
            - code_content (str): The actual code as a string.

    Returns:
        GeminiReviewResponse: A Pydantic model containing a PR-level summary and a list of AI-generated review comments.
    
    Raises:
        HTTPException: If the file extension is unsupported or an error occurs during review.
    """
    current_time = datetime.now().strftime('%I:%M %p IST on %B %d, %Y')
    try:
        ext = os.path.splitext(request.filename)[1].lower()
        language = {'.py': 'Python', '.go': 'Go', '.js': 'JavaScript', '.java': 'Java', '.ts': 'TypeScript'}.get(ext, 'Unknown')

        if ext not in supported_languages:
            raise HTTPException(status_code=400, detail=f"Unsupported file extension for Gemini review: {ext}. Supported types: {', '.join(supported_languages.keys())}")

        static_analysis_result = perform_static_analysis(request.code_content, ext)

        patch_lines = [f"--- /dev/null", f"+++ b/{request.filename}", f"@@ -0,0 +1,{len(request.code_content.splitlines())} @@"]
        patch_lines.extend([f"+{line}" for line in request.code_content.splitlines()])
        file_patch = '\n'.join(patch_lines)

        prompt = f"""
            You are an intelligent code review assistant. Your goal is to provide actionable, constructive, and context-aware feedback on code changes.
            Analyze the provided code, considering the programming language, and the detailed static analysis results.

            **Programming Language**: {language}
            **File Name**: {request.filename}

            **Code Content**:
            ```{language.lower()}
            {request.code_content}
            ```

            **Code Patch (diff format - showing all lines as new for context)**:
            ```diff
            {file_patch}
            ```

            **Detailed Static Analysis Results**:
            - **AST (S-expression)**:
              ```
              {static_analysis_result.ast_sexp}
              ```
            - **Cyclomatic Complexity**: {static_analysis_result.cyclomatic_complexity}
            - **Cognitive Complexity**: {static_analysis_result.cognitive_complexity}
            - **Halstead Metrics**: {json.dumps(static_analysis_result.halstead_metrics, indent=2)}
            - **Issues from Linters/Scanners**:
            ```json
            {json.dumps(static_analysis_result.issues, indent=2)}
            ```
            - **Function Signatures**:
            ```json
            {json.dumps([fs.dict() for fs in static_analysis_result.function_signatures], indent=2)}
            ```
            - **Class Hierarchies**:
            ```json
            {json.dumps([ch.dict() for ch in static_analysis_result.class_hierarchies], indent=2)}
            ```
            - **Module Dependencies**:
            ```json
            {json.dumps(static_analysis_result.module_dependencies, indent=2)}
            ```

            **Review Focus Areas (Multi-level Analysis)**:
            1.  **Syntax Level**:
                * Style violations (e.g., inconsistent indentation, trailing whitespace).
                * Naming conventions (e.g., snake_case for functions, PascalCase for classes).
                * Formatting issues (e.g., line length, spacing around operators).
            2.  **Logic Level**:
                * Edge case handling (e.g., null/empty inputs, division by zero).
                * Error handling gaps (e.g., missing try-except, inadequate error messages).
                * Potential bugs or unexpected behavior.
            3.  **Architecture Level**:
                * Design pattern violations or opportunities.
                * Adherence to SOLID principles (Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion).
                * Identification of code duplication and suggestions for refactoring.
                * Modularity and separation of concerns.
                * Maintainability and extensibility.
            4.  **Performance Optimization**:
                * Algorithm efficiency (e.g., time and space complexity).
                * Database query optimization (e.g., N+1 queries, missing indexes, inefficient joins).
                * Memory leak detection (e.g., unreleased resources, circular references).
                * Async/await patterns (e.g., proper use of non-blocking I/O, avoiding blocking calls in async functions).
            5.  **Security**: Common vulnerabilities (e.g., SQL injection, XSS, insecure deserialization, weak cryptography).
            6.  **Readability**: Clarity, comments, complexity.
            7.  **Testability**: Suggestions for improving test coverage or structure.
            8.  **Type Safety**: Validate type hints/annotations.
            9.  **Control Flow**: Analyze potential issues in the flow of execution, infinite loops, unreachable code.
            10. **Data Flow**: Identify potential issues with data propagation, uninitialized variables, data leaks.

            **Output Format**:
            Provide a JSON object with three top-level keys: `pr_summary`, `comments`, and `prioritization_algorithm`.

            -   `pr_summary`: (string) A concise, overall summary of the code review for the entire file/pull request. Highlight key strengths, major findings across syntax, logic, architecture, and performance, and overall maintainability/quality.
            -   `comments`: (array of objects) A JSON array of individual review comments. Each object in this array MUST have the following properties:
                -   `issue_description`: (string) A concise, one-sentence description of the issue.
                -   `body`: (string) The detailed review comment. Begin the comment with the analysis level (e.g., "Syntax: ...", "Logic: ...", "Architecture: ...", "Performance: ...") to explicitly categorize it. Include code suggestions if applicable (use markdown code blocks for suggestions).
                -   `line`: (string) The exact line of code (from the `code_content` provided) that the comment applies to. This line MUST be present in the provided `code_content`. If the comment is a file-level observation (not tied to a specific line), set `line` to "File-level".
                -   `severity`: (string) The severity level of the issue. Choose one of: "Critical", "High", "Medium", "Low".
                -   `rationale`: (string) A concise explanation of *why* this change is suggested and its impact.
                -   `suggested_code_diff`: (string, optional) A code suggestion in unified diff format (e.g., `--- a/file.py\n+++ b/file.py\n@@ -L1,C1 +L2,C2 @@\n-old code\n+new code`). Only include if a specific code change is recommended.
            -   `prioritization_algorithm`: (string) Describe the algorithm or criteria used to prioritize the generated comments (e.g., "Comments are prioritized by severity (Critical > High > Medium > Low), then by impact on functionality or security.").

            **Constraints**:
            -   Ensure the `line` property refers to an *actual line* from the `code_content` or is "File-level".
            -   Keep comments concise but informative.
            -   Prioritize critical and high-severity issues.
            -   If no significant issues are found, the `comments` array can be empty `[]`, but the `pr_summary` and `prioritization_algorithm` should still provide an overall assessment.
            -   Do not include any conversational text outside the JSON object.
            """

        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await model.generate_content_async(
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "object",
                    "properties": {
                        "pr_summary": {"type": "string"},
                        "comments": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "issue_description": {"type": "string"},
                                    "body": {"type": "string"},
                                    "line": {"type": "string"},
                                    "severity": {"type": "string", "enum": ["Critical", "High", "Medium", "Low"]},
                                    "rationale": {"type": "string"},
                                    "suggested_code_diff": {"type": "string", "nullable": True}
                                },
                                "required": ["issue_description", "body", "line", "severity", "rationale"]
                            }
                        },
                        "prioritization_algorithm": {"type": "string", "nullable": True} 
                    },
                    "required": ["pr_summary", "comments", "prioritization_algorithm"] 
                }
            }
        )
        
        raw_response = json.loads(response.candidates[0].content.parts[0].text)
        
        parsed_comments = [GeminiReviewComment(**comment) for comment in raw_response.get("comments", [])]
        
        return GeminiReviewResponse(
            pr_summary=raw_response.get("pr_summary", "No summary provided."),
            comments=parsed_comments,
            prioritization_algorithm=raw_response.get("prioritization_algorithm")
        )
    except HTTPException as e:
        logger.error(f"HTTP Error during Gemini code review: {e.detail} at {current_time}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during Gemini code review: {str(e)} at {current_time}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error performing Gemini code review: {str(e)}")


@app.post("/submit-github-file", response_model=Dict[str, Any])
async def submit_github_file(request: CodeSubmission) -> Dict[str, Any]:
    """
    API endpoint to submit and commit a file to a specified GitHub repository and branch.

    Args:
        request (CodeSubmission): A Pydantic model containing:
            - repo_full_name (str): The full name of the repository (e.g., "owner/repo").
            - filename (str): The path to the file within the repository (e.g., "src/main.py").
            - file_content (str): The content of the file to commit.
            - commit_message (str): The commit message.
            - branch (str): The target branch (default: "main").

    Returns:
        Dict[str, Any]: A dictionary indicating success and any review comments generated.
    
    Raises:
        HTTPException: If the commit fails due to GitHub API errors or other issues.
    """
    current_time = datetime.now().strftime('%I:%M %p IST on %B %d, %Y')
    try:
        github_instance = get_repo_installation(request.repo_full_name)
        repo = github_instance.get_repo(request.repo_full_name)

        ref = repo.get_git_ref(f"heads/{request.branch}")
        
        commit_sha = ref.object.sha
        commit = repo.get_git_commit(commit_sha)
        
        blob = repo.create_git_blob(request.file_content, "utf-8")
        base_tree = repo.get_git_tree(commit.tree.sha)
        tree = repo.create_git_tree([
            {
                "path": request.filename,
                "mode": "100644", # File mode (blob)
                "type": "blob",
                "sha": blob.sha
            }
        ], base_tree=base_tree)
        
        new_commit = repo.create_git_commit(
            message=request.commit_message,
            tree=tree,
            parents=[commit]
        )
        
        ref.edit(new_commit.sha)

        logger.info(f"Successfully committed file {request.filename} to {request.repo_full_name}/{request.branch} at {current_time}")
        return {"status": "success", "message": f"File '{request.filename}' committed successfully to '{request.repo_full_name}/{request.branch}'.", "commit_sha": new_commit.sha}

    except HTTPException as e:
        logger.error(f"HTTP Error submitting file to GitHub: {e.detail} at {current_time}", exc_info=True)
        raise 
    except Exception as e:
        logger.error(f"Unexpected error submitting file to GitHub: {str(e)} at {current_time}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error submitting file to GitHub: {str(e)}")


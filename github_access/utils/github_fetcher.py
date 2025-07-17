from github import Auth, GithubIntegration
from github.GithubException import GithubException
from config import get_settings
from fastapi import HTTPException, status
import logging
import github 

logger = logging.getLogger(__name__)

logger.info(f"PyGithub version detected: {github.__version__ if hasattr(github, '__version__') else 'Version attribute not found'}")

def get_github_app_instance():
    """Returns a GitHubIntegration instance."""
    settings = get_settings()
    private_key = settings.get_private_key()
    return GithubIntegration(
        settings.GITHUB_APP_ID,
        private_key,
    )

def get_repo_installation(repo_full_name: str):
    """
    Gets the installation ID for a given repository and returns an authenticated GitHub instance.
    This version iterates through all installations to find the correct one,
    providing more robustness against potential PyGithub version inconsistencies.
    """
    integration = get_github_app_instance()
    try:
        found_installation = None
        logger.info(f"Searching for GitHub App installation for repository: {repo_full_name}")
        installations = list(integration.get_installations())
        if not installations:
            logger.warning("No GitHub App installations found for this app.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No GitHub App installations found for this app. Please ensure the app is installed on at least one account."
            )

        for inst in installations:
            logger.debug(f"Checking installation ID: {inst.id}, Target Type: {inst.target_type}")
            try:
                installed_repos = inst.get_repos() 
                for repo in installed_repos:
                    if repo.full_name == repo_full_name:
                        found_installation = inst
                        logger.info(f"Found matching installation ID: {inst.id} for repository {repo_full_name}")
                        break
                if found_installation:
                    break
            except GithubException as e:
                logger.warning(f"GitHub API error fetching repositories for installation {inst.id}: {e.status} - {e.data.get('message', str(e))}")
            except Exception as e:
                logger.warning(f"Unexpected error fetching repositories for installation {inst.id}: {type(e).__name__}: {str(e)}", exc_info=True)

        if found_installation is None:
            logger.error(f"GitHub App not installed on repository '{repo_full_name}' or no matching installation found after checking all installations.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"GitHub App not installed on repository '{repo_full_name}' or no matching installation found. Please ensure the app is installed and has access to this repository."
            )
        
        logger.info(f"Attempting to get GitHub instance for found installation ID: {found_installation.id}, Target Type: {found_installation.target_type}")
        try:
            return integration.get_github_for_installation(found_installation)
        except AssertionError as e: # 
            logger.critical(f"CRITICAL PyGithub Assertion Error when getting GitHub instance for installation {found_installation.id}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal server error: A critical PyGithub assertion failed during authentication for installation {found_installation.id}. This often indicates a corrupted PyGithub installation or an environment issue. Please try 'pip uninstall PyGithub && pip install PyGithub --upgrade' and restart your server."
            )
        except Exception as e:
            logger.error(f"Error getting GitHub instance for installation {found_installation.id}: {type(e).__name__}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal server error when getting GitHub instance for installation {found_installation.id}: {type(e).__name__}: {str(e)}"
            )

    except GithubException as e:
        logger.error(f"GitHub API error in get_repo_installation (top-level) for {repo_full_name}: {e.status} - {e.data}", exc_info=True)
        raise HTTPException(
            status_code=e.status,
            detail=f"Failed to get GitHub installation for repository {repo_full_name}. Error: {e.data.get('message', str(e))}"
        )
    except HTTPException: 
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_repo_installation (top-level general) for {repo_full_name}: {type(e).__name__}: {str(e)}", exc_info=True)
        error_message = f"Internal server error when getting GitHub installation: {type(e).__name__}: {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_message
        )

def fetch_file_content(repo_full_name: str, path: str, ref: str = "main") -> str:
    """
    Fetches the content of a file from a GitHub repository.

    Args:
        repo_full_name (str): The full name of the repository (e.g., "owner/repo").
        path (str): The path to the file within the repository (e.g., "src/main.py").
        ref (str): The branch, tag, or commit SHA to fetch from (default: "main").

    Returns:
        str: The decoded content of the file.

    Raises:
        HTTPException: If the file is not found, or other errors occur during fetching.
    """
    try:
        github_instance = get_repo_installation(repo_full_name)
        repo = github_instance.get_repo(repo_full_name)
        contents = repo.get_contents(path, ref=ref)

        if isinstance(contents, list):
            # If it's a directory or multiple files, raise an error
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Path '{path}' is a directory or contains multiple files, not a single file. Please provide a path to a specific file."
            )
        
        return contents.decoded_content.decode('utf-8')
    except GithubException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"File not found at '{path}' in '{repo_full_name}' on ref '{ref}'. Error: {e.data.get('message', 'Not Found')}")
        logger.error(f"GitHub API error fetching file content from {repo_full_name}/{path}@{ref}: {e.status} - {e.data}")
        raise HTTPException(status_code=e.status, detail=f"GitHub API error: {e.data.get('message', str(e))}")
    except HTTPException: # Re-raise HTTPExceptions raised by get_repo_installation or other checks
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching file content from {repo_full_name}/{path}@{ref}: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {str(e)}")


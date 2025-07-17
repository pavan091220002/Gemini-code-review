# config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os
from pydantic import BaseModel
from typing import Dict, Any,List,Optional
from github_access.utils.static_analyzer import FunctionSignature, ClassHierarchy 

class CodeAnalysisRequest(BaseModel):
    filename: str  
    code_content: str

class Settings(BaseSettings):
    GITHUB_APP_ID: str
    GITHUB_PRIVATE_KEY_PATH: str
    WEBHOOK_SECRET: str
    GEMINI_API_KEY: str
    REVIEW_LIMIT: int = 50

    model_config = SettingsConfigDict(env_file=".env")

    def get_private_key(self) -> str:
        """
        Reads the GitHub App private key from the specified path.
        """
        try:
            with open(self.GITHUB_PRIVATE_KEY_PATH, "r") as key_file:
                return key_file.read()
        except FileNotFoundError:
            raise Exception(f"Private key file not found: {self.GITHUB_PRIVATE_KEY_PATH}")
        except Exception as e:
            raise Exception(f"Error reading private key: {str(e)}")
        
class CodeSubmission(BaseModel):
    repo_full_name: str  # e.g., "owner/repo"
    filename: str       # e.g., "src/main.py"
    file_content: str   # The code content
    commit_message: str # Commit message for the new file
    branch: str = "main" # Target branch (default: main)

class CodeContextResult(BaseModel):
    filename: str
    language: str
    function_signatures: List[FunctionSignature] = []
    class_hierarchies: List[ClassHierarchy] = []
    module_dependencies: List[str] = []

class GeminiReviewComment(BaseModel):
    body: str
    line: str
    severity: str
    rationale: Optional[str] = None 

class GeminiReviewResponse(BaseModel):
    pr_summary: str
    comments: List[GeminiReviewComment]
    prioritization_algorithm: Optional[str] = None

class GitHubDataRequest(BaseModel):
    repo_full_name: str  # e.g., "owner/repo"
    path: str           # e.g., "src/main.py"
    ref: str = "main" 
    
@lru_cache
def get_settings() -> Settings:
    """
    Caches and returns the application settings.
    """
    return Settings()


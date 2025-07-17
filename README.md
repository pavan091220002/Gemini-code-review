Code Analysis API

A robust FastAPI-based application for automated code analysis and review, leveraging GitHub integration, static analysis tools, and Google's Gemini AI for comprehensive code reviews.

Overview

The Code Analysis API provides a suite of tools for analyzing and reviewing code, either through direct code submissions or by integrating with GitHub repositories via webhooks. It supports multiple programming languages (Python, Go, JavaScript, Java, TypeScript) and performs static analysis, AST extraction, and AI-powered code reviews using Google Gemini. The application is designed to enhance code quality by identifying issues in syntax, logic, architecture, performance, security, and more.

Key Features





Static Analysis: Uses tools like pylint, bandit, ESLint, Checkstyle, and reuse for language-specific linting and security scanning.



Abstract Syntax Tree (AST) Extraction: Leverages tree-sitter for parsing and analyzing code structure across supported languages.



Code Context Extraction: Identifies function signatures, class hierarchies, and module dependencies for better code understanding.



AI-Powered Code Review: Integrates Google Gemini for multi-level code reviews, providing actionable feedback on syntax, logic, architecture, performance, and security.



GitHub Integration: Supports GitHub App authentication and webhook processing for automated pull request reviews.



File Submission: Allows direct code submission and committing to GitHub repositories with automated reviews.



Comprehensive Metrics: Calculates Cyclomatic Complexity, Cognitive Complexity, and Halstead Metrics for code quality assessment.

Supported Languages





Python (.py)



Go (.go)



JavaScript (.js)



TypeScript (.ts)



Java (.java)

Requirements

The application dependencies are listed in requirements.txt. Key dependencies include:





fastapi==0.111.0



uvicorn==0.30.1



tree-sitter==0.21.3



google-generativeai==0.7.0



radon==6.0.0



pylint==3.2.2



Additional linters: bandit, ESLint, Checkstyle, reuse (must be installed separately for full functionality)

See requirements.txt for the complete list.

Installation





Clone the Repository:

git clone https://github.com/your-organization/code-analysis-api.git
cd code-analysis-api



Set Up a Virtual Environment (recommended):

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate



Install Dependencies:

pip install -r requirements.txt



Install Additional Tools (optional, for full static analysis):





Bandit (Python security): pip install bandit



ESLint (JavaScript/TypeScript): npm install -g eslint



Checkstyle (Java): Download checkstyle.jar and ensure google_checks.xml is accessible.



Reuse (License compliance): pip install reuse



Set Up Environment Variables:

Create a .env file in the project root with the following variables:

GITHUB_APP_ID=your-github-app-id
GITHUB_PRIVATE_KEY_PATH=/path/to/your/private-key.pem
WEBHOOK_SECRET=your-webhook-secret
GEMINI_API_KEY=your-gemini-api-key
REVIEW_LIMIT=50





GITHUB_APP_ID: Your GitHub App ID.



GITHUB_PRIVATE_KEY_PATH: Path to your GitHub App's private key file (.pem).



WEBHOOK_SECRET: Secret for GitHub webhook signature verification.



GEMINI_API_KEY: API key for Google Gemini.



REVIEW_LIMIT: Maximum number of review comments per pull request (default: 50).

Running the Application





Start the FastAPI Server:

Run the following command to start the server using uvicorn:

uvicorn main:app --host 0.0.0.0 --port 8000





The API will be available at http://localhost:8000.



Use --reload for development to enable auto-reload on code changes:

uvicorn main:app --host 0.0.0.0 --port 8000 --reload



Verify the Server is Running:

Access the /demo endpoint to confirm the server is operational:

curl http://localhost:8000/demo

Expected response:

{"message": "Code Analysis Pipeline is running at <current-time>"}



Access API Documentation:

Once the server is running, you can explore the interactive API documentation (Swagger UI) at:

http://localhost:8000/docs

This provides a user-friendly interface to test all API endpoints.

Usage

API Endpoints

The API provides the following endpoints:





POST /static-analyze-code: Performs comprehensive static analysis (AST, complexity metrics, linter issues, code context).





Request: CodeAnalysisRequest (filename, code_content)



Response: StaticAnalysisResult



POST /get-ast: Extracts the Abstract Syntax Tree (AST) in S-expression format.





Request: CodeAnalysisRequest



Response: Dictionary with filename, language, and AST



POST /get-code-context: Extracts structural context (function signatures, class hierarchies, module dependencies).





Request: CodeAnalysisRequest



Response: CodeContextResult



POST /gemini-code-review: Performs an AI-powered code review using Google Gemini.





Request: CodeAnalysisRequest



Response: GeminiReviewResponse (PR summary, comments, prioritization algorithm)



POST /submit-github-file: Commits a file to a GitHub repository and generates review comments.





Request: CodeSubmission (repo_full_name, filename, file_content, commit_message, branch)



Response: Dictionary with commit status and review comments



GET /demo: Test endpoint to verify the server is running.





Response: Current timestamp and confirmation message



POST /webhook: Handles GitHub webhook events for pull request reviews.





Processes pull_request (opened, synchronize) and ping events.

Example Request (Static Analysis)

curl -X POST http://localhost:8000/static-analyze-code \
  -H "Content-Type: application/json" \
  -d '{"filename": "example.py", "code_content": "def add(a, b):\n    return a + b"}'

Example Request (Gemini Code Review)

curl -X POST http://localhost:8000/gemini-code-review \
  -H "Content-Type: application/json" \
  -d '{"filename": "example.py", "code_content": "def add(a, b):\n    return a + b"}'

GitHub Webhook Setup





Create a GitHub App and obtain its ID and private key.



Configure the webhook in your GitHub repository:





Webhook URL: http://<your-server>:8000/webhook



Secret: Set to the value of WEBHOOK_SECRET in your .env file



Events: Enable Pull requests and Ping



Install the GitHub App on your repository.

The application will automatically review pull requests when they are opened or synchronized.

Project Structure

├── main.py                # FastAPI application entry point
├── config.py              # Configuration and Pydantic models
├── github_access/
│   ├── models/
│   │   ├── pull_request.py   # Pull request handling and Gemini review
│   ├── routers/
│   │   ├── webhook.py        # Webhook handling for GitHub events
│   ├── utils/
│   │   ├── diff_checker.py   # Diff parsing utilities
│   │   ├── github_fetcher.py # GitHub API interactions
│   │   ├── static_analyzer.py # Static analysis logic
├── requirements.txt        # Project dependencies
├── README.md              # This file
├── .env                   # Environment variables (not tracked)

Contributing

Contributions are welcome! Please follow these steps:





Fork the repository.



Create a feature branch (git checkout -b feature/your-feature).



Commit your changes (git commit -m "Add your feature").



Push to the branch (git push origin feature/your-feature).



Open a pull request.

License

This project is licensed under the MIT License. See the LICENSE file for details.

Contact

For issues or inquiries, please open a GitHub issue or contact the maintainers at [your-email@example.com].

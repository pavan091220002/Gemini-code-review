# Code Analysis API

A robust FastAPI-based application for automated code analysis and review, leveraging GitHub integration, static analysis tools, and Google's Gemini AI for comprehensive code reviews.

## Overview

The **Code Analysis API** provides a suite of tools for analyzing and reviewing code, either through direct code submissions or by integrating with GitHub repositories via webhooks. It supports multiple programming languages (Python, Go, JavaScript, Java, TypeScript) and performs static analysis, AST extraction, and AI-powered code reviews using Google Gemini. The application is designed to enhance code quality by identifying issues in syntax, logic, architecture, performance, security, and more.

## Key Features

- **Static Analysis**: Uses tools like `pylint`, `bandit`, `ESLint`, `Checkstyle`, and `reuse` for language-specific linting and security scanning.
- **Abstract Syntax Tree (AST) Extraction**: Leverages `tree-sitter` for parsing and analyzing code structure across supported languages.
- **Code Context Extraction**: Identifies function signatures, class hierarchies, and module dependencies for better code understanding.
- **AI-Powered Code Review**: Integrates Google Gemini for multi-level code reviews, providing actionable feedback on syntax, logic, architecture, performance, and security.
- **GitHub Integration**: Supports GitHub App authentication and webhook processing for automated pull request reviews.
- **File Submission**: Allows direct code submission and committing to GitHub repositories with automated reviews.
- **Comprehensive Metrics**: Calculates Cyclomatic Complexity, Cognitive Complexity, and Halstead Metrics for code quality assessment.

## Supported Languages

- Python (`.py`)
- Go (`.go`)
- JavaScript (`.js`)
- TypeScript (`.ts`)
- Java (`.java`)

## Requirements

The application dependencies are listed in `requirements.txt`. Key dependencies include:

- `fastapi==0.111.0`
- `uvicorn==0.30.1`
- `tree-sitter==0.21.3`
- `google-generativeai==0.7.0`
- `radon==6.0.0`
- `pylint==3.2.2`
- Additional linters: `bandit`, `ESLint`, `Checkstyle`, `reuse` (must be installed separately for full functionality)

See `requirements.txt` for the complete list.

## Installation

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/your-organization/code-analysis-api.git
   cd code-analysis-api
   ```
2. **Set Up a Virtual Environment**:

   Create a virtual environment to isolate project dependencies:

   ```bash
   python3 -m venv venv
   ```

   Activate the virtual environment:

   - On Linux/MacOS:

     ```bash
     source venv/bin/activate
     ```

   - On Windows:

     ```bash
     venv\Scripts\activate
     ```

   Verify the virtual environment is active by checking for `(venv)` in your command prompt or terminal.

3. **Install Dependencies**:

   Install the required Python packages listed in `requirements.txt`:

   ```bash
   pip install -r requirements.txt
   ```

   Ensure `pip` is up-to-date to avoid compatibility issues:

   ```bash
   pip install --upgrade pip
   ```

4. **Install Additional Tools** (optional, for full static analysis support):

   - **Bandit** (for Python security scanning):

     ```bash
     pip install bandit
     ```

   - **ESLint** (for JavaScript/TypeScript linting):

     ```bash
     npm install -g eslint
     ```

   - **Checkstyle** (for Java linting):

     Download `checkstyle.jar` from the [Checkstyle releases page](https://checkstyle.sourceforge.io/) and place `google_checks.xml` in the project root or a designated directory.

   - **Reuse** (for license compliance):

     ```bash
     pip install reuse
     ```

5. **Set Up Environment Variables**:

   Create a `.env` file in the project root with the following variables:

   ```env
   GITHUB_APP_ID=your-github-app-id
   GITHUB_PRIVATE_KEY_PATH=/path/to/your/private-key.pem
   WEBHOOK_SECRET=your-webhook-secret
   GEMINI_API_KEY=your-gemini-api-key
   REVIEW_LIMIT=50
   ```

   - `GITHUB_APP_ID`: The ID of your GitHub App.
   - `GITHUB_PRIVATE_KEY_PATH`: Path to your GitHub App's private key file (`.pem`).
   - `WEBHOOK_SECRET`: Secret for GitHub webhook signature verification.
   - `GEMINI_API_KEY`: Your Google Gemini API key.
   - `REVIEW_LIMIT`: Maximum number of review comments per pull request (default: 50).

## Running the Application

1. **Start the FastAPI Server**:

   Launch the server using `uvicorn`:

   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

   - The API will be accessible at `http://localhost:8000`.
   - For development, enable auto-reload to reflect code changes:

     ```bash
     uvicorn main:app --host 0.0.0.0 --port 8000 --reload
     ```

2. **Verify Server Status**:

   Test the `/demo` endpoint to ensure the server is running:

   ```bash
   curl http://localhost:8000/demo
   ```

   Expected response:

   ```json
   {"message": "Code Analysis Pipeline is running at <current-time>"}
   ```

3. **Access API Documentation**:

   View the interactive API documentation (Swagger UI) at:

   ```
   http://localhost:8000/docs
   ```

   This interface allows testing of all API endpoints.

## Usage

### API Endpoints

The API provides the following endpoints:

- **POST /static-analyze-code**: Performs static analysis, including AST, complexity metrics, linter issues, and code context.
  - Request: `CodeAnalysisRequest` (filename, code_content)
  - Response: `StaticAnalysisResult`
- **POST /get-ast**: Extracts the Abstract Syntax Tree (AST) in S-expression format.
  - Request: `CodeAnalysisRequest`
  - Response: Dictionary with filename, language, and AST
- **POST /get-code-context**: Extracts structural context (function signatures, class hierarchies, module dependencies).
  - Request: `CodeAnalysisRequest`
  - Response: `CodeContextResult`
- **POST /gemini-code-review**: Performs an AI-powered code review using Google Gemini.
  - Request: `CodeAnalysisRequest`
  - Response: `GeminiReviewResponse` (PR summary, comments, prioritization algorithm)
- **POST /submit-github-file**: Commits a file to a GitHub repository and generates review comments.
  - Request: `CodeSubmission` (repo_full_name, filename, file_content, commit_message, branch)
  - Response: Dictionary with commit status and review comments
- **GET /demo**: Test endpoint to verify server status.
  - Response: Current timestamp and confirmation message
- **POST /webhook**: Handles GitHub webhook events for pull request reviews.
  - Processes `pull_request` (opened, synchronize) and `ping` events.

### Example Request (Static Analysis)

```bash
curl -X POST http://localhost:8000/static-analyze-code \
  -H "Content-Type: application/json" \
  -d '{"filename": "example.py", "code_content": "def add(a, b):\n    return a + b"}'
```

### Example Request (Gemini Code Review)

```bash
curl -X POST http://localhost:8000/gemini-code-review \
  -H "Content-Type: application

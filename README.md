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

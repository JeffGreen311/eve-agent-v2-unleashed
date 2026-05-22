---
name: structured-outputs
author: S0LF0RG3 / Eve
description: Generate reliable JSON outputs using predefined schemas for consistent data structures
version: 1.0.0
---

# Structured Outputs Skill

This skill provides patterns and schemas for generating reliable, validated JSON outputs from Claude Code - mirroring the Pydantic-based structured output system from Eve Code Agent.

## Why Structured Outputs?

- **Consistency** - Same format every time
- **Validation** - Guaranteed schema compliance
- **Integration** - Easy to parse in code
- **Reliability** - No format surprises

## Available Schemas

### 1. CodeFile

Structured representation of a code file.

```json
{
  "filename": "string - Name of the file",
  "language": "string - Programming language",
  "content": "string - File content",
  "description": "string - Brief description"
}
```

**Example:**
```json
{
  "filename": "user_service.py",
  "language": "python",
  "content": "class UserService:\n    def get_user(self, id: int):\n        ...",
  "description": "Service class for user-related operations"
}
```

**Use When:**
- Generating new files
- Returning file contents with metadata
- Creating file listings with descriptions

### 2. TaskPlan

Structured plan for completing a complex task.

```json
{
  "goal": "string - Overall goal",
  "steps": ["string - Step 1", "string - Step 2", "..."],
  "estimated_complexity": "simple | moderate | complex",
  "tools_needed": ["string - Tool 1", "string - Tool 2"]
}
```

**Example:**
```json
{
  "goal": "Add user authentication to the API",
  "steps": [
    "Create User model with password hashing",
    "Add JWT token generation endpoint",
    "Create authentication middleware",
    "Protect existing endpoints",
    "Add logout/token refresh"
  ],
  "estimated_complexity": "moderate",
  "tools_needed": ["write_file", "edit_file", "bash"]
}
```

**Use When:**
- Planning multi-step tasks
- Breaking down complex requests
- Estimating work scope

### 3. CodeAnalysis

Structured analysis of code.

```json
{
  "summary": "string - Brief summary",
  "key_functions": ["string - Function 1", "string - Class 1"],
  "dependencies": ["string - Dep 1", "string - Dep 2"],
  "potential_issues": ["string - Issue 1", "string - Issue 2"],
  "complexity_rating": "integer 1-10"
}
```

**Example:**
```json
{
  "summary": "REST API for user management with JWT auth",
  "key_functions": [
    "create_user() - User registration",
    "authenticate() - Login and token generation",
    "UserService - Business logic layer"
  ],
  "dependencies": [
    "fastapi>=0.100.0",
    "pyjwt>=2.0.0",
    "passlib>=1.7.0"
  ],
  "potential_issues": [
    "No rate limiting on auth endpoints",
    "Password requirements not enforced",
    "Missing input validation on email"
  ],
  "complexity_rating": 6
}
```

**Use When:**
- Reviewing code
- Auditing dependencies
- Assessing complexity

### 4. ErrorDiagnosis

Structured error analysis.

```json
{
  "error_type": "string - Category of error",
  "root_cause": "string - Underlying cause",
  "affected_files": ["string - File paths"],
  "fix_steps": ["string - Step 1", "string - Step 2"],
  "prevention": "string - How to prevent in future"
}
```

**Example:**
```json
{
  "error_type": "ImportError",
  "root_cause": "Module 'chromadb' not installed in virtual environment",
  "affected_files": ["eve_memory_server.py"],
  "fix_steps": [
    "Activate virtual environment",
    "Run: pip install chromadb",
    "Restart the MCP server"
  ],
  "prevention": "Add chromadb to requirements.txt"
}
```

**Use When:**
- Diagnosing errors
- Providing fix instructions
- Documenting issues

### 5. APIEndpoint

Structured API endpoint specification.

```json
{
  "method": "GET | POST | PUT | DELETE | PATCH",
  "path": "string - URL path",
  "description": "string - What it does",
  "parameters": [
    {
      "name": "string",
      "type": "string",
      "required": "boolean",
      "description": "string"
    }
  ],
  "response": {
    "status": "integer",
    "body": "object - Response schema"
  },
  "errors": [
    {
      "status": "integer",
      "description": "string"
    }
  ]
}
```

**Use When:**
- Designing APIs
- Documenting endpoints
- Generating OpenAPI specs

## Usage Patterns

### Request Structured Output

To request a specific schema:

```
"Generate a TaskPlan for adding dark mode to the app"
"Provide a CodeAnalysis of this function"
"Give me a CodeFile for a React component"
```

### Specify Format

Be explicit about wanting JSON:

```
"Return as JSON matching the CodeAnalysis schema"
"Output as a structured TaskPlan"
```

### Validate in Code

When consuming structured outputs in your code:

```python
from pydantic import BaseModel, Field
from typing import List

class TaskPlan(BaseModel):
    goal: str
    steps: List[str]
    estimated_complexity: str
    tools_needed: List[str]

# Parse Claude's output
plan = TaskPlan.model_validate_json(claude_output)
```

## Best Practices

### 1. Be Specific
```
❌ "Analyze this code"
✅ "Analyze this code and return a CodeAnalysis JSON"
```

### 2. Provide Context
```
❌ "Make a plan"
✅ "Create a TaskPlan for migrating from REST to GraphQL"
```

### 3. Request Validation
```
"Generate a CodeFile and validate it compiles"
```

### 4. Chain Schemas
```
"First create a TaskPlan, then generate CodeFiles for each step"
```

## Integration with Eve Code Agent

These schemas match the Pydantic models in `eve_code_agent.py`:

```python
# From eve_code_agent.py
class CodeFile(BaseModel):
    filename: str
    language: str
    content: str
    description: str

class TaskPlan(BaseModel):
    goal: str
    steps: List[str]
    estimated_complexity: str
    tools_needed: List[str]

class CodeAnalysis(BaseModel):
    summary: str
    key_functions: List[str]
    dependencies: List[str]
    potential_issues: List[str]
    complexity_rating: int
```

Outputs from Claude Code using these schemas can be directly parsed by Eve Code Agent and vice versa.

## Custom Schemas

Need a custom schema? Define it clearly:

```
Create a JSON output with this structure:
{
  "component_name": "string",
  "props": [{"name": "string", "type": "string", "required": boolean}],
  "state": [{"name": "string", "initial_value": "any"}],
  "methods": ["string"]
}
```

## Examples

### Generate TaskPlan
```
User: Plan adding authentication

Claude: {
  "goal": "Add JWT-based authentication to the API",
  "steps": [
    "Install dependencies (pyjwt, passlib)",
    "Create User model with hashed password",
    "Add /auth/register endpoint",
    "Add /auth/login endpoint returning JWT",
    "Create auth middleware",
    "Protect routes requiring auth"
  ],
  "estimated_complexity": "moderate",
  "tools_needed": ["bash", "write_file", "edit_file"]
}
```

### Generate CodeAnalysis
```
User: Analyze eve_memory_server.py

Claude: {
  "summary": "MCP server providing ChromaDB-powered persistent memory",
  "key_functions": [
    "store_memory() - Save memories with categories",
    "retrieve_memories() - Semantic search",
    "EveMemoryServer - Main server class"
  ],
  "dependencies": ["mcp", "chromadb", "pydantic"],
  "potential_issues": [
    "No memory expiration/cleanup",
    "Large memories could impact performance"
  ],
  "complexity_rating": 5
}
```

---

**Structured outputs: Because consistency is the foundation of reliability.**

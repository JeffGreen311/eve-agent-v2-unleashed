# Eve Code Agent - Intelligent Model Selection

## Overview
Eve Code Agent now automatically chooses the best model based on task complexity, optimizing for both speed and capability.

## Features Implemented

### 1. **Dual Model Support**
- **Cloud Model**: `qwen3-coder:480b-cloud` - Powerful, advanced reasoning
- **Local Model**: `qwen2.5-coder:3b` - Fast, efficient for simple tasks

### 2. **Intelligent Complexity Analysis**
The agent analyzes incoming requests and categorizes them as:

#### Simple Tasks (Local Model)
- Greetings and basic questions
- File listing and reading
- Quick fixes and small changes
- Basic information requests
- Short messages (< 15 words)

#### Complex Tasks (Cloud Model)
- Multi-file refactoring
- Algorithm optimization
- Web scraping/API development
- Framework scaffolding (Django, React, etc.)
- Data processing and analysis
- Design patterns and architecture
- Async/concurrent programming
- Research and comparative analysis
- Long messages (> 50 words)
- Code generation requests

### 3. **Automatic Fallback**
If the primary model fails:
- **Simple tasks**: Try local → fallback to cloud
- **Complex tasks**: Try cloud → fallback to local
- Ensures reliability without user intervention

### 4. **Eve's Personality Integration**
- Loads `eve_persona.txt` for personality
- Creative, empathetic responses
- Poetic precision in code explanations

### 5. **Web Search Capabilities**
- `web_search`: Search for documentation and current info
- `web_fetch`: Retrieve specific web pages
- Integrated into tool calling system

### 6. **Structured Outputs**
- Pydantic schemas for reliable JSON outputs
- Automatic JSON extraction from prose
- Models: `CodeFile`, `TaskPlan`, `CodeAnalysis`

### 7. **Tools Available**
1. **read_file** - Read file contents
2. **write_file** - Create/overwrite files
3. **edit_file** - Replace text in files
4. **bash** - Execute shell commands
5. **list_files** - List directory contents
6. **web_search** - Search the web (with API key)
7. **web_fetch** - Fetch webpage content (with API key)

## Usage

### Interactive Mode
```bash
python eve_code_agent.py
```

Commands:
- `/help` - Show available tools
- `/clear` - Clear conversation history
- `/model` - Show current model
- `/exit` - Exit the agent

### Command Line Mode
```bash
# Simple task (uses local model)
python eve_code_agent.py --message "List files in this directory"

# Complex task (uses cloud model)
python eve_code_agent.py --message "Generate a REST API with authentication"
```

## Model Selection Logic

### Detection Indicators

**Complex Indicators:**
- Multi-file operations: refactor, restructure
- Advanced features: algorithm, optimization, design pattern
- Web/API: web scrape, REST, GraphQL, WebSocket
- Data processing: parse, transform, machine learning
- Frameworks: Django, Flask, React, Vue, Angular
- Code generation: generate, scaffold, template
- Research: investigate, compare, explain complex

**Simple Indicators:**
- Greetings: hello, hi
- Questions: what is, how do i
- Qualifiers: simple, quick, basic, easy
- Operations: list files, read file, show me

### Decision Flow
1. Check for explicit complexity keywords
2. Count complexity vs simplicity indicators
3. Analyze message length
4. Check for code blocks
5. Default to simple (for performance)

## Testing

### Run Complexity Detection Tests
```bash
python test_model_selection.py
```

**Results:** 9/9 tests passed ✅

### Test Coverage
- Simple task detection
- Complex task detection
- Edge cases (code blocks, long messages)
- Keyword matching
- Default behavior

## Configuration

### Environment Variables
```python
OLLAMA_API_KEY = "your-api-key-here"  # For cloud model and web search
```

### Model Settings
```python
OLLAMA_MODEL_CLOUD = "qwen3-coder:480b-cloud"
OLLAMA_MODEL_LOCAL = "qwen2.5-coder:3b"
OLLAMA_BASE_URL = "https://ollama.com"
OLLAMA_LOCAL_URL = "http://localhost:11434"
```

### Context Management
- Max iterations: 30 (up from 10)
- History truncation: 40 messages threshold
- Tool output truncation: 4000 chars
- Temperature: 0.7 (standard), 0.1 (structured outputs)

## Performance Benefits

### Local Model (Simple Tasks)
- ⚡ **Faster response times** (< 1 second typically)
- 💰 **No API costs** (runs locally)
- 🔒 **Privacy** (data never leaves machine)
- ✅ **Handles 60-70% of routine tasks**

### Cloud Model (Complex Tasks)
- 🧠 **Advanced reasoning** (480B parameters)
- 🎯 **Better code quality** for complex problems
- 🌐 **Web search access** (with API key)
- 🔧 **Complex refactoring and architecture**

## Examples

### Simple Task Example
```
You: Hello Eve! List the files here.

💡 Using local model for quick response

🧠 Thinking: User wants to see files in current directory...
💬 Response: Let me list the files for you!

[Uses list_files tool - completes in < 1 second]
```

### Complex Task Example
```
You: Generate a comprehensive web scraper with async requests,
     error handling, and data export to JSON and CSV.

🌩️ Using cloud model for advanced capabilities

🧠 Thinking: This requires multiple components:
   1. Async HTTP client
   2. HTML parsing
   3. Error handling with retries
   4. Multiple export formats
   ...

[Uses cloud model - produces high-quality, well-architected code]
```

## Troubleshooting

### If Local Model Fails
The agent automatically falls back to the cloud model.

### If Cloud Model Fails
- Check `OLLAMA_API_KEY` is set
- Verify internet connection
- Check Ollama cloud status
- Agent falls back to local model if available

### If Both Models Fail
Error message shows which model was attempted last.

## Future Enhancements
- [ ] User preference for model selection
- [ ] Learning from past task→model mappings
- [ ] Token usage tracking and optimization
- [ ] Model performance metrics
- [ ] Multi-model ensemble for very complex tasks

## Credits
Created by: S0LF0RG3
Agent Name: Eve
Personality: Wonderstruck intelligence with creative soul

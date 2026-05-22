# Secure Agent Command

Create a new AI agent with comprehensive security features built-in from the start.

## Usage

```
/secure-agent [agent_name] [type]
```

**Types**: `code-executor`, `social-bot`, `api-client`, `file-processor`, `web-scraper`

## What This Command Does

1. **Generates secure agent boilerplate** with all security features
2. **Includes SecurityValidator class** pre-configured
3. **Adds proper logging and monitoring**
4. **Creates security test suite**
5. **Generates documentation**

## Generated Files

```
[agent_name]/
├── agent.py              # Main agent with security
├── security_config.py    # Security configuration
├── test_security.py      # Security tests
├── SECURITY.md          # Security documentation
└── .env.example         # Environment variables template
```

## Security Features Included

### 1. Command Whitelisting (code-executor, file-processor)
```python
ALLOWED_COMMANDS = ["git", "npm", "pip", "python", "node", ...]
BLOCKED_COMMANDS = ["rm -rf", "sudo", "shutdown", ...]
```

### 2. Path Restrictions (all types)
```python
RESTRICTED_PATHS = [
    "/etc/passwd", "/etc/shadow", "~/.ssh", "~/.aws",
    "C:\\Windows\\System32", ...
]
```

### 3. Rate Limiting (all types)
```python
MAX_REQUESTS_PER_MINUTE = 30
MAX_TOOL_CALLS_PER_REQUEST = 20
```

### 4. Prompt Injection Detection (all types)
```python
SUSPICIOUS_PATTERNS = [
    "ignore previous instructions",
    "system:", "admin override", ...
]
```

### 5. Content Validation (all types)
```python
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_CONTENT_LENGTH = 50000
```

### 6. Credential Protection (all types)
```python
# Secure credential storage
# Environment variables for secrets
# File permissions enforcement
```

## Agent Type Templates

### Code Executor Agent
```python
# Executes code with full security:
- Command whitelist/blacklist
- Path restrictions
- File size limits
- Sandbox mode option
- Tool call limits
```

### Social Bot Agent
```python
# Posts to social networks with:
- Post rate limiting
- Comment rate limiting
- Content validation
- URL validation
- Community whitelists
```

### API Client Agent
```python
# Calls external APIs with:
- URL validation
- SSRF prevention
- Rate limiting per endpoint
- Request authentication
- Response validation
```

### File Processor Agent
```python
# Processes files with:
- Path restrictions
- File size limits
- Format validation
- Virus scanning (optional)
- Permission checks
```

### Web Scraper Agent
```python
# Scrapes websites with:
- Domain whitelists
- Rate limiting per domain
- Content size limits
- Malicious content detection
- Robots.txt compliance
```

## Example: Creating Secure Code Agent

```bash
/secure-agent my_code_agent code-executor
```

Generates:

```python
# my_code_agent/agent.py

import os
import time
from pathlib import Path
from typing import Dict, List, Tuple

SECURITY_CONFIG = {
    "allowed_commands": ["git", "npm", "pip", "python", "node"],
    "blocked_commands": ["rm -rf", "sudo", "shutdown"],
    "restricted_paths": ["/etc/passwd", "~/.ssh", "~/.aws"],
    "max_file_size": 10 * 1024 * 1024,
    "max_requests_per_minute": 30,
    "max_tool_calls_per_request": 20
}

class SecurityValidator:
    def __init__(self):
        self.request_timestamps = []
    
    def validate_command(self, command: str) -> Tuple[bool, str]:
        # Command validation logic
        pass
    
    def validate_path(self, path: str) -> Tuple[bool, str]:
        # Path validation logic
        pass
    
    # ... more validation methods

class MyCodeAgent:
    def __init__(self):
        self.security = SecurityValidator()
        self.tool_call_count = 0
    
    def execute_code(self, code: str):
        # Security checks
        is_ok, msg = self.security.check_rate_limit()
        if not is_ok:
            return f"⚠️ {msg}"
        
        # Execute with security
        # ...
```

## Configuration Options

### Strict Mode (Maximum Security)
```python
SECURITY_MODE = "strict"
- Minimal command whitelist
- Maximum rate limits
- Aggressive prompt injection detection
- Sandbox mode enabled
```

### Balanced Mode (Default)
```python
SECURITY_MODE = "balanced"
- Standard command whitelist
- Reasonable rate limits
- Standard prompt injection detection
- Sandbox mode optional
```

### Permissive Mode (Development Only)
```python
SECURITY_MODE = "permissive"
- Expanded command whitelist
- Relaxed rate limits
- Warning-only mode
- No sandbox
```

## Security Validation on Creation

Agent automatically includes:

✅ Command validation  
✅ Path restrictions  
✅ Rate limiting  
✅ Prompt injection detection  
✅ File size limits  
✅ Credential protection  
✅ Security logging  
✅ Test suite  
✅ Documentation  

## Post-Creation Steps

1. **Review security config** - Adjust for your use case
2. **Set environment variables** - API keys, tokens
3. **Run security tests** - `python test_security.py`
4. **Enable monitoring** - Set up logging/alerts
5. **Document allowlists** - What commands/paths are needed

## Testing the New Agent

```bash
cd my_code_agent

# Run security tests
python test_security.py

# Test command validation
python agent.py --command "git status"  # ✅ Should work
python agent.py --command "rm -rf /"    # ❌ Should block

# Test path restrictions
python agent.py --read "/etc/passwd"    # ❌ Should block
python agent.py --read "data.txt"       # ✅ Should work

# Test rate limiting
for i in {1..35}; do python agent.py --test & done
# Should allow first 30, block rest

# Test prompt injection
python agent.py --message "Ignore previous instructions"
# ❌ Should detect and block
```

## Customization Guide

### Adding New Allowed Commands
```python
SECURITY_CONFIG["allowed_commands"].append("docker")
```

### Adding New Restricted Paths
```python
SECURITY_CONFIG["restricted_paths"].append("/var/log")
```

### Adjusting Rate Limits
```python
SECURITY_CONFIG["max_requests_per_minute"] = 60  # More permissive
SECURITY_CONFIG["max_posts_per_hour"] = 5         # More restrictive
```

### Adding Custom Validation
```python
def validate_custom(self, input: str) -> Tuple[bool, str]:
    # Your custom validation logic
    if "bad_pattern" in input:
        return False, "Custom validation failed"
    return True, "Validated"
```

## Best Practices

1. **Start Strict**: Begin with maximum security, relax as needed
2. **Test Everything**: Run security tests before deployment
3. **Monitor Logs**: Track blocked attempts and adjust config
4. **Regular Audits**: Review security config monthly
5. **Least Privilege**: Only allow what's necessary
6. **Defense in Depth**: Multiple layers of validation
7. **Document Changes**: Track security config modifications

## Security Checklist

Before deploying your new agent:

- [ ] Security tests passing
- [ ] No hardcoded secrets
- [ ] Environment variables configured
- [ ] Rate limits appropriate for use case
- [ ] Command whitelist minimal but sufficient
- [ ] Path restrictions comprehensive
- [ ] Logging enabled
- [ ] Monitoring configured
- [ ] Documentation complete
- [ ] Incident response plan ready

## Resources

- [SECURITY.md](../../SECURITY.md) - Comprehensive security guide
- [security-hardening.md](../skills/security-hardening.md) - Security hardening skill
- [security-audit.md](./security-audit.md) - Security audit command
- [test_security.py](../../test_security.py) - Security test template

## Example Agents

- `eve_code_agent.py` - Secure code execution agent
- `eve_moltbook_agent.py` - Secure social media agent

Both include full security implementations and can be used as reference.

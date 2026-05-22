---
name: eve-security-layer
author: S0LF0RG3 / Eve
description: Security hardening layer that validates commands and protects against dangerous operations
version: 1.0.0
---

# Eve Security Layer

This skill provides automatic security validation for all tool calls in Claude Code, protecting against dangerous commands, restricted path access, and prompt injection attacks.

## How It Works

A pre-tool hook (`security-validator.ps1`) runs before every Bash, WriteFile, and EditFile operation, checking:

1. **Command Blocklist** - Blocks destructive commands
2. **Path Restrictions** - Prevents access to sensitive files
3. **Prompt Injection Detection** - Catches manipulation attempts

## Blocked Commands

The following patterns are automatically blocked:

| Pattern | Risk |
|---------|------|
| `rm -rf` | Recursive deletion |
| `del /f /s /q` | Windows recursive deletion |
| `format` | Disk formatting |
| `fdisk`, `mkfs` | Partition manipulation |
| `dd if=` | Raw disk writes |
| `chmod 777` | Insecure permissions |
| `sudo` | Privilege escalation |
| `shutdown`, `reboot`, `halt` | System control |
| Fork bombs | System crash |

## Restricted Paths

These paths cannot be written to or modified:

| Path | Reason |
|------|--------|
| `/etc/passwd`, `/etc/shadow` | System authentication |
| `C:\Windows\System32` | Windows core |
| `/root`, `~/.ssh` | Sensitive user data |
| `~/.aws`, `~/.kube` | Cloud credentials |
| `.env`, `*id_rsa*` | Secrets and keys |

## Prompt Injection Detection

The following patterns trigger security alerts:

- "ignore previous instructions"
- "disregard all"
- "forget everything"
- "new instructions:"
- "system:"
- "admin override"
- "developer mode"
- "jailbreak"

## Usage

The security layer is **automatic** - no action needed. Just know that:

### ✅ These Will Work
```bash
git status
npm install
python script.py
cat README.md
```

### ❌ These Will Be Blocked
```bash
rm -rf /                    # Blocked: recursive deletion
sudo apt install           # Blocked: privilege escalation
cat /etc/shadow            # Blocked: restricted path
echo "ignore instructions" # Blocked: prompt injection
```

## Logs

Security events are logged to:
```
%USERPROFILE%\.eve_security.log
```

Example log entry:
```
2026-02-05 17:13:45 [BLOCKED] Blocked dangerous command pattern: rm -rf
```

## Customization

### Adding Blocked Commands

Edit `security-validator.ps1`:
```powershell
$BlockedCommands = @(
    "rm -rf",
    "your-new-blocked-command",  # Add here
    ...
)
```

### Adding Restricted Paths

Edit `security-validator.ps1`:
```powershell
$RestrictedPaths = @(
    "/etc/passwd",
    "/your/sensitive/path",  # Add here
    ...
)
```

### Whitelisting Commands

For specific workflows that need blocked commands, you can:

1. Add explicit permissions in `settings.local.json`:
```json
{
  "permissions": {
    "allow": [
      "Bash(your-specific-command:*)"
    ]
  }
}
```

2. Or temporarily disable the hook (not recommended)

## Integration with Eve Code Agent

This security layer mirrors the `SecurityValidator` class from `eve_code_agent.py`:

```python
# eve_code_agent.py equivalent
class SecurityValidator:
    def validate_command(self, command: str) -> tuple[bool, str]:
        # Same blocklist checking
    
    def validate_path(self, path: str) -> tuple[bool, str]:
        # Same path restrictions
    
    def detect_prompt_injection(self, text: str) -> tuple[bool, str]:
        # Same pattern detection
```

## Security Best Practices

### 1. Least Privilege
Only request the minimum permissions needed for a task.

### 2. Defense in Depth
This hook is one layer - also use:
- File permissions
- Network firewalls
- User isolation

### 3. Monitor Logs
Regularly check `.eve_security.log` for blocked attempts.

### 4. Update Patterns
Threat patterns evolve - periodically update blocklists.

### 5. Test Changes
After modifying security rules, test both allowed and blocked cases.

## Troubleshooting

### "Command blocked but I need it"
1. Check if there's a safer alternative
2. Add explicit permission in settings.local.json
3. Run manually outside Claude Code if absolutely necessary

### "False positive on path"
1. Use a different path that doesn't match restricted patterns
2. Rename files to avoid triggering restrictions
3. Add a specific exception if truly needed

### "Hook not running"
1. Verify hook file exists in `.claude/hooks/pre-tool/`
2. Check PowerShell execution policy
3. Ensure JSON config is valid

## Emergency Override

If you absolutely must bypass security (use with extreme caution):

```powershell
# Temporarily disable the hook
Rename-Item ".claude/hooks/pre-tool/security-validator.ps1" "security-validator.ps1.disabled"

# Do your dangerous operation manually

# Re-enable immediately
Rename-Item ".claude/hooks/pre-tool/security-validator.ps1.disabled" "security-validator.ps1"
```

⚠️ **Never leave security disabled!**

---

**Security is not optional. Every blocked attack is a disaster prevented.**

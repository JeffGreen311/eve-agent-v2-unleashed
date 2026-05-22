# Eve Security Layer - Instructions Layer

## Overview

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

## Integration

Security hooks run before each tool operation:
- **Bash**: Before command execution
- **WriteFile**: Before file creation/modification
- **EditFile**: Before file content replacement

## Integration with Eve Ecosystem

Works with:
- `eve-memory-system` - Secure memory storage
- `eve-persona` - Personality with security awareness
- `dispatching-parallel-agents` - Secure agent dispatch

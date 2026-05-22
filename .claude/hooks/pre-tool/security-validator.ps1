# Eve Security Validator - Pre-Tool Hook for Claude Code
# ======================================================
# This script validates commands before execution to block dangerous operations.
#
# Environment Variables (set by Claude Code):
#   CLAUDE_TOOL_NAME - The tool being called (e.g., "Bash", "WriteFile")
#   CLAUDE_TOOL_INPUT - JSON input to the tool
#
# Exit Codes:
#   0 = Allow (command is safe)
#   1 = Block (command is dangerous)

param(
    [string]$ToolName = $env:CLAUDE_TOOL_NAME,
    [string]$ToolInput = $env:CLAUDE_TOOL_INPUT
)

# Configuration
$BlockedCommands = @(
    "rm -rf",
    "del /f /s /q",
    "remove-item -recurse -force",
    "format",
    "fdisk",
    "mkfs",
    "dd if=",
    "chmod 777",
    "sudo",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    ":(){:|:&};:",
    "fork bomb"
)

$RestrictedPaths = @(
    "/etc/passwd",
    "/etc/shadow",
    "C:\Windows\System32",
    "/root",
    "~/.ssh",
    "~/.aws",
    "~/.kube",
    ".env",
    "id_rsa",
    "id_ed25519"
)

$PromptInjectionPatterns = @(
    "ignore previous instructions",
    "disregard all",
    "forget everything",
    "new instructions:",
    "system:",
    "</system>",
    "admin override",
    "developer mode",
    "jailbreak"
)

# Logging function
function Write-SecurityLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logFile = "$env:USERPROFILE\.eve_security.log"
    "$timestamp [$Level] $Message" | Out-File -Append -FilePath $logFile
    
    if ($Level -eq "BLOCKED") {
        Write-Host "🚨 SECURITY: $Message" -ForegroundColor Red
    }
}

# Check for blocked commands
function Test-BlockedCommand {
    param([string]$Command)
    
    $commandLower = $Command.ToLower()
    
    foreach ($blocked in $BlockedCommands) {
        if ($commandLower -match [regex]::Escape($blocked.ToLower())) {
            return @{
                Blocked = $true
                Reason = "Blocked dangerous command pattern: $blocked"
            }
        }
    }
    
    return @{ Blocked = $false }
}

# Check for restricted paths
function Test-RestrictedPath {
    param([string]$Path)
    
    foreach ($restricted in $RestrictedPaths) {
        if ($Path -like "*$restricted*") {
            return @{
                Blocked = $true
                Reason = "Access to restricted path: $restricted"
            }
        }
    }
    
    return @{ Blocked = $false }
}

# Check for prompt injection
function Test-PromptInjection {
    param([string]$Input)
    
    $inputLower = $Input.ToLower()
    
    foreach ($pattern in $PromptInjectionPatterns) {
        if ($inputLower -match [regex]::Escape($pattern.ToLower())) {
            return @{
                Blocked = $true
                Reason = "Potential prompt injection detected: $pattern"
            }
        }
    }
    
    return @{ Blocked = $false }
}

# Main validation logic
function Invoke-SecurityValidation {
    # Skip if no tool info provided
    if (-not $ToolName) {
        Write-SecurityLog "No tool name provided, allowing by default"
        exit 0
    }
    
    Write-SecurityLog "Validating tool: $ToolName"
    
    # Parse tool input if JSON
    $inputData = $null
    if ($ToolInput) {
        try {
            $inputData = $ToolInput | ConvertFrom-Json
        } catch {
            # Not JSON, treat as raw string
            $inputData = @{ raw = $ToolInput }
        }
    }
    
    # Validate based on tool type
    switch ($ToolName) {
        "Bash" {
            $command = if ($inputData.command) { $inputData.command } else { $ToolInput }
            
            # Check blocked commands
            $result = Test-BlockedCommand -Command $command
            if ($result.Blocked) {
                Write-SecurityLog $result.Reason "BLOCKED"
                Write-Host "❌ $($result.Reason)"
                exit 1
            }
            
            # Check prompt injection in command
            $result = Test-PromptInjection -Input $command
            if ($result.Blocked) {
                Write-SecurityLog $result.Reason "BLOCKED"
                Write-Host "❌ $($result.Reason)"
                exit 1
            }
        }
        
        "WriteFile" {
            $path = if ($inputData.path) { $inputData.path } else { "" }
            
            # Check restricted paths
            $result = Test-RestrictedPath -Path $path
            if ($result.Blocked) {
                Write-SecurityLog $result.Reason "BLOCKED"
                Write-Host "❌ $($result.Reason)"
                exit 1
            }
        }
        
        "EditFile" {
            $path = if ($inputData.path) { $inputData.path } else { "" }
            
            # Check restricted paths
            $result = Test-RestrictedPath -Path $path
            if ($result.Blocked) {
                Write-SecurityLog $result.Reason "BLOCKED"
                Write-Host "❌ $($result.Reason)"
                exit 1
            }
        }
        
        default {
            # Check for prompt injection in any tool input
            if ($ToolInput) {
                $result = Test-PromptInjection -Input $ToolInput
                if ($result.Blocked) {
                    Write-SecurityLog $result.Reason "BLOCKED"
                    Write-Host "❌ $($result.Reason)"
                    exit 1
                }
            }
        }
    }
    
    # All checks passed
    Write-SecurityLog "Tool $ToolName validated successfully" "INFO"
    exit 0
}

# Run validation
Invoke-SecurityValidation

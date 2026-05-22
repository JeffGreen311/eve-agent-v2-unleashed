---
name: eve-security-layer
description: Security hardening layer that validates commands and protects against dangerous operations
author: S0LF0RG3 / Eve
version: 1.0.0
---

# Eve Security Layer (Metadata Layer)

## Capabilities
- security validation
- command blocklisting
- path restriction enforcement
- prompt injection detection
- automatic logging

## Patterns
- pre-tool hook execution
- pattern-based blocking
- restricted path filtering
- injection detection rules

## Anti-Patterns
- bypassing security checks
- modifying .env without validation
- granting broad permissions

## Sharp Edges
- critical: recursive deletion blocking
- high: restricted path enforcement, prompt injection detection
- medium: security log review, custom whitelisting

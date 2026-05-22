# Claude Code Hooks

This directory contains automation hooks for Claude Code.

## JavaScript Formatting Hook

The `post-tool/format-javascript-files` hook automatically formats JavaScript files using Prettier.

### How it works

1. When a JavaScript file (.js or .jsx) is created or modified, this hook will automatically format it
2. It uses Prettier with the configuration defined in `.prettierrc`
3. The hook can be triggered manually by running:
   ```bash
   node .claude/hooks/post-tool/format-javascript-files.js [file-path]
   ```

### Configuration

- Prettier settings are defined in `.prettierrc`
- Hook metadata is in `.claude/hooks/post-tool/format-javascript-files.json`

### Requirements

- Node.js must be installed
- Prettier must be installed globally (`npm install -g prettier`)
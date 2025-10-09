# mac_shortcuts_mcp

Minimal MCP server that exposes macOS Shortcuts execution to ChatGPT-compatible clients.

## Requirements
- macOS host with the [Shortcuts command line tool](https://support.apple.com/guide/shortcuts/welcome/mac) installed
- Python 3.12+ and [uv](https://docs.astral.sh/uv/) for dependency management

## Setup
```bash
uv sync
```

## Run
- STDIO: `uv run mac-shortcuts-mcp stdio`
- HTTP: `uv run mac-shortcuts-mcp http --host 0.0.0.0 --port 8000`
  - Pass `--certfile`/`--keyfile` for HTTPS
  - Provide `--allowed-host` / `--allowed-origin` to enable DNS-rebinding protection

## Tool payload
```json
{
  "shortcutName": "Save Video",
  "textInput": "https://youtube.com/watch?v=...",
  "timeoutSeconds": 30
}
```

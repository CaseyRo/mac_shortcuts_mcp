# mac_shortcuts_mcp

Minimal MCP server that exposes macOS Shortcuts execution to ChatGPT-compatible clients.

## Requirements
- macOS host with the [Shortcuts command line tool](https://support.apple.com/guide/shortcuts/welcome/mac) installed
- Python 3.12+ and [uv](https://docs.astral.sh/uv/) for dependency management
- [FastMCP](https://pypi.org/project/fastmcp/) (installed automatically via `uv`) for the streamlined MCP runner

## Setup
```bash
uv sync
```

## Run

### FastMCP CLI (recommended)
- STDIO: `uv run fastmcp run src/mac_shortcuts_mcp/server.py --transport stdio`
- Streamable HTTP/SSE (defaults to `0.0.0.0:8000`):
  ```bash
  uv run fastmcp run src/mac_shortcuts_mcp/server.py \
    --transport streamable-http \
    --host 0.0.0.0 \
    --port 8000
  ```
  - Pass `--transport http` to serve JSON responses instead of SSE

## Tool payload
```json
{
  "shortcutName": "Save Video",
  "textInput": "https://youtube.com/watch?v=...",
  "timeoutSeconds": 30
}
```

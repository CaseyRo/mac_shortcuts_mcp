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

### Secure HTTP hosting options

The FastMCP runner currently binds without TLS and leaves DNS-rebinding
protection disabled. For HTTPS termination or to enforce an
`allowed_hosts`/`allowed_origins` policy, invoke the Typer-based CLI
instead:

```bash
uv run python -m mac_shortcuts_mcp http \
  --host 0.0.0.0 \
  --port 8443 \
  --allowed-host example.com \
  --allowed-origin https://example.com \
  --certfile /path/to/fullchain.pem \
  --keyfile /path/to/privkey.pem
```

- Omit `--certfile/--keyfile` to serve HTTP only, or change `--host`
  to `127.0.0.1` when terminating TLS via a reverse proxy.
- Provide multiple `--allowed-host` / `--allowed-origin` flags as
  needed to re-enable FastMCP's DNS-rebinding protection.

## Tool payload
```json
{
  "shortcutName": "Save Video",
  "textInput": "https://youtube.com/watch?v=...",
  "timeoutSeconds": 30
}
```

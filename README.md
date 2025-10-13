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

### Updating after pulling changes

Run `uv sync` again whenever you `git pull` new commits. The command reads the
project's `pyproject.toml`/`uv.lock` and makes sure the virtual environment
matches exactly, installing new dependencies, updating existing ones, and
removing anything that is no longer required. No additional cleanup steps are
needed unless you intentionally want to clear your cached wheels (use `uv cache
prune`) or recreate the environment from scratch.

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

## Connecting from clients

Most MCP clients expect one of two transport styles. The FastMCP runner exposes
both, using the following connection details:

- **STDIO transport** – launch the server with the stdio command above and
  configure the client to execute the exact command. The client should read and
  write JSON-RPC frames over the spawned process' stdin/stdout streams.
- **HTTP / SSE transport** – start the server with the HTTP example and point
  the client at `http://$HOST:$PORT/mcp` (for JSON responses use the same path
  over HTTPS/HTTP). The SSE variant also uses the `/mcp` mount for the stream.

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

Providing `textInput` pipes the supplied text to the shortcut's standard input,
mirroring `echo "value" | shortcuts run "Shortcut Name"`.

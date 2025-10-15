# mac_shortcuts_mcp

## Overview
`mac_shortcuts_mcp` is a minimal MCP (Model Context Protocol) server that lets ChatGPT-compatible clients trigger native macOS Shortcuts. It wraps the `shortcuts` CLI behind a schema-aware MCP tool so assistants can execute named shortcuts, pass optional text input, and receive structured results.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running the Server](#running-the-server)
  - [Quick Start (STDIO)](#quick-start-stdio)
  - [Streamable HTTP / SSE](#streamable-http--sse)
- [Client Integration](#client-integration)
  - [STDIO Clients](#stdio-clients)
  - [HTTP / SSE Clients](#http--sse-clients)
  - [Tool Payload Example](#tool-payload-example)
- [Advanced Configuration](#advanced-configuration)

## Prerequisites
- A macOS host with the Shortcuts app and `shortcuts` command-line tool available in `PATH`.
- Python 3.12 or newer, plus [uv](https://docs.astral.sh/uv/) for dependency management.
- [FastMCP](https://pypi.org/project/fastmcp/) (installed automatically via `uv`) to provide the streamlined MCP runner.

## Installation

### Initial setup
```bash
uv sync
```

### Updating after pulling changes
Run `uv sync` again whenever you `git pull` new commits. The command reads the project's `pyproject.toml`/`uv.lock` and ensures the virtual environment matches exactly—installing new dependencies, updating existing ones, and removing anything no longer required. No additional cleanup is needed unless you intentionally want to clear cached wheels (`uv cache prune`) or recreate the environment from scratch.

## Running the Server

### Quick Start (STDIO)
```bash
uv run fastmcp run src/mac_shortcuts_mcp/server.py --transport stdio
```
This launches the MCP server using the recommended FastMCP CLI in STDIO mode. Configure your client to execute the exact command and communicate via JSON-RPC over stdin/stdout.

### Streamable HTTP / SSE
```bash
uv run fastmcp run src/mac_shortcuts_mcp/server.py \
  --transport streamable-http \
  --host 0.0.0.0 \
  --port 8000
```
- Use `--transport http` instead when you need JSON responses instead of SSE streams.
- Adjust `--host`/`--port` to match your network environment.

## Client Integration
Most MCP clients expect either a spawned STDIO process or an HTTP endpoint. The FastMCP runner exposes both using the commands above.

### STDIO Clients
1. Launch the server with the [Quick Start](#quick-start-stdio) command.
2. Configure the client to run the exact command and keep the process alive.
3. The client should send and receive JSON-RPC frames over stdin/stdout.

### HTTP / SSE Clients
1. Start the server with the [Streamable HTTP / SSE](#streamable-http--sse) command.
2. Point the client to `http://$HOST:$PORT/mcp` (use `https://` when terminating TLS elsewhere).
3. Choose SSE for streaming responses or JSON for discrete responses.

### Tool Payload Example
Provide the MCP client with a payload like the following when invoking the exposed tool:

```json
{
  "shortcutName": "Show Content",
  "textInput": "testing output",
  "timeoutSeconds": 30
}
```
- `shortcutName` selects the macOS Shortcut to execute.
- `textInput` (optional) pipes text to the shortcut's standard input, mirroring `` `echo "value" | shortcuts run "Shortcut Name"` ``.
- `timeoutSeconds` bounds execution time to prevent runaway processes.

![Screenshot of a successful run of a shortcut.](https://github.com/CaseyRo/mac_shortcuts_mcp/blob/fd3b0a480d87c82740672bf2a11e6df8ff224b11/img/SCR-20251015-odll.png)

## Advanced Configuration
The FastMCP runner binds without TLS and leaves DNS-rebinding protection disabled. For HTTPS termination or to enforce an `allowed_hosts` / `allowed_origins` policy, use the Typer-based CLI instead:

```bash
uv run python -m mac_shortcuts_mcp http \
  --host 0.0.0.0 \
  --port 8443 \
  --allowed-host example.com \
  --allowed-origin https://example.com \
  --certfile /path/to/fullchain.pem \
  --keyfile /path/to/privkey.pem
```

- Omit `--certfile`/`--keyfile` to serve HTTP only, or change `--host` to `127.0.0.1` when terminating TLS via a reverse proxy.
- Provide multiple `--allowed-host` / `--allowed-origin` flags as needed to re-enable FastMCP's DNS-rebinding protection.


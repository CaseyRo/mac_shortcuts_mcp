# Agent Notes
## Project Setup Plan
1. Initialize project structure and document architecture.
2. Implement MCP server scaffolding supporting both STDIO and HTTP stream modes.
3. Integrate Siri Shortcuts execution functionality with parameter input.
4. Provide thorough documentation and testing instructions.

## Working Agreements
- Record significant design decisions and open questions in this file.
- Update sections as the implementation evolves.

## 2025-02-14 Progress
- Bootstrapped a `uv`-managed Python project with a src layout and Typer CLI entrypoints.
- Implemented the MCP server with a single `run_shortcut` tool that shells out to the macOS `shortcuts` CLI.
- Added stdio and streamable HTTP runners (uvicorn-based) with optional TLS support.
- README now summarizes requirements plus quick-start commands.

## 2025-10-09 Notes
- Adopted the FastMCP CLI as the primary runner while keeping the Typer entry point for advanced HTTP configuration.
- Added a lightweight adapter (`fastmcp_server`) so the existing server works with `fastmcp run` without rewriting the protocol handlers.
- Documented the new workflow in the README and noted the FastMCP dependency to reduce future confusion about transport options.
- Exported the FastMCP adapter as `server` so `fastmcp run src/mac_shortcuts_mcp/server.py` works without specifying an entry point.

## 2025-10-11 Notes
- Updated the FastMCP integration for the latest `mcp` release: constructor no longer accepts `version=` and tool decorators use `structured_output` instead of `output_schema`.
- Tool responses now return a Pydantic model containing both the execution summary and structured fields so schema generation continues to work without manual JSON.

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

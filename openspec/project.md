# Project Context

## Purpose
Minimal MCP (Model Context Protocol) server that exposes macOS Shortcuts execution to ChatGPT-compatible clients. Enables AI assistants to trigger native macOS Shortcuts through a standardized protocol interface.

## Tech Stack
- **Python 3.12+** - Core runtime
- **uv** - Fast Python package and project manager
- **FastMCP** (≥2.12.0) - Streamlined MCP server framework
- **mcp** (≥1.16.0) - Model Context Protocol implementation
- **Typer** (≥0.19.2) - CLI framework for advanced HTTP configuration
- **Pydantic** - Data validation and structured output
- **anyio** (≥4.11.0) - Async I/O framework
- **uvicorn** - ASGI server (for TLS/advanced HTTP)
- **hatchling** - Build backend

## Project Conventions

### Code Style
- **Module structure**: `src/mac_shortcuts_mcp/` layout (PEP 420 namespace package)
- **Naming conventions**:
  - Functions: `snake_case` (e.g., `run_shortcut`, `create_fastmcp_app`)
  - Classes: `PascalCase` (e.g., `ShortcutExecutionResult`, `FastMCPServerAdapter`)
  - Constants: `UPPER_SNAKE_CASE` (e.g., `SERVER_NAME`, `RUN_SHORTCUT_TOOL_NAME`)
  - Private module variables: `_lowercase_with_prefix` (e.g., `_APP`, `_FASTMCP_SUPPORTS_VERSION`)
- **Type hints**: Use `from __future__ import annotations` and comprehensive type annotations throughout
- **Docstrings**: Google-style docstrings for public functions and classes
- **Imports**: Organized by standard library, third-party, local modules
- **Modern Python**: Use `dataclasses.dataclass(slots=True)`, `|` union types, pattern matching where appropriate

### Architecture Patterns
- **Modular separation**:
  - `shortcuts.py`: Pure macOS Shortcuts CLI integration (no MCP knowledge)
  - `server.py`: MCP protocol layer and FastMCP configuration
  - `cli.py`: Typer-based CLI entrypoints for advanced use cases
  - `__main__.py`: Python module execution support
- **Dual transport support**:
  - STDIO transport for spawned process clients
  - HTTP/SSE transport for web-based clients
- **Adapter pattern**: `FastMCPServerAdapter` bridges legacy/modern FastMCP CLI versions
- **Async-first**: All I/O operations use `async`/`await` patterns
- **Error handling**: Custom exceptions (e.g., `ShortcutExecutionError`) with clear messages
- **Structured output**: Pydantic models for tool responses to ensure schema generation
- **Configuration**: Factory pattern (`create_fastmcp_app`) for testable server instances
- **Singleton pattern**: Cached app instance via `get_app()` for consistent STDIO usage

### Testing Strategy
_(Not yet implemented; document approach here when tests are added)_
- Target: async unit tests for `shortcuts.py` execution logic
- Target: integration tests for MCP tool invocation
- Use `pytest` with `pytest-asyncio` for async test support
- Mock `subprocess` calls for deterministic shortcut execution tests

### Git Workflow
- **Main branch**: `main` (up to date with `origin/main`)
- **Commit style**: Descriptive commits with context
- **Change management**: OpenSpec-driven proposals for features/breaking changes
- **Direct fixes**: Bug fixes, typos, non-breaking updates committed directly

## Domain Context
### macOS Shortcuts
- **shortcuts CLI**: Native macOS command (`shortcuts run <name>`) executes Shortcuts
- **Text input**: Optional stdin piping via `--input` argument
- **Return codes**: 0 for success, non-zero for failures
- **Timeout handling**: Long-running shortcuts need explicit timeout management
- **Discovery**: Shortcuts are user-created; no programmatic enumeration from CLI

### MCP Protocol
- **Tools**: Exposed capabilities (currently: `run_shortcut`)
- **Transports**: STDIO (JSON-RPC over stdin/stdout) or HTTP/SSE (JSON responses or event streams)
- **Security**: DNS rebinding protection optional via `TransportSecuritySettings`
- **Structured output**: Tools return Pydantic models for schema introspection

## Important Constraints
- **macOS-only**: Requires macOS host with Shortcuts.app and CLI installed
- **PATH requirement**: `shortcuts` binary must be discoverable via `shutil.which()`
- **Process execution**: Relies on subprocess spawning; sandboxed environments may block
- **Timeout defaults**: No default timeout; long shortcuts run indefinitely unless specified
- **Version compatibility**: Adapts to `mcp` package API changes (e.g., `version=` parameter removal)
- **FastMCP CLI bridge**: Maintains backward compatibility with both old and new FastMCP CLI versions

## External Dependencies
### System Dependencies
- **macOS Shortcuts CLI**: Apple's native shortcuts command-line tool
  - Location: Typically `/usr/bin/shortcuts`
  - Reference: https://support.apple.com/guide/shortcuts/welcome/mac

### Python Package Dependencies
- **FastMCP**: Provides high-level MCP server abstractions and CLI runner
- **mcp**: Core Model Context Protocol implementation
- **Typer**: Powers advanced CLI with `--certfile`, `--allowed-host`, etc.
- **Pydantic**: Validates tool arguments and structures responses
- **anyio**: Cross-platform async I/O (used by FastMCP)

### Development Dependencies
- **uv**: Manages project dependencies and virtual environment
  - Lock file: `uv.lock` (commit this for reproducible builds)
  - Sync command: `uv sync` (run after `git pull` to update environment)

## Additional Notes
- **Entry points**: Two CLI modes
  1. `uv run fastmcp run src/mac_shortcuts_mcp/server.py` (recommended, simple)
  2. `uv run python -m mac_shortcuts_mcp http` (advanced TLS/security options)
- **Version introspection**: Uses `importlib.metadata.version()` with `__version__` fallback
- **Graceful degradation**: Detects FastMCP API versions via `inspect.signature()` checks

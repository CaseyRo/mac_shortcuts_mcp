"""MCP server definition for mac-shortcuts-mcp."""

from __future__ import annotations

import asyncio
import anyio
from collections.abc import Awaitable, Callable, Sequence
from importlib.metadata import version
from typing import Any

from mcp import types
from mcp.server import Server
from fastmcp.server.server import FastMCP as FastMCPBase

from mac_shortcuts_mcp import __version__
from mac_shortcuts_mcp.shortcuts import ShortcutExecutionError, run_shortcut

SERVER_NAME = "mac-shortcuts-mcp"
RUN_SHORTCUT_TOOL_NAME = "run_shortcut"
SERVER_INSTRUCTIONS = (
    "Execute Siri Shortcuts on macOS hosts using the `shortcuts` command line tool. "
    "Provide the shortcut display name and optional text input."
)


def _get_version() -> str:
    try:
        return version("mac-shortcuts-mcp")
    except Exception:
        return __version__


def create_server() -> Server[Any, Any]:
    """Create and configure the MCP server instance."""

    server = Server(
        name=SERVER_NAME,
        version=_get_version(),
        instructions=SERVER_INSTRUCTIONS,
        website_url="https://support.apple.com/guide/shortcuts/welcome/mac",
    )

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=RUN_SHORTCUT_TOOL_NAME,
                description=(
                    "Run a Siri Shortcut that exists on the host macOS machine using "
                    "the `shortcuts run` command."
                ),
                inputSchema={
                    "type": "object",
                    "required": ["shortcutName"],
                    "additionalProperties": False,
                    "properties": {
                        "shortcutName": {
                            "type": "string",
                            "description": "Display name of the shortcut to execute.",
                            "minLength": 1,
                        },
                        "textInput": {
                            "type": "string",
                            "description": (
                                "Optional text forwarded to the shortcut via the `--input` argument."
                            ),
                        },
                        "timeoutSeconds": {
                            "type": "number",
                            "description": (
                                "Maximum seconds to wait for the shortcut before aborting."
                            ),
                            "exclusiveMinimum": 0,
                        },
                    },
                },
                outputSchema={
                    "type": "object",
                    "required": ["command", "returnCode", "stdout", "stderr", "timedOut", "succeeded"],
                    "additionalProperties": False,
                    "properties": {
                        "command": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Command that was executed.",
                        },
                        "returnCode": {
                            "type": ["integer", "null"],
                            "description": "Process return code when available.",
                        },
                        "stdout": {
                            "type": "string",
                            "description": "Captured standard output from the shortcut.",
                        },
                        "stderr": {
                            "type": "string",
                            "description": "Captured standard error from the shortcut.",
                        },
                        "timedOut": {
                            "type": "boolean",
                            "description": "True if execution timed out.",
                        },
                        "succeeded": {
                            "type": "boolean",
                            "description": "True when the shortcut completed successfully.",
                        },
                    },
                },
            )
        ]

    @server.call_tool()
    async def call_tool(tool_name: str, arguments: dict[str, Any]) -> tuple[Sequence[types.TextContent], dict[str, Any]]:
        if tool_name != RUN_SHORTCUT_TOOL_NAME:
            raise ShortcutExecutionError(f"Unknown tool: {tool_name}")

        shortcut_name = arguments.get("shortcutName")
        if not isinstance(shortcut_name, str) or not shortcut_name.strip():
            raise ShortcutExecutionError("`shortcutName` must be a non-empty string.")

        text_input = arguments.get("textInput")
        if text_input is not None and not isinstance(text_input, str):
            raise ShortcutExecutionError("`textInput` must be a string when provided.")

        timeout_value = arguments.get("timeoutSeconds")
        timeout_seconds: float | None
        if timeout_value is None:
            timeout_seconds = None
        elif isinstance(timeout_value, (int, float)):
            timeout_seconds = float(timeout_value)
            if timeout_seconds <= 0:
                raise ShortcutExecutionError("`timeoutSeconds` must be greater than 0.")
        else:
            raise ShortcutExecutionError("`timeoutSeconds` must be a number when provided.")

        result = await run_shortcut(
            shortcut_name=shortcut_name,
            text_input=text_input,
            timeout=timeout_seconds,
        )

        summary_lines: list[str] = []
        if result.timed_out:
            summary_lines.append(
                f"Shortcut '{shortcut_name}' timed out after {timeout_seconds} seconds."
                if timeout_seconds is not None
                else f"Shortcut '{shortcut_name}' timed out."
            )
        elif result.succeeded:
            summary_lines.append(f"Shortcut '{shortcut_name}' completed successfully.")
        else:
            summary_lines.append(
                f"Shortcut '{shortcut_name}' exited with return code {result.return_code}."
            )

        stdout_text = result.stdout.strip()
        stderr_text = result.stderr.strip()
        if stdout_text:
            summary_lines.append("--- stdout ---\n" + stdout_text)
        if stderr_text:
            summary_lines.append("--- stderr ---\n" + stderr_text)

        structured = {
            "command": list(result.command),
            "returnCode": result.return_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timedOut": result.timed_out,
            "succeeded": result.succeeded,
        }

        content = [
            types.TextContent(
                type="text",
                text="\n\n".join(summary_lines) if summary_lines else "No output produced.",
            )
        ]

        return content, structured

    return server


async def serve_stdio() -> None:
    """Run the MCP server over stdio."""

    from mcp.server.stdio import stdio_server

    server = create_server()
    initialization = server.create_initialization_options()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, initialization)


async def serve_http(
    *,
    host: str,
    port: int,
    json_response: bool,
    stateless: bool,
    allowed_hosts: list[str],
    allowed_origins: list[str],
    ssl_certfile: str | None = None,
    ssl_keyfile: str | None = None,
) -> None:
    """Run the MCP server using the Streamable HTTP transport."""

    import uvicorn
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from mcp.server.transport_security import TransportSecuritySettings

    server = create_server()
    enable_dns_protection = bool(allowed_hosts or allowed_origins)

    security_settings = TransportSecuritySettings(
        enable_dns_rebinding_protection=enable_dns_protection,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )

    session_manager = StreamableHTTPSessionManager(
        server,
        json_response=json_response,
        stateless=stateless,
        security_settings=security_settings,
    )

    ReceiveCallable = Callable[[], Awaitable[dict[str, Any]]]
    SendCallable = Callable[[dict[str, Any]], Awaitable[None]]

    class _MCPHttpApp:
        def __init__(self) -> None:
            self._context = None

        async def __call__(
            self,
            scope: dict[str, Any],
            receive: ReceiveCallable,
            send: SendCallable,
        ) -> None:
            if scope["type"] == "lifespan":
                await self._handle_lifespan(receive, send)
            else:
                await session_manager.handle_request(scope, receive, send)

        async def _handle_lifespan(
            self,
            receive: ReceiveCallable,
            send: SendCallable,
        ) -> None:
            while True:
                message = await receive()
                message_type = message.get("type")
                if message_type == "lifespan.startup":
                    self._context = session_manager.run()
                    try:
                        await self._context.__aenter__()
                    except Exception as exc:  # pragma: no cover - defensive
                        await send(
                            {
                                "type": "lifespan.startup.failed",
                                "message": str(exc),
                            }
                        )
                        self._context = None
                        return
                    await send({"type": "lifespan.startup.complete"})
                elif message_type == "lifespan.shutdown":
                    if self._context is not None:
                        await self._context.__aexit__(None, None, None)
                        self._context = None
                    await send({"type": "lifespan.shutdown.complete"})
                    return

    app = _MCPHttpApp()

    uvicorn_config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        loop="asyncio",
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
    )
    server_runner = uvicorn.Server(uvicorn_config)
    await server_runner.serve()


class FastMCPServerAdapter(FastMCPBase[Any]):
    """Adapter to expose the legacy server via the FastMCP CLI."""

    def __init__(self) -> None:
        super().__init__(
            name=SERVER_NAME,
            instructions=SERVER_INSTRUCTIONS,
        )

    async def run_async(
        self,
        *,
        transport: str | None = None,
        host: str | None = None,
        port: int | None = None,
        path: str | None = None,  # Unused but accepted for API compatibility
        log_level: str | None = None,  # Unused but accepted for API compatibility
        show_banner: bool | None = None,  # Unused but accepted for API compatibility
        **_: Any,
    ) -> None:
        del path, log_level, show_banner

        normalized_transport = (transport or "stdio").lower()
        if normalized_transport == "stdio":
            await serve_stdio()
            return

        if normalized_transport in {"http", "streamable-http", "sse"}:
            json_response = normalized_transport == "http"
            await serve_http(
                host=host or "0.0.0.0",
                port=port or 8000,
                json_response=json_response,
                stateless=False,
                allowed_hosts=[],
                allowed_origins=[],
            )
            return

        raise ValueError(f"Unsupported transport: {transport}")

    def run(
        self,
        transport: str = "stdio",
        mount_path: str | None = None,
        **kwargs: Any,
    ) -> None:
        del mount_path
        anyio.run(self.run_async, transport=transport, **kwargs)


fastmcp_server = FastMCPServerAdapter()
server = fastmcp_server


"""MCP server definition for mac-shortcuts-mcp."""

from __future__ import annotations

from collections.abc import Iterable
from importlib.metadata import PackageNotFoundError, version as pkg_version
from typing import Any

import anyio
from fastmcp.server.server import FastMCP as FastMCPBase
from fastmcp.tools.tool import TextContent, ToolResult
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field

from . import __version__
from .shortcuts import (
    ShortcutExecutionError,
    ShortcutExecutionResult,
    run_shortcut,
)

SERVER_NAME = "mac-shortcuts-mcp"
RUN_SHORTCUT_TOOL_NAME = "run_shortcut"
SERVER_INSTRUCTIONS = (
    "Execute Siri Shortcuts on macOS hosts using the `shortcuts` command line tool. "
    "Provide the shortcut display name and optional text input."
)

RUN_SHORTCUT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "command",
        "returnCode",
        "stdout",
        "stderr",
        "timedOut",
        "succeeded",
    ],
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
}


class RunShortcutArguments(BaseModel):
    """Request payload for the ``run_shortcut`` tool."""

    shortcutName: str = Field(
        ...,
        min_length=1,
        description="Display name of the shortcut to execute.",
    )
    textInput: str | None = Field(
        default=None,
        description=(
            "Optional text forwarded to the shortcut via the `--input` argument."
        ),
    )
    timeoutSeconds: float | None = Field(
        default=None,
        gt=0,
        description="Maximum seconds to wait for the shortcut before aborting.",
    )


class RunShortcutStructuredResponse(BaseModel):
    """Structured response returned from the ``run_shortcut`` tool."""

    command: list[str]
    returnCode: int | None
    stdout: str
    stderr: str
    timedOut: bool
    succeeded: bool


_APP: FastMCP | None = None


def _get_version() -> str:
    """Return the installed package version, falling back to the local build."""

    try:
        return pkg_version("mac-shortcuts-mcp")
    except PackageNotFoundError:
        return __version__


def _build_summary(
    *,
    shortcut_name: str,
    execution: ShortcutExecutionResult,
    timeout_seconds: float | None,
) -> str:
    """Construct a human readable summary for tool output."""

    summary_lines: list[str] = []

    if execution.timed_out:
        if timeout_seconds is not None:
            summary_lines.append(
                f"Shortcut '{shortcut_name}' timed out after {timeout_seconds} seconds."
            )
        else:
            summary_lines.append(f"Shortcut '{shortcut_name}' timed out.")
    elif execution.succeeded:
        summary_lines.append(f"Shortcut '{shortcut_name}' completed successfully.")
    else:
        summary_lines.append(
            f"Shortcut '{shortcut_name}' exited with return code {execution.return_code}."
        )

    stdout_text = execution.stdout.strip()
    stderr_text = execution.stderr.strip()

    if stdout_text:
        summary_lines.append("--- stdout ---\n" + stdout_text)
    if stderr_text:
        summary_lines.append("--- stderr ---\n" + stderr_text)

    return "\n\n".join(summary_lines) if summary_lines else "No output produced."


def _validate_timeout(timeout_value: float | None) -> float | None:
    if timeout_value is None:
        return None
    if timeout_value <= 0:
        raise ShortcutExecutionError("`timeoutSeconds` must be greater than 0.")
    return timeout_value


def _register_run_shortcut_tool(app: FastMCP) -> None:
    """Attach the run_shortcut tool to the provided FastMCP app."""

    @app.tool(
        name=RUN_SHORTCUT_TOOL_NAME,
        description=(
            "Run a Siri Shortcut that exists on the host macOS machine using "
            "the `shortcuts run` command."
        ),
        output_schema=RUN_SHORTCUT_OUTPUT_SCHEMA,
    )
    async def _run_shortcut_tool(arguments: RunShortcutArguments) -> ToolResult:
        shortcut_name = arguments.shortcutName.strip()
        if not shortcut_name:
            raise ShortcutExecutionError("`shortcutName` must be a non-empty string.")

        timeout_seconds = _validate_timeout(arguments.timeoutSeconds)

        execution = await run_shortcut(
            shortcut_name=shortcut_name,
            text_input=arguments.textInput,
            timeout=timeout_seconds,
        )

        structured = RunShortcutStructuredResponse(
            command=list(execution.command),
            returnCode=execution.return_code,
            stdout=execution.stdout,
            stderr=execution.stderr,
            timedOut=execution.timed_out,
            succeeded=execution.succeeded,
        )

        summary = _build_summary(
            shortcut_name=shortcut_name,
            execution=execution,
            timeout_seconds=timeout_seconds,
        )

        return ToolResult(
            content=[
                TextContent(
                    type="text",
                    text=summary,
                )
            ],
            structured_content=structured.model_dump(),
        )


def create_fastmcp_app(
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    json_response: bool = False,
    stateless_http: bool = False,
    allowed_hosts: Iterable[str] | None = None,
    allowed_origins: Iterable[str] | None = None,
) -> FastMCP:
    """Create a configured FastMCP application for this server."""

    allow_hosts = list(allowed_hosts or [])
    allow_origins = list(allowed_origins or [])
    enable_dns_protection = bool(allow_hosts or allow_origins)

    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=enable_dns_protection,
        allowed_hosts=allow_hosts,
        allowed_origins=allow_origins,
    )

    app = FastMCP(
        name=SERVER_NAME,
        version=_get_version(),
        instructions=SERVER_INSTRUCTIONS,
        website_url="https://support.apple.com/guide/shortcuts/welcome/mac",
        host=host,
        port=port,
        json_response=json_response,
        stateless_http=stateless_http,
        transport_security=transport_security,
    )

    _register_run_shortcut_tool(app)
    return app


def get_app() -> FastMCP:
    """Return a cached FastMCP application instance."""

    global _APP
    if _APP is None:
        _APP = create_fastmcp_app()
    return _APP


async def serve_stdio() -> None:
    """Run the MCP server over stdio using FastMCP's runner."""

    app = get_app()
    await app.run_stdio_async()


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
    """Run the MCP server using FastMCP's HTTP/SSE runner."""

    app = create_fastmcp_app(
        host=host,
        port=port,
        json_response=json_response,
        stateless_http=stateless,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )

    if ssl_certfile or ssl_keyfile:
        import uvicorn

        http_app = app.streamable_http_app()
        config = uvicorn.Config(
            http_app,
            host=app.settings.host,
            port=app.settings.port,
            log_level=app.settings.log_level.lower(),
            ssl_certfile=ssl_certfile,
            ssl_keyfile=ssl_keyfile,
        )
        server = uvicorn.Server(config)
        await server.serve()
        return

    await app.run_streamable_http_async()


class FastMCPServerAdapter(FastMCPBase[Any]):
    """Adapter to expose the server via the FastMCP CLI."""

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
        path: str | None = None,
        log_level: str | None = None,
        show_banner: bool | None = None,
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

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
from importlib.metadata import PackageNotFoundError, version as pkg_version
from typing import Annotated, Any, Iterable

from mcp import types
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, ConfigDict, Field
from importlib.metadata import version
from typing import Any

from fastmcp import FastMCP
from fastmcp.tools.tool import TextContent, ToolResult
from pydantic import BaseModel, Field
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .shortcuts import run_shortcut

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


class RunShortcutResult(BaseModel):
    """Structured result payload returned from the run_shortcut tool."""

    model_config = ConfigDict(populate_by_name=True)

    command: list[str]
    returnCode: int | None
    stdout: str
    stderr: str
    timedOut: bool
    succeeded: bool
    summary: str = Field(default="No output produced.", exclude=True)


def _build_summary(
    *,
    shortcut_name: str,
    execution_result: RunShortcutResult,
    timeout_seconds: float | None,
) -> str:
    """Construct a human readable summary for tool output."""

    summary_lines: list[str] = []

    if execution_result.timedOut:
        if timeout_seconds is not None:
            summary_lines.append(
                f"Shortcut '{shortcut_name}' timed out after {timeout_seconds} seconds."
            )
        else:
            summary_lines.append(f"Shortcut '{shortcut_name}' timed out.")
    elif execution_result.succeeded:
        summary_lines.append(f"Shortcut '{shortcut_name}' completed successfully.")
    else:
        summary_lines.append(
            f"Shortcut '{shortcut_name}' exited with return code {execution_result.returnCode}."
        )

    stdout_text = execution_result.stdout.strip()
    stderr_text = execution_result.stderr.strip()

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

    server = Server(
        name=SERVER_NAME,
        version=_get_version(),
        instructions=SERVER_INSTRUCTIONS,
        website_url="https://support.apple.com/guide/shortcuts/welcome/mac",
    instructions = (
        "Execute Siri Shortcuts on macOS hosts using the `shortcuts` command line tool. "
        "Provide the shortcut display name and optional text input."
    )
def get_app() -> FastMCP:
    """Return a configured FastMCP application instance."""

    global _APP
    if _APP is not None:
        return _APP

    instructions = (
        "Execute Siri Shortcuts on macOS hosts using the `shortcuts` command line tool. "
        "Provide the shortcut display name and optional text input."
    )

    app = FastMCP(
        name=SERVER_NAME,
        version=_get_version(),
        instructions=instructions,
    )
    app._mcp_server.website_url = (
        "https://support.apple.com/guide/shortcuts/welcome/mac"
    )

    @app.tool(
        name=RUN_SHORTCUT_TOOL_NAME,
        description=(
            "Run a Siri Shortcut that exists on the host macOS machine using "
            "the `shortcuts run` command."
        ),
        output_schema=RUN_SHORTCUT_OUTPUT_SCHEMA,
    )
    async def _run_shortcut_tool(
        arguments: RunShortcutArguments,
    ) -> ToolResult:
        timeout_seconds = (
            float(arguments.timeoutSeconds)
            if arguments.timeoutSeconds is not None
            else None
        )

        result = await run_shortcut(
            shortcut_name=arguments.shortcutName,
            text_input=arguments.textInput,
            timeout=timeout_seconds,
        )

        summary_lines: list[str] = []
        if result.timed_out:
            if timeout_seconds is not None:
                summary_lines.append(
                    f"Shortcut '{arguments.shortcutName}' timed out after {timeout_seconds} seconds."
                )
            else:
                summary_lines.append(
                    f"Shortcut '{arguments.shortcutName}' timed out."
                )
        elif result.succeeded:
            summary_lines.append(
                f"Shortcut '{arguments.shortcutName}' completed successfully."
            )
        else:
            summary_lines.append(
                f"Shortcut '{arguments.shortcutName}' exited with return code {result.return_code}."
            )

        stdout_text = result.stdout.strip()
        stderr_text = result.stderr.strip()
        if stdout_text:
            summary_lines.append("--- stdout ---\n" + stdout_text)
        if stderr_text:
            summary_lines.append("--- stderr ---\n" + stderr_text)

        structured = RunShortcutStructuredResponse(
            command=list(result.command),
            returnCode=result.return_code,
            stdout=result.stdout,
            stderr=result.stderr,
            timedOut=result.timed_out,
            succeeded=result.succeeded,
        )

        content = [
            TextContent(
                type="text",
                text="\n\n".join(summary_lines)
                if summary_lines
                else "No output produced.",
            )
        ]

        return ToolResult(
            content=content,
            structured_content=structured.model_dump(),
        )

    _APP = app
    return app


async def serve_stdio() -> None:
    """Run the MCP server over stdio using FastMCP's runner."""

    app = get_app()
    await app.run_stdio_async()

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
        instructions=instructions,
        website_url="https://support.apple.com/guide/shortcuts/welcome/mac",
        host=host,
        port=port,
        json_response=json_response,
        stateless_http=stateless_http,
        transport_security=transport_security,
    )

    @app.tool(
        name=RUN_SHORTCUT_TOOL_NAME,
        description=(
            "Run a Siri Shortcut that exists on the host macOS machine using "
            "the `shortcuts run` command."
        ),
        structured_output=True,
    )
    async def run_shortcut_tool(
        shortcutName: Annotated[str, Field(min_length=1)],
        textInput: str | None = None,
        timeoutSeconds: Annotated[float | None, Field(gt=0)] = None,
    ) -> RunShortcutResult:
        """Execute a Shortcut and return structured telemetry."""

        if not shortcutName.strip():
            raise ShortcutExecutionError("`shortcutName` must be a non-empty string.")

        timeout_seconds = _validate_timeout(timeoutSeconds)

        execution = await run_shortcut(
            shortcut_name=shortcutName,
            text_input=textInput,
            timeout=timeout_seconds,
        )

        structured = RunShortcutResult(
            command=list(execution.command),
            returnCode=execution.return_code,
            stdout=execution.stdout,
            stderr=execution.stderr,
            timedOut=execution.timed_out,
            succeeded=execution.succeeded,
        )

        structured.summary = _build_summary(
            shortcut_name=shortcutName,
            execution_result=structured,
            timeout_seconds=timeout_seconds,
        )

        return structured

    tool = app._tool_manager.get_tool(RUN_SHORTCUT_TOOL_NAME)
    if tool is not None:
        original_convert_result = tool.fn_metadata.convert_result

        def _convert_result(result: RunShortcutResult) -> tuple[list[types.TextContent], dict[str, Any]] | Any:
            if isinstance(result, RunShortcutResult):
                summary_text = result.summary or "No output produced."
                content = [types.TextContent(type="text", text=summary_text)]
                structured_payload = result.model_dump(
                    mode="json", by_alias=True, exclude={"summary"}
                )
                return content, structured_payload

            return original_convert_result(result)

        tool.fn_metadata.convert_result = _convert_result  # type: ignore[assignment]

    return app
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

    app = get_app()

    # Configure response format and stateless behaviour on the server instance.
    app._deprecated_settings.json_response = json_response
    app._deprecated_settings.stateless_http = stateless

    middleware: list[Middleware] = []
    if allowed_hosts:
        middleware.append(
            Middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
        )
    if allowed_origins:
        middleware.append(
            Middleware(
                CORSMiddleware,
                allow_origins=allowed_origins,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        )

    uvicorn_config: dict[str, Any] = {}
    if ssl_certfile and ssl_keyfile:
        uvicorn_config["ssl_certfile"] = ssl_certfile
        uvicorn_config["ssl_keyfile"] = ssl_keyfile

    await app.run_http_async(
        transport="streamable-http",
        host=host,
        port=port,
        uvicorn_config=uvicorn_config or None,
        middleware=middleware or None,
        stateless_http=stateless,
    )


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


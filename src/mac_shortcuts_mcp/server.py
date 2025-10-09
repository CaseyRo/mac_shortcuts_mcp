"""MCP server definition for mac-shortcuts-mcp."""

from __future__ import annotations

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
    try:
        return version("mac-shortcuts-mcp")
    except Exception:
        return __version__


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


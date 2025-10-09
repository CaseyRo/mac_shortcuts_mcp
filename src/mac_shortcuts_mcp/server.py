"""MCP server definition for mac-shortcuts-mcp."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as pkg_version
from typing import Annotated, Any, Iterable

from mcp import types
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, ConfigDict, Field

from . import __version__
from .shortcuts import ShortcutExecutionError, run_shortcut

SERVER_NAME = "mac-shortcuts-mcp"
RUN_SHORTCUT_TOOL_NAME = "run_shortcut"


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

    instructions = (
        "Execute Siri Shortcuts on macOS hosts using the `shortcuts` command line tool. "
        "Provide the shortcut display name and optional text input."
    )

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


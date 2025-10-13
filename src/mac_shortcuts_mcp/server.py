"""MCP server definition for mac-shortcuts-mcp."""

from __future__ import annotations

import inspect
from collections.abc import Iterable
from importlib.metadata import PackageNotFoundError, version as pkg_version
from typing import Annotated, Any

import anyio
from fastmcp.server.server import FastMCP as FastMCPBase
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field

from mac_shortcuts_mcp import __version__
from mac_shortcuts_mcp.shortcuts import (
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

class RunShortcutStructuredResponse(BaseModel):
    """Structured response returned from the ``run_shortcut`` tool."""

    summary: str
    command: list[str]
    returnCode: int | None
    stdout: str
    stderr: str
    timedOut: bool
    succeeded: bool


_APP: FastMCP | None = None


_FASTMCP_SUPPORTS_VERSION = "version" in inspect.signature(FastMCP.__init__).parameters


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
        structured_output=True,
    )
    async def _run_shortcut_tool(
        shortcutName: Annotated[
            str,
            Field(
                ...,
                min_length=1,
                description="Display name of the shortcut to execute.",
            ),
        ],
        textInput: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Optional text forwarded to the shortcut via the `--input` argument."
                ),
            ),
        ] = None,
        timeoutSeconds: Annotated[
            float | None,
            Field(
                default=None,
                gt=0,
                description="Maximum seconds to wait for the shortcut before aborting.",
            ),
        ] = None,
    ) -> RunShortcutStructuredResponse:
        shortcut_name = shortcutName.strip()
        if not shortcut_name:
            raise ShortcutExecutionError("`shortcutName` must be a non-empty string.")

        timeout_seconds = _validate_timeout(timeoutSeconds)

        execution = await run_shortcut(
            shortcut_name=shortcut_name,
            text_input=textInput,
            timeout=timeout_seconds,
        )

        summary = _build_summary(
            shortcut_name=shortcut_name,
            execution=execution,
            timeout_seconds=timeout_seconds,
        )

        return RunShortcutStructuredResponse(
            summary=summary,
            command=list(execution.command),
            returnCode=execution.return_code,
            stdout=execution.stdout,
            stderr=execution.stderr,
            timedOut=execution.timed_out,
            succeeded=execution.succeeded,
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

    app_kwargs: dict[str, Any] = {
        "name": SERVER_NAME,
        "instructions": SERVER_INSTRUCTIONS,
        "website_url": "https://support.apple.com/guide/shortcuts/welcome/mac",
        "host": host,
        "port": port,
        "json_response": json_response,
        "stateless_http": stateless_http,
        "transport_security": transport_security,
    }

    package_version = _get_version()
    if _FASTMCP_SUPPORTS_VERSION:
        app_kwargs["version"] = package_version

    app = FastMCP(**app_kwargs)

    if not _FASTMCP_SUPPORTS_VERSION:
        # ``mcp.server.fastmcp.FastMCP`` no longer accepts ``version=`` in its
        # constructor (the metadata now lives on the wrapped low-level server).
        # Preserve the published package version in the handshake metadata when
        # possible so clients can keep displaying it.
        low_level_server = getattr(app, "_mcp_server", None)
        if low_level_server is not None and getattr(low_level_server, "version", None) is None:
            low_level_server.version = package_version

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

    def __init__(self, *, version: str | None = None, **_: Any) -> None:
        """Initialise the adapter, ignoring legacy keyword arguments.

        Recent releases of the ``mcp`` package removed the ``version`` keyword
        from :class:`mcp.server.fastmcp.FastMCP`. Older FastMCP CLI versions may
        still attempt to provide that keyword when instantiating the exported
        ``server`` object. Accept (and discard) it here so both old and new
        CLIs can construct the adapter without raising a ``TypeError``.
        """

        del version

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

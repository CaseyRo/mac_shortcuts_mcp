"""MCP server definition for mac-shortcuts-mcp."""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import signal
import sys
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

# Configure logging if not already configured
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SERVER_NAME = "mac-shortcuts-mcp"
RUN_SHORTCUT_TOOL_NAME = "run_shortcut"
SERVER_INSTRUCTIONS = (
    "Execute Siri Shortcuts on macOS hosts using the `shortcuts` command line tool. "
    "Provide the shortcut display name and optional text input."
)

class RunShortcutArguments(BaseModel):
    """Request payload for the ``run_shortcut`` tool."""

    shortcutName: str = Field(
        ...,
        min_length=1,
        description="Display name of the shortcut to execute.",
    )
    textInput: str | None = Field(
        default=None,
        description="Optional text piped to the shortcut's standard input.",
    )
    timeoutSeconds: float | None = Field(
        default=None,
        gt=0,
        description="Maximum seconds to wait for the shortcut before aborting.",
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


def _setup_signal_handlers(shutdown_event: asyncio.Event) -> None:
    """Register signal handlers for graceful shutdown.

    Args:
        shutdown_event: Event to set when shutdown is requested.
    """
    def handle_shutdown(signum: int, frame: Any) -> None:
        """Signal handler that triggers graceful shutdown."""
        sig_name = signal.Signals(signum).name
        if not shutdown_event.is_set():
            logger.info(f"Received {sig_name}, initiating graceful shutdown...")
            shutdown_event.set()
        else:
            logger.info(f"Received {sig_name} during shutdown, please wait...")

    # Register handlers for SIGINT (Ctrl+C) and SIGTERM
    signals_to_handle = [signal.SIGINT, signal.SIGTERM]
    for sig in signals_to_handle:
        try:
            signal.signal(sig, handle_shutdown)
        except (OSError, ValueError) as exc:
            # Some signals may not be available on all platforms
            logger.debug(f"Could not register handler for {sig.name}: {exc}")


async def _run_with_graceful_shutdown(
    main_task: asyncio.Task[Any],
    shutdown_event: asyncio.Event,
    *,
    timeout: float = 10.0,
) -> None:
    """Run a task with graceful shutdown support.

    Args:
        main_task: The main server task to run.
        shutdown_event: Event that signals shutdown request.
        timeout: Maximum seconds to wait for graceful shutdown (default: 10).
    """
    try:
        # Wait for either the main task to complete or shutdown signal
        shutdown_waiter = asyncio.create_task(shutdown_event.wait())
        done, pending = await asyncio.wait(
            [main_task, shutdown_waiter],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # If shutdown was signaled, cancel the main task
        if shutdown_event.is_set():
            if not main_task.done():
                logger.info("Cancelling server task...")
                main_task.cancel()
                try:
                    await asyncio.wait_for(main_task, timeout=timeout)
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Graceful shutdown timed out after {timeout}s, forcing exit"
                    )
                    sys.exit(1)
                except asyncio.CancelledError:
                    logger.info("Server task cancelled successfully")

        # Clean up the waiter task if it's still pending
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except asyncio.CancelledError:
        logger.info("Shutdown cancelled")
        raise
    except Exception as exc:
        logger.error(f"Error during shutdown: {exc}")
        raise


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
    """Run the MCP server over stdio using FastMCP's runner.

    Note: Graceful shutdown via KeyboardInterrupt doesn't work well with stdio
    due to stdin blocking. We install a SIGINT handler that calls os._exit(0)
    directly for immediate termination.
    """

    # Install signal handler INSIDE the async context to override anyio's handler
    def immediate_exit(signum: int, frame: Any) -> None:
        """Exit immediately on SIGINT without any cleanup."""
        logger.info("\nReceived interrupt signal, exiting...")
        os._exit(0)

    signal.signal(signal.SIGINT, immediate_exit)
    signal.signal(signal.SIGTERM, immediate_exit)

    app = get_app()
    logger.info(f"MCP server '{SERVER_NAME}' ready on STDIO transport")

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
    """Run the MCP server using FastMCP's HTTP/SSE runner with graceful shutdown."""

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()
    _setup_signal_handlers(shutdown_event)

    app = create_fastmcp_app(
        host=host,
        port=port,
        json_response=json_response,
        stateless_http=stateless,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )

    protocol = "HTTPS" if ssl_certfile else "HTTP"
    mode = "JSON" if json_response else "SSE"
    logger.info(f"MCP server '{SERVER_NAME}' starting on {protocol} at {host}:{port} ({mode} mode)")

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

        # Uvicorn has its own signal handling, but we'll wrap it for consistency
        main_task = asyncio.create_task(server.serve())
        await _run_with_graceful_shutdown(main_task, shutdown_event)
        return

    # Run FastMCP's HTTP runner with graceful shutdown
    main_task = asyncio.create_task(app.run_streamable_http_async())
    await _run_with_graceful_shutdown(main_task, shutdown_event)


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

        # For stdio mode, install immediate exit handler to override anyio
        if normalized_transport == "stdio":
            def immediate_exit(signum: int, frame: Any) -> None:
                """Exit immediately on SIGINT without any cleanup."""
                logger.info("\nReceived interrupt signal, exiting...")
                os._exit(0)

            signal.signal(signal.SIGINT, immediate_exit)
            signal.signal(signal.SIGTERM, immediate_exit)

            logger.info("Starting MCP server in STDIO mode...")
            logger.info("Press Ctrl+C to stop the server")
            await serve_stdio()
            return

        if normalized_transport in {"http", "streamable-http", "sse"}:
            json_response = normalized_transport == "http"
            logger.info("Starting MCP server in HTTP mode...")
            logger.info("Press Ctrl+C to stop the server")
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

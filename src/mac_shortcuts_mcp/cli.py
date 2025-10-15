"""Command line interface for mac-shortcuts-mcp."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any, Optional

import typer

from mac_shortcuts_mcp import __version__
from mac_shortcuts_mcp.server import serve_http, serve_stdio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _install_immediate_exit_handler() -> None:
    """Install a signal handler that exits immediately without cleanup.

    This is necessary for stdio mode where stdin blocking prevents
    graceful cancellation of async tasks.
    """
    def immediate_exit(signum: int, frame: Any) -> None:
        """Exit immediately on SIGINT without any cleanup."""
        logger.info("\nReceived interrupt signal, exiting...")
        os._exit(0)

    signal.signal(signal.SIGINT, immediate_exit)

app = typer.Typer(
    help="Run the mac-shortcuts-mcp server over stdio or HTTP.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the package version."""

    typer.echo(__version__)


@app.command()
def stdio() -> None:
    """Start the MCP server using the stdio transport with graceful shutdown."""

    # Install immediate exit handler before starting server
    # This ensures Ctrl+C exits immediately without stdin lock issues
    _install_immediate_exit_handler()

    logger.info("Starting MCP server in STDIO mode...")
    logger.info("Press Ctrl+C to stop the server")

    asyncio.run(serve_stdio())


@app.command()
def http(
    host: str = typer.Option("127.0.0.1", help="Host interface to bind."),
    port: int = typer.Option(8000, help="Port to listen on."),
    json_response: bool = typer.Option(
        False,
        help="Return JSON responses instead of SSE streams.",
    ),
    stateless: bool = typer.Option(
        False,
        help="Disable session reuse and treat every request independently.",
    ),
    allowed_host: list[str] = typer.Option(
        [],
        help="Allowed Host headers when DNS rebinding protection is enabled.",
    ),
    allowed_origin: list[str] = typer.Option(
        [],
        help="Allowed Origin headers when DNS rebinding protection is enabled.",
    ),
    certfile: Optional[Path] = typer.Option(
        None,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to a TLS certificate for HTTPS.",
    ),
    keyfile: Optional[Path] = typer.Option(
        None,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the TLS private key matching --certfile.",
    ),
) -> None:
    """Start the MCP server over HTTP(S) with streaming support and graceful shutdown."""

    if bool(certfile) ^ bool(keyfile):
        raise typer.BadParameter(
            "--certfile and --keyfile must be provided together.",
            param_hint="certfile",
        )

    logger.info("Starting MCP server in HTTP mode...")
    logger.info("Press Ctrl+C to stop the server")

    try:
        asyncio.run(
            serve_http(
                host=host,
                port=port,
                json_response=json_response,
                stateless=stateless,
                allowed_hosts=allowed_host,
                allowed_origins=allowed_origin,
                ssl_certfile=str(certfile) if certfile else None,
                ssl_keyfile=str(keyfile) if keyfile else None,
            )
        )
    except KeyboardInterrupt:
        logger.info("Server stopped")
        sys.exit(0)


def run() -> None:
    """Entry point for ``python -m mac_shortcuts_mcp``."""

    app()


if __name__ == "__main__":
    run()

"""Command line interface for mac-shortcuts-mcp."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer

from mcp.server.fastmcp import FastMCP

from . import __version__
from .server import create_fastmcp_app

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
    """Start the MCP server using the stdio transport."""

    app_instance = create_fastmcp_app()
    asyncio.run(app_instance.run_stdio_async())


async def _run_http(
    app_instance: FastMCP,
    *,
    ssl_certfile: str | None,
    ssl_keyfile: str | None,
) -> None:
    if ssl_certfile or ssl_keyfile:
        import uvicorn

        http_app = app_instance.streamable_http_app()
        config = uvicorn.Config(
            http_app,
            host=app_instance.settings.host,
            port=app_instance.settings.port,
            log_level=app_instance.settings.log_level.lower(),
            ssl_certfile=ssl_certfile,
            ssl_keyfile=ssl_keyfile,
        )
        server = uvicorn.Server(config)
        await server.serve()
    else:
        await app_instance.run_streamable_http_async()


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
    """Start the MCP server over HTTP(S) with streaming support."""

    if bool(certfile) ^ bool(keyfile):
        raise typer.BadParameter(
            "--certfile and --keyfile must be provided together.",
            param_hint="certfile",
        )

    if certfile and keyfile:
        ssl_options = {
            "ssl_certfile": str(certfile),
            "ssl_keyfile": str(keyfile),
        }
    else:
        ssl_options = {}

    app_instance = create_fastmcp_app(
        host=host,
        port=port,
        json_response=json_response,
        stateless_http=stateless,
        allowed_hosts=allowed_host,
        allowed_origins=allowed_origin,
    )

    asyncio.run(
        _run_http(
            app_instance,
            ssl_certfile=ssl_options.get("ssl_certfile"),
            ssl_keyfile=ssl_options.get("ssl_keyfile"),
        )
    )


def run() -> None:
    """Entry point for ``python -m mac_shortcuts_mcp``."""

    app()


if __name__ == "__main__":
    run()

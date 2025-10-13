"""Utilities for interacting with the macOS Shortcuts command line tool."""

from __future__ import annotations

import asyncio
import dataclasses
import shutil
from typing import Sequence


class ShortcutExecutionError(RuntimeError):
    """Raised when the Shortcuts command cannot be executed."""


@dataclasses.dataclass(slots=True)
class ShortcutExecutionResult:
    """Represents the outcome of running a Siri Shortcut."""

    command: Sequence[str]
    return_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the shortcut finished successfully."""

        return not self.timed_out and self.return_code == 0


async def run_shortcut(
    shortcut_name: str,
    *,
    text_input: str | None = None,
    timeout: float | None = None,
) -> ShortcutExecutionResult:
    """Run the given Siri Shortcut via the ``shortcuts`` CLI.

    Args:
        shortcut_name: The display name of the shortcut to run.
        text_input: Optional text input piped to the shortcut via stdin.
        timeout: Optional timeout in seconds before the process is terminated.

    Returns:
        A :class:`ShortcutExecutionResult` describing the execution.

    Raises:
        ShortcutExecutionError: If the ``shortcuts`` binary cannot be found or
            fails to launch.
    """

    binary = shutil.which("shortcuts")
    if not binary:
        raise ShortcutExecutionError(
            "The 'shortcuts' command line tool is not available. "
            "Install the Shortcuts CLI on macOS and ensure it is on PATH."
        )

    command = [binary, "run", shortcut_name]

    input_bytes: bytes | None = None
    stdin_setting = None
    if text_input:
        input_bytes = text_input.encode("utf-8")
        stdin_setting = asyncio.subprocess.PIPE

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=stdin_setting,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise ShortcutExecutionError(
            "Unable to start the 'shortcuts' command line tool"
        ) from exc

    timed_out = False
    stdout_bytes: bytes = b""
    stderr_bytes: bytes = b""

    try:
        communicate_kwargs = {}
        if input_bytes is not None:
            communicate_kwargs["input"] = input_bytes

        if timeout is not None:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(**communicate_kwargs),
                timeout=timeout,
            )
        else:
            stdout_bytes, stderr_bytes = await process.communicate(**communicate_kwargs)
    except asyncio.TimeoutError:
        timed_out = True
        process.kill()
        try:
            await process.wait()
        except Exception:
            # Ensure the process is reaped even if wait() fails.
            pass

    if timed_out:
        return ShortcutExecutionResult(
            command=command,
            return_code=None,
            stdout="",
            stderr="",
            timed_out=True,
        )

    return ShortcutExecutionResult(
        command=command,
        return_code=process.returncode,
        stdout=stdout_bytes.decode("utf-8", errors="replace"),
        stderr=stderr_bytes.decode("utf-8", errors="replace"),
        timed_out=False,
    )


# Proposal: Add Graceful Shutdown

## Why
The MCP server currently hangs when users attempt to exit via Ctrl+C (SIGINT) or other termination signals. The server doesn't handle signals properly, requiring forceful termination and leaving async tasks in undefined states. This creates a poor user experience and can potentially leave shortcuts running in the background.

## What Changes
- Add signal handling (SIGINT, SIGTERM) to both STDIO and HTTP transport modes
- Implement graceful shutdown that:
  - Catches termination signals
  - Cancels running shortcut executions
  - Cleans up async tasks properly
  - Exits cleanly without hanging
- Add timeout mechanism to force shutdown if graceful shutdown takes too long (10 seconds)
- Preserve existing behavior for normal exits

## Impact
- **Affected specs**: New capability `server-lifecycle`
- **Affected code**:
  - `cli.py` - Update `stdio()` and `http()` commands with signal handlers
  - `server.py` - Add signal handling to `serve_stdio()` and `serve_http()`
- **Breaking changes**: None - purely additive improvement to existing behavior
- **User experience**: Users can now cleanly exit with single Ctrl+C


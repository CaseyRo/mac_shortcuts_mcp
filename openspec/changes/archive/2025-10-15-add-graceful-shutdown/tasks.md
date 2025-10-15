# Implementation Tasks

## 1. Add Signal Handling Infrastructure
- [x] 1.1 Create signal handler setup function that catches SIGINT and SIGTERM
- [x] 1.2 Add graceful shutdown coordination using asyncio.Event
- [x] 1.3 Implement shutdown timeout mechanism (10 second limit)

## 2. Update STDIO Server
- [x] 2.1 Wrap `serve_stdio()` with signal handling
- [x] 2.2 Ensure running shortcuts are properly cancelled on shutdown
- [x] 2.3 Test Ctrl+C exits cleanly in STDIO mode

## 3. Update HTTP Server
- [x] 3.1 Wrap `serve_http()` with signal handling
- [x] 3.2 Integrate with uvicorn's shutdown mechanism when using TLS
- [x] 3.3 Test Ctrl+C exits cleanly in HTTP/SSE mode

## 4. Update CLI Commands
- [x] 4.1 Update `cli.py` stdio() command to use new signal handling
- [x] 4.2 Update `cli.py` http() command to use new signal handling
- [x] 4.3 Update FastMCP adapter if needed

## 5. Testing & Validation
- [x] 5.1 Manual test: Start STDIO server, send Ctrl+C, verify clean exit
- [x] 5.2 Manual test: Start HTTP server, send Ctrl+C, verify clean exit
- [x] 5.3 Manual test: Start shortcut, send Ctrl+C mid-execution, verify cancellation (graceful shutdown cancels async tasks)
- [x] 5.4 Verify no hanging processes or zombie shortcuts remain (confirmed clean exits)


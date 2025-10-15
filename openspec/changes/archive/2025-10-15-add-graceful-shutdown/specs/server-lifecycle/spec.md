# Server Lifecycle Specification Delta

## ADDED Requirements

### Requirement: Signal Handling
The server SHALL handle termination signals (SIGINT, SIGTERM) gracefully to ensure clean shutdown without hanging or leaving orphaned processes.

#### Scenario: User presses Ctrl+C once
- **WHEN** the user sends SIGINT (Ctrl+C) to the running server
- **THEN** the server SHALL log shutdown initiation
- **AND** the server SHALL cancel all running shortcut executions
- **AND** the server SHALL clean up async tasks
- **AND** the server SHALL exit with code 0 within 2 seconds

#### Scenario: Multiple Ctrl+C presses
- **WHEN** the user sends multiple SIGINT signals in rapid succession
- **THEN** the first signal SHALL initiate graceful shutdown
- **AND** subsequent signals within the shutdown window SHALL be acknowledged but not restart shutdown
- **AND** the server SHALL still exit cleanly

#### Scenario: Shutdown during shortcut execution
- **WHEN** a shortcut is running and SIGINT is received
- **THEN** the running shortcut process SHALL be terminated
- **AND** the MCP tool response SHALL indicate the shortcut was cancelled
- **AND** no zombie processes SHALL remain

### Requirement: Shutdown Timeout
The server SHALL enforce a maximum shutdown time to prevent indefinite hangs.

#### Scenario: Graceful shutdown completes quickly
- **WHEN** shutdown is initiated and all tasks complete within 1 second
- **THEN** the server SHALL exit normally with code 0

#### Scenario: Graceful shutdown exceeds timeout
- **WHEN** shutdown is initiated but cleanup takes longer than 10 seconds
- **THEN** the server SHALL force terminate all remaining tasks
- **AND** the server SHALL exit with code 1
- **AND** a warning SHALL be logged about forced shutdown

### Requirement: Platform Compatibility
Signal handling SHALL work correctly on macOS (primary platform) and be compatible with standard POSIX signal behavior.

#### Scenario: Running on macOS
- **WHEN** the server runs on macOS
- **THEN** SIGINT (Ctrl+C) and SIGTERM SHALL be properly caught
- **AND** shutdown SHALL complete without hanging

#### Scenario: Signal not available on platform
- **WHEN** a signal type is not available on the current platform (e.g., Windows)
- **THEN** the server SHALL skip registering that specific signal handler
- **AND** continue functioning with available signals


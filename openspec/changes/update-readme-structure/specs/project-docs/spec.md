## ADDED Requirements
### Requirement: README Structure and Navigation
The README MUST present a clear outline that helps new users move from prerequisites to running the MCP server.

#### Scenario: Reader scans top-level sections
- **WHEN** a developer opens README.md
- **THEN** the first headings after the title SHALL include Overview, Prerequisites, Installation, Running the Server, Client Integration, and Advanced Configuration/Troubleshooting content
- **AND** a table of contents SHALL link to those sections for quick navigation

#### Scenario: Reader identifies recommended run command
- **WHEN** the developer reads the Running the Server section
- **THEN** the FastMCP STDIO command SHALL be presented as the primary quick-start command with context on transport variants

### Requirement: Documented Tool Payload Usage
The README MUST describe how to invoke the exposed `run_shortcut` tool payload with required fields.

#### Scenario: Reader learns payload format
- **WHEN** the developer reaches the Client Integration or Usage section
- **THEN** an example JSON payload SHALL document `shortcutName`, optional `textInput`, and `timeoutSeconds`
- **AND** the README SHALL explain how stdin piping maps to `textInput`

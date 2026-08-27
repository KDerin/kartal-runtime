# Security policy

KARTAL Runtime is currently alpha research software.

## Supported versions

Only the latest release receives security fixes during the alpha phase.

## Reporting a vulnerability

Do not publish exploitable details in a public issue. Use GitHub's private vulnerability
reporting feature for this repository. Include the affected version, reproduction steps,
impact, and any suggested mitigation.

## Security boundaries

- A provenance record proves consistency of the recorded journal, not truth of its content.
- Tool execution must still be sandboxed and authorized by the host application.
- Secrets and raw personal data should not be placed in node payloads.
- Human approval is an application control; it must use authenticated reviewer identities.
- Exported snapshots must be protected by the host system's access controls.

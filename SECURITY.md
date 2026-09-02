# Security Policy

## Reporting a Vulnerability

MindForge is a local-first encrypted memory system — security is core to the project.

If you discover a security vulnerability, please report it responsibly:

1. **Email**: 2638895480@qq.com
2. **Subject line**: `[SECURITY] MindForge — <brief description>`
3. **Include**: steps to reproduce, affected version, potential impact

## Response Timeline

| Stage | Target |
|-------|--------|
| Acknowledgment | 48 hours |
| Initial assessment | 7 days |
| Fix or mitigation | 30 days (severity-dependent) |

## Scope

- Encryption implementation (AES-256-GCM, PBKDF2-SHA256)
- API authentication and rate limiting
- MCP tool parameter validation
- Local storage and database access

## Out of Scope

- Third-party dependencies (report upstream)
- Social engineering attacks

## Disclosure

We follow coordinated disclosure. Please do not publish details publicly until a fix is released.

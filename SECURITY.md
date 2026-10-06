# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

Please do not report security vulnerabilities through public GitHub issues.
Submit findings privately to security@paseoms.com.

## Security Constraints

- **Fail-Closed Architecture**: Unhandled tool exceptions must never leak unsanitized internal states or terminate transport streams unexpectedly.
- **Data Boundary**: Raw tabular objects (`DataFrame`) are strictly forbidden across tool boundaries to eliminate token exhaustion attacks.
- **Secrets & Isolation**: This repository contains zero tenant credentials, proprietary endpoints, or private models.

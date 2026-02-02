# Security Policy

## Supported Versions

Currently supported versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.0.6   | :white_check_mark: |
| < 0.0.6 | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please:

1. **DO NOT** open a public issue
2. Send details to: admin@foodsaid.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)

We will respond within 48 hours and provide updates every 5 business days.

## Security Features

This project implements:

- **Input Validation**: All user inputs are validated and sanitized
- **Rate Limiting**: 100 requests/minute globally, 50 requests/minute per endpoint
- **Security Headers**:
  - Content-Security-Policy
  - X-Frame-Options: DENY
  - X-Content-Type-Options: nosniff
  - X-XSS-Protection
- **CORS Configuration**: Controlled cross-origin access
- **Docker Security**: Non-root user execution
- **Logging**: Comprehensive request and error logging
- **No Hardcoded Secrets**: All sensitive data via environment variables

## Security Best Practices

When deploying this service:

1. **Environment Variables**: Never commit sensitive data
2. **HTTPS**: Always use HTTPS in production
3. **Rate Limiting**: Configure appropriate limits for your use case
4. **Updates**: Keep dependencies up-to-date (enable Dependabot)
5. **Monitoring**: Enable logging and monitor for suspicious activity

## Acknowledgments

We appreciate the security research community's efforts in keeping this project safe.

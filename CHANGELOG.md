# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.6] - 2026-02-02

### Added
- Configurable barcode layout parameters (`module_width`, `module_height`, `quiet_zone`, `font_size`, `text_distance`, `margin_top`)
- `SWAGGER_HOST` environment variable for dynamic API documentation host configuration
- `SWAGGER_SCHEMES` environment variable to configure supported protocols (http/https)
- Swagger UI now supports protocol selection dropdown (http and https)

### Changed
- Optimized default barcode layout for better readability and paper efficiency
- Improved barcode text positioning with proper spacing from barcode bars

---

## [0.0.5] - 2026-02-01

### Added
- Full ASCII character support for barcodes (characters 0-127)
- `BARCODE_MAX_LENGTH` configuration setting (64 characters)
- Support for special characters in barcodes: `-`, `.`, `@`, `#`, `_`, `/`, etc.
- Enhanced API documentation for barcode character support

### Changed
- **Breaking**: Barcode maximum length reduced from 1000 to 64 characters
- Removed alphanumeric-only restriction for barcodes
- Improved validation logic with separate limits for QR codes and barcodes
- Updated Swagger documentation to reflect new capabilities

### Fixed
- Barcode validation now properly supports Code128 full character set
- Improved error messages for content validation

---

## [0.0.2] - 2026-02-01

### Added
- Comprehensive input validation with length limits (max 1000 chars)
- Detailed logging for all operations and errors
- Security headers (X-Content-Type-Options, X-Frame-Options, CSP, etc.)
- CORS support for cross-origin requests
- Health check endpoint (`/health`) for monitoring
- Exception handling for all code generation operations
- Type hints throughout the codebase
- Comprehensive test suite with pytest (100+ tests)
- Development dependencies (flake8, black, pylint, mypy)
- Pre-commit hooks for code quality
- GitHub Actions CI/CD pipeline
- Docker multi-stage builds for smaller images
- Non-root user in Docker containers for security
- Health check in Dockerfile
- `.dockerignore` for optimized builds
- `docker-compose.yml` for easy local development
- Complete documentation (LICENSE, CHANGELOG, CONTRIBUTING)
- Code quality tools configuration

### Changed
- Refactored main.py with proper code organization
- Moved all imports to the top (PEP 8 compliant)
- Fixed dependency versions in requirements.txt
- Improved error messages with specific details
- Enhanced Dockerfile with security best practices
- Updated `.gitignore` with comprehensive exclusions
- Improved `run_local.sh` with error checking

### Security
- Added input sanitization and validation
- Implemented rate limiting protection via input validation
- Added security response headers
- Docker containers now run as non-root user
- Fixed potential XSS and injection vulnerabilities

---

## [0.0.1] - 2026-02-01

### Added
- Initial implementation of QR code generation
- Barcode (Code128) generation support
- Flask-based REST API
- Docker support
- Basic documentation in README
- Dynamic PORT configuration

### Changed
- Updated default port from 5033 to 8080 for production
- Moved project files to repository root

---

[0.0.6]: https://github.com/foodsaid/qrbarcode/compare/v0.0.5...v0.0.6
[0.0.5]: https://github.com/foodsaid/qrbarcode/compare/v0.0.2...v0.0.5
[0.0.2]: https://github.com/foodsaid/qrbarcode/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/foodsaid/qrbarcode/releases/tag/v0.0.1

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-10-25

### Added
- `type=datamatrix` and `type=ean13` (EAN-13 adds or verifies the GS1 check digit), via zxing-cpp
- `format=svg` for every type; `scale`, `size`, `border`, `ec` (QR error correction) and `text` options
- `codes.py`: rendering independent of Flask, shared by the API and the upcoming MCP server
- Tests decode every generated image with zxing-cpp; `docs/v0.2-plan.md` describes the v0.2 roadmap
- GS1 Digital Link: `GET /gs1/digital-link` validates GTIN (check digit), batch/serial (CSET 82) and dates (`YYMMDD` or `YYYY-MM-DD`), and returns the URI, element string and AIs; `type=gs1qr` and `type=gs1datamatrix` (true GS1 `]d2` with FNC1) in `/generate`; custom resolver via `domain`
- `gs1.py` (pure, no dependencies) with Digital Link parsing, and shared GS1 test vectors in `tests/gs1_vectors.json`
- Signed anti-counterfeit codes (Ed25519): `POST /sign` (Bearer API key, hashed) for URLs or GS1 fields, `GET /verify`, `GET /.well-known/qr-signing-keys.json` (JWKS); key rotation via `SIGNING_PUBLIC_KEY_FILES`; `scripts/gen_signing_key.py`; `docker-compose.signing.yml` mounts the key as a Docker secret
- Request bodies are limited to 64 KB (was 16 MB)
- MCP server `qr_mcp.py` (stdio, official `mcp` SDK 2.3.0 `MCPServer`): read-only tools `generate_code`, `generate_gs1_code`, `build_gs1_digital_link`, `verify_signed_code`; PNG as image content, SVG as text, structured results, validation errors returned to the model; own lock `requirements-mcp.txt`, audited in CI, not in the Docker image
- `KeyRing.from_jwks()` to verify with a published JWKS (`QR_SIGNING_JWKS` path or https URL)

### Fixed (since phase 1)
- EAN-13 validation errors were wrapped twice ("Cannot encode content: …")

### Fixed
- QR content beyond capacity returned 500 (qrcode 8 raises `ValueError`, not `DataOverflowError`); now a 400 with a clear message

---

## [0.1.5] - 2026-10-25

### Security
- Security headers on every response (was `/generate` only): CSP (`default-src 'none'` for the API; same-origin scripts only for `/docs`), `X-Frame-Options: DENY` / `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy`; `X-XSS-Protection` set to `0` as browsers no longer support the auditor
- Generation errors no longer echo exception text to clients
- gunicorn uses threaded workers (`gthread`, 2×4) so idle connections can no longer tie up every worker until the 30 s timeout; the gunicorn 26 control socket is disabled
- Docker Compose runs the container with a read-only root filesystem, `cap_drop: ALL`, `no-new-privileges` and a PID limit
- Swagger UI `queryConfigEnabled: false` is now explicit, so `?url=` cannot load a foreign spec
- New CI check of the vendored Swagger UI and its bundled DOMPurify against OSV, with reviewed advisories in `scripts/vendored_vuln_allowlist.json`; CI also runs weekly
- `SECURITY.md` documents the protections, known and accepted risks, and a deployment checklist

### Fixed
- `scripts/deploy_local.sh` and `run_local.sh` are executable again (`make docker-deploy` failed with "Permission denied")

---

## [0.1.4] - 2026-10-25

### Added
- GitHub Releases: pushing a `vX.Y.Z` tag publishes a release whose notes are the matching CHANGELOG section (`.github/workflows/release.yml`, `scripts/release_notes.py`); the tag must match `main.__version__` and be on `main`
- `THIRD_PARTY_NOTICES.md` listing vendored and runtime third-party licenses, the bundled DejaVu font, and trademarks (QR Code, Swagger, OpenAPI); shipped in the Docker image
- Swagger UI `NOTICE` and `swagger-ui-bundle.js.LICENSE.txt` (required by Apache-2.0 and referenced by the bundle) vendored next to the bundle
- CI: copyleft license check inside the runtime image, Trivy scan of the built image (base OS packages included), hadolint, real smoke test of `/generate` and `/apispec.json`, and a check that the current version has a CHANGELOG section

### Changed
- `LICENSE` copyright holder is now foodsaid
- Docs page footer states the license, Swagger UI attribution and the QR Code trademark
- Docker image runs as numeric `USER 1000:1000`

### Security
- Removed pip and ensurepip from the runtime image: their vendored urllib3, msgpack and setuptools were the only HIGH findings of an image scan (CVE-2026-97687, CVE-2026-97689, GHSA-6v7p-g79w-8964, CVE-2025-47273) and are unused at runtime
- CI cancels superseded pull-request runs and no longer triggers on the unused `develop` branch

---

## [0.1.3] - 2026-10-25

### Fixed
- Swagger UI "Try it out" hung for ~30 s and then failed when the `https` server was picked on a plain-http port. Without `SWAGGER_HOST`, requests now use the docs page's own scheme and host (also correct behind a TLS-terminating proxy)

### Added
- `PROXY_COUNT`: trust `X-Forwarded-For` / `X-Forwarded-Proto` from that many reverse proxies, so rate limits count real client IPs behind Cloudflare Tunnel or nginx (previously all clients shared the proxy's limit)
- `/` redirects to `/docs`

### Changed
- Docs page: bilingual (Chinese/English) texts, `/generate` opens ready to execute, request duration shown, Servers dropdown and Schemas section hidden, contact/license links removed, tighter layout and an icon
- Without `SWAGGER_HOST` the spec has no `servers` list (Swagger UI then uses the page's own origin)
- `SWAGGER_SCHEMES` only applies when `SWAGGER_HOST` is set; its default is now `https,http`
- Default host port is now `8505` (Docker Compose `QR_HOST_PORT`, `run_local.sh`, `make run`, README examples); the container still listens on `8080`

---

## [0.1.2] - 2026-10-25

### Changed
- API docs are now an OpenAPI 3.0 spec maintained in `openapi.json` (was Swagger 2.0 generated from docstrings); `/docs` and `/apispec.json` keep their URLs
- `SWAGGER_HOST` / `SWAGGER_SCHEMES` now fill the OpenAPI `servers` list

### Removed
- Python 3.11 support (CI now tests 3.12–3.14; Docker stays on 3.13). Lock files no longer need 3.11-only entries, which Dependabot dropped when it re-resolved them
- Unused `[build-system]` table from `pyproject.toml` (the service is not packaged)
- `flasgger` (unmaintained since 2023) and the dependencies only it needed: mistune, jsonschema, referencing, rpds-py, PyYAML, six, attrs (runtime lock 29 → 20 packages)
- Vendored jQuery and the unused Swagger UI standalone preset

### Added
- Tests that the spec documents exactly the routes the app serves, and that documented limits match the runtime config

---

## [0.1.1] - 2026-10-25

### Changed
- Upgraded Flask-Limiter 3.8.0 → 4.1.1, qrcode 7.4.2 → 8.2, gunicorn 23.0.0 → 26.2.0, python-barcode 0.15.1 → 0.16.1 (generated images are pixel-identical)
- Upgraded dev tools (pytest 9.1.1, pytest-cov 7.1.0, flake8 7.4.1, pylint 4.1.2, mypy 2.4.0, pre-commit 4.6.2, bandit 1.9.4)
- Replaced `safety` with `pip-audit` (no account needed)
- CI now also tests Python 3.14

### Security
- Hash-pinned lock files (`requirements*.txt`) generated from `requirements*.in` with a 14-day release cooldown; Docker and CI install with `--require-hashes`
- Docker base image pinned by digest; removed the unpinned `pip` upgrade from the image build
- Pre-commit hooks frozen to commit SHAs
- Fixed vulnerable dev dependencies: virtualenv 21.14.13, filelock 4.2.4, certifi 2026.10.23
- Dependabot version updates for pip, GitHub Actions and Docker with cooldown
- CI runs `pip-audit` against both lock files

---

## [0.1.0] - 2026-10-25

### Added
- Configurable barcode layout parameters (`module_width`, `module_height`, `quiet_zone`, `font_size`, `text_distance`, `margin_top`) with paper-saving defaults
- `SWAGGER_HOST` / `SWAGGER_SCHEMES` environment variables for the API docs
- `RATE_LIMIT_ENABLED`, `RATE_LIMIT`, `GENERATE_RATE_LIMIT` environment variables
- `gunicorn.conf.py` and `scripts/deploy_local.sh` (versioned build, redeploy, rollback)
- Patched local Swagger UI 5.33.1 and jQuery 3.7.1 assets for `/docs`

### Changed
- Upgraded Flask to 3.1.3 and pinned security floors for werkzeug, pillow, mistune
- Docker Compose now runs the prebuilt `qr-service:stable` image on the external `qrnetwork` network
- CI lint, type and security checks now fail the build

### Security
- Application and gunicorn access logs no longer record encoded content or query strings
- Replaced flasgger's bundled Swagger UI 3.28.0 / jQuery 2.2.4, which have known XSS issues

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

[0.2.0]: https://github.com/foodsaid/qrbarcode/compare/v0.1.5...v0.2.0
[0.1.5]: https://github.com/foodsaid/qrbarcode/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/foodsaid/qrbarcode/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/foodsaid/qrbarcode/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/foodsaid/qrbarcode/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/foodsaid/qrbarcode/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/foodsaid/qrbarcode/releases/tag/v0.1.0

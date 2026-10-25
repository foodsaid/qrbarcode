# Security Policy

## Supported Versions

Currently supported versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please:

1. **DO NOT** open a public issue
2. Report it privately via [GitHub Security Advisories](https://github.com/foodsaid/qrbarcode/security/advisories/new)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)

We will respond within 48 hours and provide updates every 5 business days.

## Security Features

- **Input validation**: content length and type are checked; barcodes accept ASCII only. Generation errors return a generic message without exception details.
- **Rate limiting**: 100 requests/minute per client IP globally, 50/minute on `/generate`. Behind a reverse proxy set `PROXY_COUNT` so the real client IP is counted.
- **Security headers on every response**: `Content-Security-Policy` (`default-src 'none'` for the API; same-origin scripts only for `/docs`, no inline script), `X-Frame-Options: DENY` / `frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy`.
- **Log privacy**: logs record type, length and status, never the encoded content or query string.
- **Container**: non-root `USER 1000:1000`, no pip in the runtime image, base image pinned by digest. Docker Compose runs it with a read-only root filesystem, all Linux capabilities dropped, `no-new-privileges`, and memory/CPU/PID limits.
- **gunicorn**: threaded workers so idle connections cannot exhaust the pool; the runtime control socket is disabled.
- **Supply chain**: hash-pinned Python dependencies with a 14-day release cooldown; GitHub Actions, the base image and pre-commit hooks pinned by SHA/digest; only allowlisted actions may run.
- **Continuous checks** (every push and weekly): pip-audit, Trivy on the repository and the built image, OSV check of the vendored Swagger UI and its bundled DOMPurify, copyleft license check, bandit, CodeQL, Dependabot alerts, secret scanning with push protection.

## Signing Keys

- The Ed25519 private key is created by `scripts/gen_signing_key.py` with mode 0600, never overwritten, and mounted read-only as a Docker secret. `secrets/` and `*.pem` are ignored by git and excluded from the Docker build context; push protection blocks private keys.
- `POST /sign` requires a Bearer API key; only SHA-256 hashes are stored and compared in constant time. CORS does not allow `Authorization` or `POST`, so browsers on other sites cannot sign.
- A misconfigured key (missing file, wrong type) stops the service at startup instead of signing with something unexpected.
- Signatures cover a version tag, the key id and the exact URL text, and `kid`/`sig` must be the last parameters, so verification never depends on URL normalisation.
- If a key leaks: create a new key, stop listing the leaked public key, redeploy. Codes signed with the leaked key then fail verification.

## Known and Accepted Risks

| Item | Why it is accepted |
| :--- | :--- |
| DOMPurify 3.4.13 bundled in Swagger UI 5.33.1 has advisories (incl. GHSA-cg2g-xh64-v4q7, GHSA-mrv2-3pqr-j5jr) | They need `SAFE_FOR_TEMPLATES` or `IN_PLACE`, which Swagger UI never enables, and only this project's own `openapi.json` is rendered (`queryConfigEnabled: false`). Reviewed in `scripts/vendored_vuln_allowlist.json`; upgrade once a Swagger UI release bundles DOMPurify 3.4.17+. |
| Rate limits are in memory, per gunicorn worker (2 workers) | The effective limit per IP is up to 2× the configured value. Use a shared store (e.g. Redis via `limits`) if exact limits matter. |
| `Access-Control-Allow-Origin: *` | Public, read-only GET API with no cookies or authentication. |
| A signed code can be photocopied | Signatures stop forged data, not copies. Detecting copies needs per-item serials and scan tracking (planned). |
| The service is reachable by anyone who knows the URL | Intended for embedding in reports. To restrict it, put access control in front (e.g. Cloudflare Access or an IP allowlist). |

## Deployment Checklist

1. Bind the port to localhost (`QR_HOST_PORT=127.0.0.1:8505`) when a reverse proxy or tunnel fronts the service, and set `PROXY_COUNT=1`.
2. Serve over HTTPS only and enable HSTS at the proxy (e.g. Cloudflare: SSL/TLS → Edge Certificates → HSTS, and "Always Use HTTPS").
3. Keep the compose hardening (`read_only`, `cap_drop`, `no-new-privileges`, resource limits).
4. Redeploy after each release (`make docker-deploy`) so base image and dependency fixes reach production.
5. Never commit `.env` or other secrets; push protection blocks known secret formats.

## Acknowledgments

We appreciate the security research community's efforts in keeping this project safe.

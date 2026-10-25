"""
QR Code and Barcode Generation Service

A Flask-based microservice for generating QR codes and barcodes.
"""

import io
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple, Union

from flask import Flask, Response, jsonify, redirect, request, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.wrappers import Response as WerkzeugResponse

import codes
import gs1
import signing

# Built from GS1 fields (gtin, batch, serial, dates) instead of `content`
GS1_TYPES = {"gs1qr", "gs1datamatrix"}

__version__ = "0.1.5"


@dataclass
class Config:
    """Application configuration."""

    MAX_CONTENT_LENGTH: int = 1000
    BARCODE_MAX_LENGTH: int = 64
    DEFAULT_PORT: int = 8080
    ALLOWED_TYPES: set = field(default_factory=lambda: set(codes.KINDS) | GS1_TYPES)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT: str = "100 per minute"  # Global default per client IP
    GENERATE_RATE_LIMIT: str = "50 per minute"  # Per client IP on /generate
    DEBUG: bool = False
    # Reverse proxies in front of the app (e.g. 1 for a Cloudflare Tunnel). Their
    # X-Forwarded-For / X-Forwarded-Proto are trusted so rate limits count real client IPs.
    # Only set this when the port is reachable through those proxies alone.
    PROXY_COUNT: int = 0
    # Signed codes: PEM private key (Docker secret), retired public keys, API key hashes
    SIGNING_KEY_FILE: str = ""
    SIGNING_PUBLIC_KEY_FILES: str = ""
    SIGNING_API_KEY_HASHES: str = ""
    SIGN_RATE_LIMIT: str = "30 per minute"
    # API docs servers. Empty host = no servers list, so Swagger UI calls the docs page's own
    # scheme and host. Schemes only apply when SWAGGER_HOST is set; the first is the default.
    SWAGGER_HOST: str = ""
    SWAGGER_SCHEMES: list = field(default_factory=lambda: ["https", "http"])

    def __post_init__(self):
        """Load configuration from environment."""
        self.DEBUG = os.environ.get("DEBUG", "False").lower() == "true"
        self.DEFAULT_PORT = int(os.environ.get("PORT", self.DEFAULT_PORT))
        self.PROXY_COUNT = int(os.environ.get("PROXY_COUNT", self.PROXY_COUNT))
        self.RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true"
        self.RATE_LIMIT = os.environ.get("RATE_LIMIT", self.RATE_LIMIT)
        self.GENERATE_RATE_LIMIT = os.environ.get("GENERATE_RATE_LIMIT", self.GENERATE_RATE_LIMIT)
        self.SIGNING_KEY_FILE = os.environ.get("SIGNING_KEY_FILE", self.SIGNING_KEY_FILE)
        self.SIGNING_PUBLIC_KEY_FILES = os.environ.get(
            "SIGNING_PUBLIC_KEY_FILES", self.SIGNING_PUBLIC_KEY_FILES
        )
        self.SIGNING_API_KEY_HASHES = os.environ.get(
            "SIGNING_API_KEY_HASHES", self.SIGNING_API_KEY_HASHES
        )
        self.SIGN_RATE_LIMIT = os.environ.get("SIGN_RATE_LIMIT", self.SIGN_RATE_LIMIT)
        self.SWAGGER_HOST = os.environ.get("SWAGGER_HOST", self.SWAGGER_HOST)
        schemes_env = os.environ.get("SWAGGER_SCHEMES")
        if schemes_env:
            self.SWAGGER_SCHEMES = [s.strip() for s in schemes_env.split(",") if s.strip()]


# Initialize configuration
config = Config()

# Initialize Flask app
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # only POST /sign has a (small) JSON body
app.config["RATELIMIT_ENABLED"] = config.RATE_LIMIT_ENABLED
if config.PROXY_COUNT > 0:
    app.wsgi_app = ProxyFix(  # type: ignore[method-assign]
        app.wsgi_app, x_for=config.PROXY_COUNT, x_proto=config.PROXY_COUNT
    )

# Initialize rate limiter (in-memory: limits are per gunicorn worker)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[config.RATE_LIMIT],
    storage_uri="memory://",
)

# Fails at startup if a configured key file is missing or not Ed25519
keyring = signing.KeyRing.from_files(config.SIGNING_KEY_FILE, config.SIGNING_PUBLIC_KEY_FILES)

# OpenAPI spec, hand-maintained in openapi.json; /docs renders it with the vendored Swagger UI
OPENAPI_SPEC: Dict[str, Any] = json.loads(
    (Path(__file__).parent / "openapi.json").read_text(encoding="utf-8")
)
OPENAPI_SPEC["info"]["version"] = __version__

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
# Never log request content or query strings: they may carry order or customer data.


def validate_input(content: str, generate_type: str) -> Tuple[bool, str]:
    """
    Validate user input for content and type parameters.

    Args:
        content: The text content to encode
        generate_type: Type of code to generate (one of codes.KINDS)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not content:
        return False, "Missing 'content' parameter"

    if generate_type not in config.ALLOWED_TYPES:
        return False, f"Invalid type. Must be one of: {', '.join(config.ALLOWED_TYPES)}"

    # Validate barcode content (Code128 supports ASCII characters 0-127)
    if generate_type == "barcode":
        if len(content) > config.BARCODE_MAX_LENGTH:
            return (
                False,
                f"Barcode content exceeds maximum length of {config.BARCODE_MAX_LENGTH} characters",
            )

        # Check if all characters are printable ASCII (Code128 supports ASCII 0-127)
        if not all(0 <= ord(char) < 128 for char in content):
            return False, "Barcode content must contain only ASCII characters"
    elif generate_type != "ean13":  # EAN-13 is checked digit by digit in codes.py
        if len(content) > config.MAX_CONTENT_LENGTH:
            return (
                False,
                f"Content exceeds maximum length of {config.MAX_CONTENT_LENGTH} characters",
            )

    return True, ""


# API responses never need to load anything or be framed
API_CSP = "default-src 'none'; frame-ancestors 'none'"
# The docs page loads only same-origin assets (no inline script). Swagger UI sets inline
# styles, uses data: icons, shows "Try it out" images as blob: URLs, and calls the API on
# the same origin.
DOCS_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)


def add_security_headers(response: Response, csp: str = API_CSP) -> Response:
    """
    Add security headers to HTTP response.

    Args:
        response: Flask Response object
        csp: Content-Security-Policy to send

    Returns:
        Response object with security headers added
    """
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    # The legacy XSS auditor is removed from browsers and could be abused; "0" disables it
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = csp
    return response


@app.route("/health")
@limiter.exempt
def health_check() -> Tuple[str, int]:
    """Health check endpoint for monitoring and container orchestration."""
    return "OK", 200


@app.route("/metrics")
@limiter.exempt
def metrics() -> Response:
    """Report service status, version and effective limits."""
    return jsonify(
        {
            "status": "healthy",
            "version": __version__,
            "config": {
                "max_content_length": config.MAX_CONTENT_LENGTH,
                "rate_limit": config.RATE_LIMIT if config.RATE_LIMIT_ENABLED else "disabled",
                "allowed_types": list(config.ALLOWED_TYPES),
            },
        }
    )


def resolve_content(generate_type: str, args: Mapping[str, str]) -> str:
    """Return the text to encode: `content`, or the GS1 data for GS1 types. Raises CodeError."""
    if generate_type in GS1_TYPES:
        item = gs1.build(args)
        if generate_type == "gs1qr":
            return item.digital_link(args.get("domain") or gs1.DEFAULT_RESOLVER)
        return item.element_string()
    content = (args.get("content") or "").strip()
    is_valid, error_msg = validate_input(content, generate_type)
    if not is_valid:
        raise codes.CodeError(error_msg)
    return content


def render_type(generate_type: str, content: str, options: codes.RenderOptions):
    """Render with the right renderer for an API type; returns (bytes, mimetype)."""
    if generate_type == "gs1datamatrix":
        return codes.render_gs1_datamatrix(content, options)
    return codes.render("qrcode" if generate_type == "gs1qr" else generate_type, content, options)


@app.route("/generate")
@limiter.limit(lambda: config.GENERATE_RATE_LIMIT)
def generate_code() -> Union[Response, Tuple[str, int]]:
    """
    Generate a code image from the query parameters (`content` or GS1 fields, `type`, options).

    See openapi.json for the full parameter and response contract.
    """
    generate_type = request.args.get("type", "qrcode").lower()
    try:
        content = resolve_content(generate_type, request.args)
        options = codes.parse_options(request.args)
        logger.info(f"Generating {generate_type} (length={len(content)}, format={options.format})")
        data, mimetype = render_type(generate_type, content, options)
    except codes.CodeError as e:
        logger.warning(f"Invalid input for {generate_type}: {e}")
        return str(e), 400
    except Exception as e:
        logger.error(f"{generate_type} generation failed: {type(e).__name__}", exc_info=True)
        return f"{'QR code' if generate_type == 'qrcode' else 'Barcode'} generation error", 500

    response = send_file(io.BytesIO(data), mimetype=mimetype)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    logger.info(f"Successfully generated {generate_type}")
    return response


@app.route("/gs1/digital-link")
@limiter.limit(lambda: config.GENERATE_RATE_LIMIT)
def gs1_digital_link() -> Union[Response, Tuple[Response, int]]:
    """Validate GS1 fields and return the Digital Link URI and element string as JSON."""
    try:
        item = gs1.build(request.args)
        uri = item.digital_link(request.args.get("domain") or gs1.DEFAULT_RESOLVER)
    except codes.CodeError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(
        {
            "uri": uri,
            "element_string": item.element_string(),
            "ais": item.ais(),
        }
    )


def sign_authorized() -> bool:
    """Bearer API key from the Authorization header, checked against the configured hashes."""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    hashes = [h for h in config.SIGNING_API_KEY_HASHES.split(",") if h.strip()]
    return scheme.lower() == "bearer" and bool(token) and signing.api_key_matches(token, hashes)


@app.route("/sign", methods=["POST"])
@limiter.limit(lambda: config.SIGN_RATE_LIMIT)
def sign() -> Union[Response, Tuple[Response, int]]:
    """Sign an https URL or GS1 fields (as a Digital Link); requires a Bearer API key."""
    if not sign_authorized():
        logger.warning("Rejected /sign request: missing or invalid API key")
        response = jsonify({"error": "Missing or invalid API key"})
        response.headers["WWW-Authenticate"] = "Bearer"
        return response, 401
    if not keyring.can_sign:
        return jsonify({"error": "Signing is not configured on this server"}), 503
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Body must be a JSON object"}), 400
    fields = {k: str(v) for k, v in body.items() if isinstance(v, (str, int))}
    try:
        if "url" in fields:
            url = fields["url"]
        else:
            url = gs1.build(fields).digital_link(fields.get("domain") or gs1.DEFAULT_RESOLVER)
        signed = keyring.sign(url)
    except codes.CodeError as e:
        return jsonify({"error": str(e)}), 400
    logger.info("Signed a URL")
    return jsonify({"url": signed, "kid": keyring.signing_kid})


@app.route("/verify")
@limiter.limit(lambda: config.GENERATE_RATE_LIMIT)
def verify() -> Union[Response, Tuple[Response, int]]:
    """Verify a scanned signed URL (`u`); also decodes its GS1 data when it is a Digital Link."""
    scanned = request.args.get("u", "")
    if not scanned:
        return jsonify({"error": "Missing 'u' parameter"}), 400
    result = keyring.verify(scanned)
    gs1_data = None
    if result.valid and result.url:
        try:
            gs1_data = gs1.parse_digital_link(result.url).ais()
        except codes.CodeError:
            pass  # a valid signature on a non-GS1 URL
    return jsonify(
        {
            "valid": result.valid,
            "reason": result.reason,
            "kid": result.kid,
            "url": result.url,
            "gs1": gs1_data,
        }
    )


@app.route("/.well-known/qr-signing-keys.json")
def signing_keys() -> Response:
    """Public keys for offline verification (JWKS, Ed25519)."""
    response = jsonify(keyring.jwks())
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.route("/apispec.json")
def apispec() -> Response:
    """Serve the OpenAPI spec with servers for the configured host and schemes."""
    if not config.SWAGGER_HOST:
        # Without servers Swagger UI calls back on the page's own scheme and host, so it never
        # offers https on a plain-http port (or http behind a TLS-terminating proxy).
        return jsonify(OPENAPI_SPEC)
    servers = [{"url": f"{s}://{config.SWAGGER_HOST}"} for s in config.SWAGGER_SCHEMES]
    return jsonify(dict(OPENAPI_SPEC, servers=servers))


@app.route("/docs")
@app.route("/docs/")
def docs() -> Response:
    """Serve the Swagger UI page."""
    return app.send_static_file("docs/index.html")


@app.route("/")
def index() -> WerkzeugResponse:
    """Send visitors of the bare domain to the API docs."""
    return redirect("/docs", code=302)


@app.after_request
def after_request(response: Response) -> Response:
    """
    Add CORS headers and security headers to all responses.

    Args:
        response: Flask Response object

    Returns:
        Response object with headers added
    """
    # Public, read-only GET API without cookies or auth, so any origin may embed the images
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    csp = DOCS_CSP if request.path in ("/docs", "/docs/") else API_CSP
    return add_security_headers(response, csp)


@app.errorhandler(404)
def not_found(_error) -> Tuple[str, int]:
    """Handle 404 errors."""
    logger.warning(f"404 error: {request.path}")
    return "Endpoint not found. Use /generate, /health, /metrics or /docs", 404


@app.errorhandler(429)
def ratelimit_handler(_error) -> Tuple[str, int]:
    """Handle rate limit errors."""
    logger.warning(f"Rate limit exceeded for {get_remote_address()}")
    return "Rate limit exceeded. Please try again later.", 429


@app.errorhandler(500)
def internal_error(error) -> Tuple[str, int]:
    """Handle 500 errors."""
    logger.error(f"500 error: {str(error)}")
    return "Internal server error", 500


if __name__ == "__main__":
    port = config.DEFAULT_PORT
    debug = config.DEBUG

    logger.info(f"Starting QR/Barcode service on port {port} (debug={debug})")
    logger.info(f"API documentation available at http://localhost:{port}/docs")
    # Binding all interfaces is intended: the service runs inside a container
    app.run(host="0.0.0.0", port=port, debug=debug)  # nosec B104

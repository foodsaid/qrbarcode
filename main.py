"""
QR Code and Barcode Generation Service

A Flask-based microservice for generating QR codes and barcodes.
"""

import io
import logging
import os
from dataclasses import dataclass, field
from typing import Tuple, Union

import barcode
import qrcode
from barcode.writer import ImageWriter
from flasgger import Swagger
from flask import Flask, Response, jsonify, request, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

__version__ = "0.1.0"


@dataclass
class Config:
    """Application configuration."""

    MAX_CONTENT_LENGTH: int = 1000
    BARCODE_MAX_LENGTH: int = 64
    DEFAULT_PORT: int = 8080
    ALLOWED_TYPES: set = field(default_factory=lambda: {"qrcode", "barcode"})
    QR_BORDER_SIZE: int = 1
    QR_BOX_SIZE: int = 10
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT: str = "100 per minute"  # Global default per client IP
    GENERATE_RATE_LIMIT: str = "50 per minute"  # Per client IP on /generate
    DEBUG: bool = False
    # Barcode options - reduce margins to save paper
    BARCODE_MODULE_WIDTH: float = 0.3  # Width of one barcode module in mm
    BARCODE_MODULE_HEIGHT: float = 15.0  # Height of barcode bars in mm
    BARCODE_QUIET_ZONE: float = 3.0  # Minimal quiet zone on left/right in mm
    BARCODE_FONT_SIZE: int = 12  # Font size for text below barcode
    BARCODE_TEXT_DISTANCE: float = 6.0  # Distance between barcode and text in mm
    BARCODE_MARGIN_TOP: float = 3.0  # Top margin in mm
    # Swagger configuration (empty host = use the host the docs page was served from)
    SWAGGER_HOST: str = ""
    SWAGGER_SCHEMES: list = field(default_factory=lambda: ["http", "https"])

    def __post_init__(self):
        """Load configuration from environment."""
        self.DEBUG = os.environ.get("DEBUG", "False").lower() == "true"
        self.DEFAULT_PORT = int(os.environ.get("PORT", self.DEFAULT_PORT))
        self.RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true"
        self.RATE_LIMIT = os.environ.get("RATE_LIMIT", self.RATE_LIMIT)
        self.GENERATE_RATE_LIMIT = os.environ.get("GENERATE_RATE_LIMIT", self.GENERATE_RATE_LIMIT)
        self.SWAGGER_HOST = os.environ.get("SWAGGER_HOST", self.SWAGGER_HOST)
        schemes_env = os.environ.get("SWAGGER_SCHEMES")
        if schemes_env:
            self.SWAGGER_SCHEMES = [s.strip() for s in schemes_env.split(",") if s.strip()]


# Initialize configuration
config = Config()

# Initialize Flask app
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max request size
app.config["RATELIMIT_ENABLED"] = config.RATE_LIMIT_ENABLED

# Initialize rate limiter (in-memory: limits are per gunicorn worker)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[config.RATE_LIMIT],
    storage_uri="memory://",
)

# Swagger configuration
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/docs",
    # flasgger 0.9.7.1 bundles swagger-ui 3.28.0 / jQuery 2.2.4 (known XSS/spoofing CVEs);
    # serve patched local copies from static/vendor instead.
    "swagger_ui_bundle_js": "/static/vendor/swagger-ui-5.33.1/swagger-ui-bundle.js",
    "swagger_ui_standalone_preset_js": "/static/vendor/swagger-ui-5.33.1/swagger-ui-standalone-preset.js",
    "swagger_ui_css": "/static/vendor/swagger-ui-5.33.1/swagger-ui.css",
    "jquery_js": "/static/vendor/jquery-3.7.1/jquery.min.js",
    # Without this flasgger renders `let auth_config = None;` and the docs page throws.
    "auth": {},
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "QR/Barcode Generation API",
        "description": "A lightweight microservice for generating QR codes and barcodes",
        "contact": {"name": "foodsaid", "url": "https://github.com/foodsaid/qrbarcode"},
        "version": __version__,
    },
    "basePath": "/",
    "schemes": config.SWAGGER_SCHEMES,
    "tags": [
        {"name": "generate", "description": "Code generation endpoints"},
        {"name": "health", "description": "Health check endpoints"},
    ],
}

if config.SWAGGER_HOST:
    swagger_template["host"] = config.SWAGGER_HOST

swagger = Swagger(app, config=swagger_config, template=swagger_template)

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
        generate_type: Type of code to generate ('qrcode' or 'barcode')

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
    else:
        # QR code validation
        if len(content) > config.MAX_CONTENT_LENGTH:
            return (
                False,
                f"Content exceeds maximum length of {config.MAX_CONTENT_LENGTH} characters",
            )

    return True, ""


def add_security_headers(response: Response) -> Response:
    """
    Add security headers to HTTP response.

    Args:
        response: Flask Response object

    Returns:
        Response object with security headers added
    """
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.route("/health")
@limiter.exempt
def health_check() -> Tuple[str, int]:
    """
    Health check endpoint for monitoring and container orchestration.
    ---
    tags:
      - health
    responses:
      200:
        description: Service is healthy
        schema:
          type: string
          example: OK
    """
    return "OK", 200


@app.route("/metrics")
@limiter.exempt
def metrics() -> Response:
    """
    Basic metrics endpoint for monitoring.
    ---
    tags:
      - health
    responses:
      200:
        description: Service metrics
        schema:
          type: object
          properties:
            status:
              type: string
              example: healthy
            version:
              type: string
              example: 0.1.0
            config:
              type: object
              properties:
                max_content_length:
                  type: integer
                  example: 1000
                rate_limit:
                  type: string
                  example: "100 per minute"
    """
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


@app.route("/generate")
@limiter.limit(lambda: config.GENERATE_RATE_LIMIT)
def generate_code() -> Union[Response, Tuple[str, int]]:
    """
    Generate QR code or barcode based on user input.
    ---
    tags:
      - generate
    parameters:
      - name: content
        in: query
        type: string
        required: true
        description: |
          Text content to encode.
          - QR code: max 1000 chars, supports any text
          - Barcode: max 64 chars, ASCII characters only (supports special chars like -,.,@,#,etc)
        example: "Hello World"
      - name: type
        in: query
        type: string
        required: false
        description: Type of code to generate
        enum: [qrcode, barcode]
        default: qrcode
        example: qrcode
    responses:
      200:
        description: Successfully generated image
        content:
          image/png:
            schema:
              type: string
              format: binary
      400:
        description: Invalid input parameters
        schema:
          type: string
          example: "Missing 'content' parameter"
      429:
        description: Rate limit exceeded
        schema:
          type: string
          example: "Rate limit exceeded"
      500:
        description: Internal server error
        schema:
          type: string
          example: "Internal server error"
    """
    try:
        # Get and validate parameters
        content = request.args.get("content", "").strip()
        generate_type = request.args.get("type", "qrcode").lower()

        # Validate input
        is_valid, error_msg = validate_input(content, generate_type)
        if not is_valid:
            logger.warning(
                f"Invalid input: {error_msg} - length={len(content)}, type={generate_type}"
            )
            return error_msg, 400

        # Create image buffer
        buf = io.BytesIO()

        if generate_type == "barcode":
            # Generate Barcode (Code128)
            logger.info(f"Generating barcode (length={len(content)})")
            try:
                code128 = barcode.get("code128", content, writer=ImageWriter())
                code128.write(
                    buf,
                    options={
                        "module_width": config.BARCODE_MODULE_WIDTH,
                        "module_height": config.BARCODE_MODULE_HEIGHT,
                        "quiet_zone": config.BARCODE_QUIET_ZONE,
                        "font_size": config.BARCODE_FONT_SIZE,
                        "text_distance": config.BARCODE_TEXT_DISTANCE,
                        "margin_top": config.BARCODE_MARGIN_TOP,
                    },
                )
            except Exception as e:
                logger.error(f"Barcode generation failed: {type(e).__name__}")
                return f"Barcode generation error: {str(e)}", 500
        else:
            # Generate QR code
            logger.info(f"Generating QR code (length={len(content)})")
            try:
                qr = qrcode.QRCode(
                    border=config.QR_BORDER_SIZE,
                    box_size=config.QR_BOX_SIZE,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                )
                qr.add_data(content)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                img.save(buf, format="PNG")
            except Exception as e:
                logger.error(f"QR code generation failed: {type(e).__name__}")
                return f"QR code generation error: {str(e)}", 500

        # Prepare response
        buf.seek(0)
        response = send_file(buf, mimetype="image/png")
        response = add_security_headers(response)

        logger.info(f"Successfully generated {generate_type}")
        return response

    except Exception as e:
        logger.error(f"Unexpected error in generate_code: {str(e)}", exc_info=True)
        return "Internal server error", 500


@app.after_request
def after_request(response: Response) -> Response:
    """
    Add CORS headers and security headers to all responses.

    Args:
        response: Flask Response object

    Returns:
        Response object with headers added
    """
    # CORS headers (adjust origins for production)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


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

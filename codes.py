"""
Code rendering, independent of Flask so the HTTP API and the MCP server share it.

`render(kind, content, options)` returns `(bytes, mimetype)` for:

- ``qrcode``     QR code (qrcode library)
- ``barcode``    Code 128 (python-barcode)
- ``datamatrix`` Data Matrix (zxing-cpp)
- ``ean13``      EAN-13 (zxing-cpp)

With default options, ``qrcode`` and ``barcode`` produce exactly the images the service
has always produced, so existing report formulas keep printing the same output.
"""

import io
import re
from dataclasses import dataclass
from html import escape
from typing import Mapping, Optional, Tuple

import barcode
import qrcode
import qrcode.image.svg
import zxingcpp
from barcode.writer import ImageWriter, SVGWriter
from PIL import Image

KINDS = ("qrcode", "barcode", "datamatrix", "ean13")
FORMATS = {"png": "image/png", "svg": "image/svg+xml"}
EC_LEVELS = {
    "L": qrcode.constants.ERROR_CORRECT_L,
    "M": qrcode.constants.ERROR_CORRECT_M,
    "Q": qrcode.constants.ERROR_CORRECT_Q,
    "H": qrcode.constants.ERROR_CORRECT_H,
}

SCALE_RANGE = (1, 40)
SIZE_RANGE = (64, 4096)
BORDER_RANGE = (0, 10)

# Defaults (pixels per module, quiet zone in modules)
QR_SCALE, QR_BORDER = 10, 1
DATAMATRIX_SCALE, DATAMATRIX_BORDER = 10, 1  # ISO/IEC 16022 minimum quiet zone: 1 module
EAN13_SCALE = 4

# Code 128 layout, in mm at BARCODE_DPI (python-barcode's own units)
BARCODE_DPI = 300
BARCODE_MODULE_WIDTH = 0.3
BARCODE_MODULE_HEIGHT = 15.0
BARCODE_QUIET_ZONE = 3.0
BARCODE_FONT_SIZE = 12
BARCODE_TEXT_DISTANCE = 6.0
BARCODE_MARGIN_TOP = 3.0


class CodeError(ValueError):
    """Invalid input or options; the message is safe to show to the client."""


@dataclass(frozen=True)
class RenderOptions:
    """Output options shared by all code types. ``None`` means the type's default."""

    format: str = "png"
    scale: Optional[int] = None
    size: Optional[int] = None
    border: Optional[int] = None
    ec: str = "L"
    text: bool = True


def _int_option(args: Mapping[str, str], name: str, bounds: Tuple[int, int]) -> Optional[int]:
    """Parse an optional integer option within inclusive bounds."""
    raw = args.get(name)
    if raw is None or raw == "":
        return None
    try:
        value = int(raw)
    except ValueError:
        raise CodeError(f"'{name}' must be an integer") from None
    low, high = bounds
    if not low <= value <= high:
        raise CodeError(f"'{name}' must be between {low} and {high}")
    return value


def parse_options(args: Mapping[str, str]) -> RenderOptions:
    """Build RenderOptions from query parameters, rejecting invalid values."""
    fmt = (args.get("format") or "png").lower()
    if fmt not in FORMATS:
        raise CodeError(f"Invalid format. Must be one of: {', '.join(FORMATS)}")
    scale = _int_option(args, "scale", SCALE_RANGE)
    size = _int_option(args, "size", SIZE_RANGE)
    if scale is not None and size is not None:
        raise CodeError("Use either 'scale' or 'size', not both")
    ec = (args.get("ec") or "L").upper()
    if ec not in EC_LEVELS:
        raise CodeError("Invalid ec. Must be one of: L, M, Q, H")
    text_raw = (args.get("text") or "true").lower()
    if text_raw not in ("true", "false", "1", "0"):
        raise CodeError("'text' must be true or false")
    return RenderOptions(
        format=fmt,
        scale=scale,
        size=size,
        border=_int_option(args, "border", BORDER_RANGE),
        ec=ec,
        text=text_raw in ("true", "1"),
    )


def gs1_check_digit(digits: str) -> int:
    """GS1 mod-10 check digit for the digits preceding it (GTIN, EAN, GLN ...)."""
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits)))
    return (10 - total % 10) % 10


def _fit_scale(size: int, modules: int) -> int:
    """Largest whole pixels-per-module so that `modules` fit in `size` pixels."""
    scale = size // modules
    if scale < 1:
        raise CodeError(f"'size' is too small for this content; minimum is {modules}")
    return scale


def _matrix_png(matrix: Image.Image, scale: int, border: int) -> bytes:
    """Scale a 1-pixel-per-module matrix and add a white quiet zone."""
    width, height = matrix.size
    canvas = Image.new("L", (width + 2 * border, height + 2 * border), 255)
    canvas.paste(matrix, (border, border))
    canvas = canvas.resize((canvas.width * scale, canvas.height * scale), Image.Resampling.NEAREST)
    buf = io.BytesIO()
    canvas.convert("1").save(buf, format="PNG")
    return buf.getvalue()


def _matrix_svg(matrix: Image.Image, scale: int, border: int, title: str) -> bytes:
    """Vector SVG of a 1-pixel-per-module matrix: one path, one unit per module."""
    width, height = matrix.size
    pixels = matrix.tobytes()  # one byte per module, row-major; 0 = dark
    runs = []
    for y in range(height):
        row = pixels[y * width : (y + 1) * width]
        x = 0
        while x < width:
            if row[x] == 0:
                start = x
                while x < width and row[x] == 0:
                    x += 1
                runs.append(f"M{start + border} {y + border}h{x - start}v1h{start - x}z")
            else:
                x += 1
    total_w, total_h = width + 2 * border, height + 2 * border
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w * scale}" '
        f'height="{total_h * scale}" viewBox="0 0 {total_w} {total_h}" '
        'shape-rendering="crispEdges">'
        f"<title>{escape(title)}</title>"
        f'<rect width="{total_w}" height="{total_h}" fill="#fff"/>'
        f'<path fill="#000" d="{"".join(runs)}"/></svg>\n'
    ).encode()


def _zxing_matrix(content: str, fmt, **kwargs) -> Image.Image:
    """Create a symbol with zxing-cpp and return it at one pixel per module, no quiet zone."""
    try:
        symbol = zxingcpp.create_barcode(content, fmt, **kwargs)
    except ValueError as e:
        raise CodeError(f"Cannot encode content: {e}") from None
    raw = symbol.to_image(scale=1, add_quiet_zones=False)
    height, width = raw.shape
    return Image.frombytes("L", (width, height), bytes(memoryview(raw)))


def _render_qrcode(content: str, opts: RenderOptions) -> bytes:
    border = QR_BORDER if opts.border is None else opts.border
    qr = qrcode.QRCode(border=border, error_correction=EC_LEVELS[opts.ec])
    qr.add_data(content)
    try:
        qr.make(fit=True)
    # qrcode 8 raises ValueError("Invalid version ...") when no version up to 40 fits
    except (qrcode.exceptions.DataOverflowError, ValueError):
        raise CodeError("Content is too long for a QR code at this ec level") from None
    if opts.size is not None:
        qr.box_size = _fit_scale(opts.size, qr.modules_count + 2 * border)
    else:
        qr.box_size = opts.scale or QR_SCALE
    buf = io.BytesIO()
    if opts.format == "svg":
        qr.make_image(image_factory=qrcode.image.svg.SvgPathImage).save(buf)
    else:
        qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
    return buf.getvalue()


def _render_code128(content: str, opts: RenderOptions) -> bytes:
    module_width = BARCODE_MODULE_WIDTH
    px_per_module = opts.scale
    if opts.size is not None:
        modules = len(barcode.get("code128", content).build()[0])
        quiet_px = BARCODE_QUIET_ZONE * BARCODE_DPI / 25.4
        px_per_module = _fit_scale(int(opts.size - 2 * quiet_px), modules)
    if px_per_module is not None:
        module_width = px_per_module * 25.4 / BARCODE_DPI
    quiet_zone = BARCODE_QUIET_ZONE if opts.border is None else opts.border * module_width
    writer = SVGWriter() if opts.format == "svg" else ImageWriter()
    buf = io.BytesIO()
    barcode.get("code128", content, writer=writer).write(
        buf,
        options={
            "module_width": module_width,
            "module_height": BARCODE_MODULE_HEIGHT,
            "quiet_zone": quiet_zone,
            "font_size": BARCODE_FONT_SIZE,
            "text_distance": BARCODE_TEXT_DISTANCE,
            "margin_top": BARCODE_MARGIN_TOP,
            "write_text": opts.text,
            "dpi": BARCODE_DPI,
        },
    )
    return buf.getvalue()


def _render_datamatrix(content: str, opts: RenderOptions, gs1: bool = False) -> bytes:
    matrix = _zxing_matrix(content, zxingcpp.BarcodeFormat.DataMatrix, gs1=gs1)
    border = DATAMATRIX_BORDER if opts.border is None else opts.border
    if opts.size is not None:
        scale = _fit_scale(opts.size, max(matrix.size) + 2 * border)
    else:
        scale = opts.scale or DATAMATRIX_SCALE
    if opts.format == "svg":
        return _matrix_svg(matrix, scale, border, "GS1 Data Matrix" if gs1 else "Data Matrix")
    return _matrix_png(matrix, scale, border)


def normalize_ean13(content: str) -> str:
    """Return the 13-digit EAN for 12 digits (check digit added) or 13 (check digit verified)."""
    if not content.isascii() or not content.isdigit() or len(content) not in (12, 13):
        raise CodeError("EAN-13 content must be 12 or 13 digits")
    check = gs1_check_digit(content[:12])
    if len(content) == 13 and int(content[12]) != check:
        raise CodeError(f"Invalid EAN-13 check digit '{content[12]}', expected '{check}'")
    return content[:12] + str(check)


def _render_ean13(content: str, opts: RenderOptions) -> bytes:
    if opts.border is not None:
        raise CodeError("'border' is fixed by the EAN-13 specification")
    try:
        symbol = zxingcpp.create_barcode(normalize_ean13(content), zxingcpp.BarcodeFormat.EAN13)
    except ValueError as e:
        raise CodeError(f"Cannot encode content: {e}") from None
    if opts.size is not None:
        # EAN-13 is 113 modules wide including its specified quiet zones
        scale = _fit_scale(opts.size, 113)
    else:
        scale = opts.scale or EAN13_SCALE
    if opts.format == "svg":
        return symbol.to_svg(scale=scale, add_hrt=opts.text, add_quiet_zones=True).encode()
    raw = symbol.to_image(scale=scale, add_hrt=opts.text, add_quiet_zones=True)
    height, width = raw.shape
    buf = io.BytesIO()
    Image.frombytes("L", (width, height), bytes(memoryview(raw))).save(buf, format="PNG")
    return buf.getvalue()


def render_gs1_datamatrix(element_string: str, opts: RenderOptions) -> Tuple[bytes, str]:
    """GS1 Data Matrix (FNC1, ]d2) from a parenthesised element string like (01)...(10)..."""
    values = re.findall(r"\(\d{2}\)([^(]*)", element_string)
    if element_string.count("(") != len(values) or any(")" in v for v in values):
        raise CodeError(
            "Parentheses in batch/serial are not supported in GS1 Data Matrix; use gs1qr"
        )
    return _render_datamatrix(element_string, opts, gs1=True), FORMATS[opts.format]


def render(kind: str, content: str, opts: RenderOptions) -> Tuple[bytes, str]:
    """Render `content` as `kind`; returns (image bytes, mimetype). Raises CodeError."""
    if kind == "qrcode":
        data = _render_qrcode(content, opts)
    elif kind == "barcode":
        data = _render_code128(content, opts)
    elif kind == "datamatrix":
        data = _render_datamatrix(content, opts)
    elif kind == "ean13":
        data = _render_ean13(content, opts)
    else:
        raise CodeError(f"Invalid type. Must be one of: {', '.join(KINDS)}")
    return data, FORMATS[opts.format]

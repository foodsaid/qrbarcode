"""
MCP server (stdio) exposing the code generator to AI assistants such as Claude.

Runs locally, needs no network and no Flask; it calls codes.py, gs1.py and signing.py
directly. Signing is deliberately not exposed: the private key stays on the HTTP server.

    pip install --require-hashes -r requirements-mcp.txt
    python qr_mcp.py

Verification keys (optional), first match wins:
    QR_SIGNING_JWKS            path or https URL of a JWKS (/.well-known/qr-signing-keys.json)
    SIGNING_PUBLIC_KEY_FILES   comma-separated PEM public keys
"""

import json
import os
import urllib.request
from contextlib import contextmanager
from typing import Dict, Iterator, Literal, Optional, TypedDict, Union

from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

import codes
import gs1
import signing

READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


class DigitalLink(TypedDict):
    """Result of build_gs1_digital_link."""

    uri: str
    element_string: str
    ais: Dict[str, str]


class Verification(TypedDict):
    """Result of verify_signed_code."""

    valid: bool
    reason: str
    kid: Optional[str]
    url: Optional[str]
    gs1: Optional[Dict[str, str]]


server = MCPServer(
    name="qrbarcode",
    instructions=(
        "Generates QR codes, Code 128 barcodes, Data Matrix, EAN-13 and GS1 codes as PNG images "
        "or SVG text, builds and validates GS1 Digital Links, and verifies signed codes. "
        "Everything runs locally; nothing is uploaded."
    ),
)


@contextmanager
def tool_errors() -> Iterator[None]:
    """Report invalid input to the model as a readable tool error it can correct and retry."""
    try:
        yield
    except codes.CodeError as e:
        raise ToolError(e.public_message) from None


def load_keyring() -> signing.KeyRing:
    """Public keys for verify_signed_code, from QR_SIGNING_JWKS or SIGNING_PUBLIC_KEY_FILES."""
    source = os.environ.get("QR_SIGNING_JWKS", "").strip()
    if source.startswith("https://"):
        with urllib.request.urlopen(source, timeout=10) as response:  # nosec B310 - https only
            return signing.KeyRing.from_jwks(json.load(response))
    if source:
        with open(source, encoding="utf-8") as handle:
            return signing.KeyRing.from_jwks(json.load(handle))
    return signing.KeyRing.from_files("", os.environ.get("SIGNING_PUBLIC_KEY_FILES", ""))


def _image(data: bytes, mimetype: str) -> Union[Image, str]:
    """PNG as MCP image content; SVG as text so it can be saved or embedded directly."""
    return data.decode() if mimetype == "image/svg+xml" else Image(data=data, format="png")


def _options(
    format: str,
    scale: Optional[int],
    size: Optional[int],
    border: Optional[int],
    ec: str,
    text: bool,
) -> codes.RenderOptions:
    """Validate rendering options with the same rules as the HTTP API."""
    raw = {"format": format, "ec": ec, "text": "true" if text else "false"}
    numbers = (("scale", scale), ("size", size), ("border", border))
    raw.update({k: str(v) for k, v in numbers if v is not None})
    return codes.parse_options(raw)


@server.tool(annotations=READ_ONLY)
def generate_code(
    content: str,
    type: Literal["qrcode", "barcode", "datamatrix", "ean13"] = "qrcode",
    format: Literal["png", "svg"] = "png",
    scale: Optional[int] = None,
    size: Optional[int] = None,
    border: Optional[int] = None,
    ec: Literal["L", "M", "Q", "H"] = "L",
    text: bool = True,
) -> Union[Image, str]:
    """Render text as a QR code, Code 128 barcode, Data Matrix or EAN-13.

    Use `qrcode` (default) or `datamatrix` for any text including Chinese and URLs;
    `barcode` (Code 128) for ASCII up to 64 characters such as order numbers;
    `ean13` for 12 digits (check digit added) or 13 digits (check digit verified).
    For GTIN + batch/expiry use generate_gs1_code instead.

    Options: `format` png returns an image, svg returns SVG markup for printing at any size.
    `scale` is pixels per module (1-40) or `size` a target width in pixels (64-4096), not both.
    `border` is the quiet zone in modules (not for ean13). `ec` is QR error correction
    (M or Q for worn packaging). `text` shows digits under 1D codes.
    """
    with tool_errors():
        options = _options(format, scale, size, border, ec, text)
        data, mimetype = codes.render(type, content, options)
    return _image(data, mimetype)


@server.tool(annotations=READ_ONLY)
def generate_gs1_code(
    gtin: str,
    batch: Optional[str] = None,
    serial: Optional[str] = None,
    expiry: Optional[str] = None,
    best_before: Optional[str] = None,
    prod_date: Optional[str] = None,
    pack_date: Optional[str] = None,
    symbol: Literal["qrcode", "datamatrix"] = "qrcode",
    domain: str = gs1.DEFAULT_RESOLVER,
    format: Literal["png", "svg"] = "png",
    scale: Optional[int] = None,
    size: Optional[int] = None,
    ec: Literal["L", "M", "Q", "H"] = "L",
) -> Union[Image, str]:
    """Render a GS1 trade item code: a GS1 Digital Link QR code or a GS1 Data Matrix.

    `gtin` is a GTIN-8/12/13/14 whose check digit must be correct. `batch` (AI 10) and
    `serial` (AI 21) are up to 20 characters of the GS1 character set (letters, digits and
    common symbols, no spaces). Dates accept YYMMDD or YYYY-MM-DD; a day of 00 means end of
    month. `symbol` qrcode (default) encodes a Digital Link URL on `domain` that phones and
    2D retail scanners read; datamatrix encodes the GS1 element string with FNC1, common in
    pharma and fresh food. Call build_gs1_digital_link first to check the data as text.
    """
    fields = {
        "gtin": gtin,
        "batch": batch,
        "serial": serial,
        "expiry": expiry,
        "best_before": best_before,
        "prod_date": prod_date,
        "pack_date": pack_date,
    }
    with tool_errors():
        item = gs1.build({k: v for k, v in fields.items() if v})
        options = _options(format, scale, size, None, ec, True)
        if symbol == "datamatrix":
            data, mimetype = codes.render_gs1_datamatrix(item.element_string(), options)
        else:
            data, mimetype = codes.render("qrcode", item.digital_link(domain), options)
    return _image(data, mimetype)


@server.tool(annotations=READ_ONLY)
def build_gs1_digital_link(
    gtin: str,
    batch: Optional[str] = None,
    serial: Optional[str] = None,
    expiry: Optional[str] = None,
    best_before: Optional[str] = None,
    prod_date: Optional[str] = None,
    pack_date: Optional[str] = None,
    domain: str = gs1.DEFAULT_RESOLVER,
) -> DigitalLink:
    """Validate GS1 data and return its Digital Link URI, element string and AIs as text.

    Same fields and rules as generate_gs1_code. Errors name the field and the problem,
    e.g. the expected GTIN check digit, so they can be fixed and retried.
    """
    fields = {
        "gtin": gtin,
        "batch": batch,
        "serial": serial,
        "expiry": expiry,
        "best_before": best_before,
        "prod_date": prod_date,
        "pack_date": pack_date,
    }
    with tool_errors():
        item = gs1.build({k: v for k, v in fields.items() if v})
        return {
            "uri": item.digital_link(domain),
            "element_string": item.element_string(),
            "ais": item.ais(),
        }


@server.tool(annotations=READ_ONLY)
def verify_signed_code(url: str) -> Verification:
    """Check the signature of a scanned code URL ending in `&kid=...&sig=...`.

    Returns `valid`, a `reason` (ok, unknown key id, signature does not match, not a signed
    URL), the key id, the URL without the signature, and its GS1 AIs when it is a valid
    GS1 Digital Link. A valid signature proves the data was issued by the key holder; it
    cannot tell an original label from a photocopy. Needs QR_SIGNING_JWKS or
    SIGNING_PUBLIC_KEY_FILES to be configured, otherwise every code is "unknown key id".
    """
    result = load_keyring().verify(url)
    gs1_data = None
    if result.valid and result.url:
        try:
            gs1_data = gs1.parse_digital_link(result.url).ais()
        except codes.CodeError:
            pass
    return {
        "valid": result.valid,
        "reason": result.reason,
        "kid": result.kid,
        "url": result.url,
        "gs1": gs1_data,
    }


if __name__ == "__main__":
    server.run()

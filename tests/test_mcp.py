"""
Tests for the MCP server (qr_mcp.py): tool calls in-process, and one real stdio session.
"""

import asyncio
import base64
import io
import json
import sys
from pathlib import Path

import pytest
import zxingcpp
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.mcpserver.exceptions import ToolError
from PIL import Image

import qr_mcp
import signing

ROOT = Path(__file__).resolve().parent.parent


def call(name, args):
    """Call a tool in-process and return the CallToolResult."""
    return asyncio.run(qr_mcp.server.call_tool(name, args))


def decode_image_content(result):
    """Decode the first image block of a tool result with zxing-cpp."""
    block = next(c for c in result.content if c.type == "image")
    assert block.mime_type == "image/png"
    return zxingcpp.read_barcode(Image.open(io.BytesIO(base64.b64decode(block.data))))


class TestTools:
    """Tool listing and calls."""

    def test_tools_are_listed_read_only(self):
        """Test the four tools exist and are annotated read-only and idempotent."""
        tools = {t.name: t for t in asyncio.run(qr_mcp.server.list_tools())}
        assert set(tools) == {
            "generate_code",
            "generate_gs1_code",
            "build_gs1_digital_link",
            "verify_signed_code",
        }
        for tool in tools.values():
            assert tool.annotations.read_only_hint and tool.annotations.idempotent_hint
            assert tool.description and len(tool.description) > 80

    def test_generate_code_png(self):
        """Test a QR code comes back as an image that decodes to the content."""
        result = call("generate_code", {"content": "你好 MCP", "ec": "Q"})
        decoded = decode_image_content(result)
        assert decoded.text == "你好 MCP" and decoded.ec_level == "Q"

    def test_generate_code_svg_is_text(self):
        """Test SVG comes back as text."""
        result = call("generate_code", {"content": "LOT-42", "type": "datamatrix", "format": "svg"})
        assert result.content[0].type == "text"
        assert "<svg" in result.content[0].text

    def test_border_zero_is_honoured(self):
        """Test that border=0 is passed through, not treated as 'unset'."""
        with_default = call("generate_code", {"content": "x", "scale": 1})
        without = call("generate_code", {"content": "x", "scale": 1, "border": 0})
        sizes = [
            Image.open(io.BytesIO(base64.b64decode(r.content[0].data))).size[0]
            for r in (with_default, without)
        ]
        assert sizes[1] == sizes[0] - 2

    def test_generate_gs1_qr_and_datamatrix(self):
        """Test both GS1 symbols decode to the GS1 data."""
        args = {"gtin": "9506000134352", "batch": "ABC123", "expiry": "2027-12-31"}
        qr = decode_image_content(call("generate_gs1_code", args))
        assert qr.text == "https://id.gs1.org/01/09506000134352/10/ABC123?17=271231"
        dm = decode_image_content(call("generate_gs1_code", {**args, "symbol": "datamatrix"}))
        assert dm.symbology_identifier == "]d2"
        assert dm.text == "(01)09506000134352(17)271231(10)ABC123"

    def test_build_digital_link_structured(self):
        """Test the Digital Link tool returns structured data."""
        result = call("build_gs1_digital_link", {"gtin": "96385074", "serial": "S1"})
        data = result.structured_content
        assert data["uri"] == "https://id.gs1.org/01/00000096385074/21/S1"
        assert data["ais"] == {"01": "00000096385074", "21": "S1"}

    @pytest.mark.parametrize(
        "name, args, message",
        [
            ("generate_code", {"content": "x", "type": "ean13"}, "12 or 13 digits"),
            ("generate_code", {"content": "x", "scale": 2, "size": 200}, "either"),
            ("generate_gs1_code", {"gtin": "9506000134353"}, "expected '2'"),
            ("build_gs1_digital_link", {"gtin": "9506000134352", "batch": "a b"}, "set 82"),
        ],
    )
    def test_invalid_input_reaches_the_model(self, name, args, message):
        """Test that validation messages are returned to the model, not a generic crash."""
        with pytest.raises(ToolError, match=message):
            call(name, args)


class TestVerify:
    """verify_signed_code with keys from a JWKS file."""

    def test_valid_and_forged(self, tmp_path, monkeypatch):
        """Test a genuine code verifies with GS1 data and a forged batch does not."""
        ring = signing.KeyRing(Ed25519PrivateKey.generate())
        jwks = tmp_path / "keys.json"
        jwks.write_text(json.dumps(ring.jwks()))
        monkeypatch.setenv("QR_SIGNING_JWKS", str(jwks))
        signed = ring.sign("https://id.gs1.org/01/09506000134352/10/ABC123")
        ok = call("verify_signed_code", {"url": signed}).structured_content
        assert ok["valid"] and ok["gs1"] == {"01": "09506000134352", "10": "ABC123"}
        bad = call("verify_signed_code", {"url": signed.replace("ABC123", "XYZ")})
        assert bad.structured_content["reason"] == "signature does not match"

    def test_without_keys_everything_is_unknown(self, monkeypatch):
        """Test the documented behaviour when no keys are configured."""
        monkeypatch.delenv("QR_SIGNING_JWKS", raising=False)
        monkeypatch.delenv("SIGNING_PUBLIC_KEY_FILES", raising=False)
        signed = signing.KeyRing(Ed25519PrivateKey.generate()).sign("https://x.example/a")
        result = call("verify_signed_code", {"url": signed}).structured_content
        assert result["reason"] == "unknown key id"

    def test_jwks_kid_mismatch_is_rejected(self):
        """Test that a JWKS whose kid doesn't match its key is refused."""
        jwks = signing.KeyRing(Ed25519PrivateKey.generate()).jwks()
        jwks["keys"][0]["kid"] = "AAAAAAAAAAA"
        with pytest.raises(ValueError, match="does not match"):
            signing.KeyRing.from_jwks(jwks)


def test_stdio_session_end_to_end():
    """Start qr_mcp.py as a real stdio server, list tools and render a code through MCP."""

    async def session():
        params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "qr_mcp.py")])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                names = {t.name for t in (await client.list_tools()).tools}
                result = await client.call_tool("generate_code", {"content": "stdio"})
                return names, result

    names, result = asyncio.run(asyncio.wait_for(session(), timeout=60))
    assert "generate_code" in names
    assert decode_image_content(result).text == "stdio"

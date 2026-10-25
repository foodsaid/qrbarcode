"""
Tests for gs1.py and the GS1 API, driven by the shared vectors in tests/gs1_vectors.json.
"""

import io
import json
from pathlib import Path

import pytest
import zxingcpp
from PIL import Image

import gs1
from codes import CodeError, RenderOptions, render, render_gs1_datamatrix
from main import app, limiter

VECTORS = json.loads((Path(__file__).parent / "gs1_vectors.json").read_text(encoding="utf-8"))


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config["TESTING"] = True
    limiter.reset()
    with app.test_client() as client:
        yield client


def decode(data: bytes):
    """Decode a PNG with zxing-cpp; fail the test if nothing is found."""
    result = zxingcpp.read_barcode(Image.open(io.BytesIO(data)))
    assert result is not None, "no symbol decoded"
    return result


def build(fields):
    """Build a TradeItem and its URI the way the API does."""
    item = gs1.build(fields)
    return item, item.digital_link(fields.get("domain") or gs1.DEFAULT_RESOLVER)


class TestVectors:
    """Shared vectors: the same expectations any other implementation must meet."""

    @pytest.mark.parametrize("vector", VECTORS["valid"], ids=lambda v: v["name"])
    def test_valid(self, vector):
        """Test URI and element string for each valid vector."""
        item, uri = build(vector["input"])
        assert uri == vector["uri"]
        assert item.element_string() == vector["element_string"]

    @pytest.mark.parametrize("vector", VECTORS["invalid"], ids=lambda v: v["error"])
    def test_invalid(self, vector):
        """Test that each invalid vector is rejected with the expected message."""
        with pytest.raises(CodeError, match=vector["error"]):
            build(vector["input"])

    @pytest.mark.parametrize("vector", VECTORS["valid"], ids=lambda v: v["name"])
    def test_parse_round_trip(self, vector):
        """Test that parsing the generated URI gives back the same item."""
        item, uri = build(vector["input"])
        assert gs1.parse_digital_link(uri) == item


class TestSymbols:
    """Generated symbols decode to the GS1 data."""

    @pytest.mark.parametrize("vector", VECTORS["valid"], ids=lambda v: v["name"])
    def test_gs1_qr_decodes_to_digital_link(self, vector):
        """Test that the QR code carries the Digital Link URI."""
        _, uri = build(vector["input"])
        assert decode(render("qrcode", uri, RenderOptions())[0]).text == uri

    @pytest.mark.parametrize("vector", VECTORS["valid"], ids=lambda v: v["name"])
    def test_gs1_datamatrix_is_real_gs1(self, vector):
        """Test that the Data Matrix is GS1 (]d2, FNC1) and decodes to the element string."""
        item, _ = build(vector["input"])
        result = decode(render_gs1_datamatrix(item.element_string(), RenderOptions())[0])
        assert result.symbology_identifier == "]d2"
        assert result.content_type == zxingcpp.ContentType.GS1
        assert result.text == item.element_string()

    def test_datamatrix_rejects_parentheses_in_values(self):
        """Test that '(' in a batch is refused for Data Matrix (it would be misread as an AI)."""
        item = gs1.build({"gtin": "9506000134352", "batch": "A(1)"})
        with pytest.raises(CodeError, match="use gs1qr"):
            render_gs1_datamatrix(item.element_string(), RenderOptions())

    def test_parentheses_are_fine_in_digital_link(self):
        """Test that the same batch works in a Digital Link, where it is percent-encoded."""
        item = gs1.build({"gtin": "9506000134352", "batch": "A(1)"})
        assert item.digital_link().endswith("/10/A%281%29")
        assert gs1.parse_digital_link(item.digital_link()).batch == "A(1)"


class TestParse:
    """Parsing Digital Link URIs."""

    def test_ignores_unknown_query_keys(self):
        """Test that extra query parameters (e.g. a signature) do not break parsing."""
        uri = "https://id.gs1.org/01/09506000134352/10/ABC?17=271231&sig=abc&kid=k1"
        item = gs1.parse_digital_link(uri)
        assert item.batch == "ABC" and item.dates == {"17": "271231"}

    @pytest.mark.parametrize(
        "uri, message",
        [
            ("https://example.com/products/42", "no /01/"),
            ("https://id.gs1.org/01/09506000134352/10", "pairs"),
            ("https://id.gs1.org/01/09506000134352/99/X", "Unsupported AI"),
            ("https://id.gs1.org/01/09506000134353", "check digit"),
        ],
    )
    def test_rejects_invalid(self, uri, message):
        """Test that malformed or invalid Digital Links are rejected."""
        with pytest.raises(CodeError, match=message):
            gs1.parse_digital_link(uri)


class TestApi:
    """GS1 through HTTP."""

    def test_digital_link_json(self, client):
        """Test /gs1/digital-link returns URI, element string and AIs."""
        response = client.get("/gs1/digital-link?gtin=9506000134352&batch=ABC123&expiry=2027-12-31")
        assert response.status_code == 200
        assert response.get_json() == {
            "uri": "https://id.gs1.org/01/09506000134352/10/ABC123?17=271231",
            "element_string": "(01)09506000134352(17)271231(10)ABC123",
            "ais": {"01": "09506000134352", "10": "ABC123", "17": "271231"},
        }

    def test_digital_link_error_is_json(self, client):
        """Test that validation errors are 400 JSON with the message."""
        response = client.get("/gs1/digital-link?gtin=9506000134353")
        assert response.status_code == 400
        assert "check digit" in response.get_json()["error"]

    def test_generate_gs1qr_with_domain(self, client):
        """Test /generate?type=gs1qr builds the Digital Link on a custom resolver."""
        response = client.get(
            "/generate?type=gs1qr&gtin=9506000134352&batch=B1&domain=https://qr.example.com"
        )
        assert response.status_code == 200
        assert decode(response.data).text == "https://qr.example.com/01/09506000134352/10/B1"

    def test_generate_gs1datamatrix_svg(self, client):
        """Test /generate?type=gs1datamatrix&format=svg returns SVG."""
        response = client.get("/generate?type=gs1datamatrix&gtin=9506000134352&format=svg")
        assert response.status_code == 200
        assert response.mimetype == "image/svg+xml"

    def test_generate_gs1_without_content(self, client):
        """Test that GS1 types need gtin, not content."""
        response = client.get("/generate?type=gs1qr")
        assert response.status_code == 400
        assert b"Missing 'gtin'" in response.data

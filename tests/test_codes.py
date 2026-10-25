"""
Tests for codes.py. Every generated image is decoded back with zxing-cpp, so a test
only passes if a scanner would read the intended content.
"""

import io
import xml.etree.ElementTree as ET  # nosec B405 - parses our own generated SVG

import barcode
import pytest
import qrcode
import zxingcpp
from barcode.writer import ImageWriter
from PIL import Image

import codes
from codes import CodeError, RenderOptions, parse_options, render

PNG = RenderOptions()
SVG = RenderOptions(format="svg")


def decode(data: bytes):
    """Decode a PNG with zxing-cpp; fail the test if nothing is found."""
    result = zxingcpp.read_barcode(Image.open(io.BytesIO(data)))
    assert result is not None, "no symbol decoded"
    return result


def png_size(data: bytes):
    """Return (width, height) of a PNG."""
    return Image.open(io.BytesIO(data)).size


class TestBackwardCompatibility:
    """Default output must stay byte-for-byte what earlier versions produced."""

    def test_qrcode_default_matches_legacy(self):
        """Test the default QR code equals the pre-0.2 rendering (box 10, border 1, ec L)."""
        legacy = qrcode.QRCode(
            border=1, box_size=10, error_correction=qrcode.constants.ERROR_CORRECT_L
        )
        legacy.add_data("ORD-2026-001")
        legacy.make(fit=True)
        buf = io.BytesIO()
        legacy.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
        data, mimetype = render("qrcode", "ORD-2026-001", PNG)
        assert mimetype == "image/png"
        assert data == buf.getvalue()

    def test_barcode_default_matches_legacy(self):
        """Test the default Code 128 equals the pre-0.2 rendering options."""
        buf = io.BytesIO()
        barcode.get("code128", "ABC-123", writer=ImageWriter()).write(
            buf,
            options={
                "module_width": 0.3,
                "module_height": 15.0,
                "quiet_zone": 3.0,
                "font_size": 12,
                "text_distance": 6.0,
                "margin_top": 3.0,
            },
        )
        data, _ = render("barcode", "ABC-123", PNG)
        assert data == buf.getvalue()


class TestRoundTrip:
    """Each type decodes back to its content."""

    @pytest.mark.parametrize(
        "kind, content, fmt",
        [
            ("qrcode", "你好 Hello", "QRCode"),
            ("barcode", "ORDER-2026@01#001", "Code128"),
            ("datamatrix", "LOT-42/A", "DataMatrix"),
            ("ean13", "5901234123457", "EAN13"),
        ],
    )
    def test_decodes_to_content(self, kind, content, fmt):
        """Test that the PNG decodes to the same content and symbology."""
        result = decode(render(kind, content, PNG)[0])
        assert result.text == content
        assert result.format == getattr(zxingcpp.BarcodeFormat, fmt)

    def test_ean13_check_digit_added(self):
        """Test that 12 digits get the GS1 check digit."""
        assert decode(render("ean13", "590123412345", PNG)[0]).text == "5901234123457"


class TestSvg:
    """SVG output is well-formed vector XML."""

    @pytest.mark.parametrize(
        "kind, content",
        [
            ("qrcode", "Hello"),
            ("barcode", "ABC-123"),
            ("datamatrix", "LOT-42"),
            ("ean13", "590123412345"),
        ],
    )
    def test_svg_is_well_formed(self, kind, content):
        """Test that SVG parses and has the SVG root element."""
        data, mimetype = render(kind, content, SVG)
        assert mimetype == "image/svg+xml"
        root = ET.fromstring(data)  # nosec B314 - our own output
        assert root.tag.endswith("svg")

    def test_svg_has_no_script(self):
        """Test that markup in barcode text is escaped, not emitted as elements."""
        data, _ = render("barcode", "<script>x</script>", SVG)
        root = ET.fromstring(data)  # nosec B314 - our own output
        assert not [el for el in root.iter() if el.tag.endswith("script")]

    def test_datamatrix_svg_matches_png_modules(self):
        """Test that the hand-built SVG has one viewBox unit per module plus the border."""
        png = render("datamatrix", "LOT-42", RenderOptions(scale=1, border=0))[0]
        svg = render("datamatrix", "LOT-42", RenderOptions(format="svg", border=0))[0]
        width, height = png_size(png)
        assert ET.fromstring(svg).get("viewBox") == f"0 0 {width} {height}"  # nosec B314


class TestOptions:
    """Each option demonstrably changes the output (zxing-cpp ignores unknown kwargs)."""

    def test_scale_changes_pixels_per_module(self):
        """Test that scale multiplies the image size."""
        small = png_size(render("datamatrix", "LOT", RenderOptions(scale=2, border=0))[0])
        big = png_size(render("datamatrix", "LOT", RenderOptions(scale=6, border=0))[0])
        assert big == (small[0] * 3, small[1] * 3)

    @pytest.mark.parametrize("kind", ["qrcode", "datamatrix", "ean13", "barcode"])
    def test_size_fits_within_target(self, kind):
        """Test that size picks the largest scale that fits and the result still scans."""
        content = "590123412345" if kind == "ean13" else "LOT-42"
        data = render(kind, content, RenderOptions(size=300))[0]
        width, _ = png_size(data)
        assert 150 < width <= 300
        decode(data)

    def test_border_changes_quiet_zone(self):
        """Test that border adds whole modules on each side."""
        base = png_size(render("qrcode", "x", RenderOptions(scale=1, border=0))[0])[0]
        assert png_size(render("qrcode", "x", RenderOptions(scale=1, border=4))[0])[0] == base + 8

    @pytest.mark.parametrize("ec", ["L", "M", "Q", "H"])
    def test_ec_level_is_applied(self, ec):
        """Test that the decoder reports the requested error-correction level."""
        assert decode(render("qrcode", "Hello", RenderOptions(ec=ec))[0]).ec_level == ec

    def test_text_false_removes_human_readable_line(self):
        """Test that text=false makes the 1D image shorter (no digits under the bars)."""
        with_text = png_size(render("ean13", "590123412345", RenderOptions(scale=2))[0])
        without = png_size(render("ean13", "590123412345", RenderOptions(scale=2, text=False))[0])
        assert without[1] < with_text[1]


class TestParseOptions:
    """Query parameter parsing."""

    def test_defaults(self):
        """Test that no parameters give the defaults."""
        assert parse_options({}) == RenderOptions()

    @pytest.mark.parametrize(
        "args, message",
        [
            ({"format": "gif"}, "Invalid format"),
            ({"scale": "0"}, "between"),
            ({"scale": "abc"}, "integer"),
            ({"size": "10"}, "between"),
            ({"scale": "2", "size": "200"}, "either"),
            ({"ec": "X"}, "Invalid ec"),
            ({"border": "11"}, "between"),
            ({"text": "maybe"}, "true or false"),
        ],
    )
    def test_rejects_invalid(self, args, message):
        """Test that invalid options raise CodeError with a clear message."""
        with pytest.raises(CodeError, match=message):
            parse_options(args)


class TestValidation:
    """Content checks."""

    @pytest.mark.parametrize("content", ["59012341234", "ABCDEFGHIJKL", "59012341234567"])
    def test_ean13_rejects_bad_length_or_chars(self, content):
        """Test that EAN-13 needs exactly 12 or 13 digits."""
        with pytest.raises(CodeError, match="12 or 13 digits"):
            render("ean13", content, PNG)

    def test_ean13_rejects_wrong_check_digit(self):
        """Test that a wrong 13th digit is reported with the correct one."""
        with pytest.raises(CodeError, match="expected '7'"):
            render("ean13", "5901234123458", PNG)

    def test_ean13_rejects_border(self):
        """Test that EAN-13 quiet zones cannot be overridden."""
        with pytest.raises(CodeError, match="fixed"):
            render("ean13", "590123412345", RenderOptions(border=2))

    def test_size_too_small(self):
        """Test that an impossible size is a client error, not a broken image."""
        with pytest.raises(CodeError, match="too small"):
            render("qrcode", "x" * 900, RenderOptions(size=64))

    def test_qr_overflow_is_client_error(self):
        """Test that content beyond QR capacity (version 40, ec H) is a CodeError."""
        with pytest.raises(CodeError, match="too long"):
            render("qrcode", "x" * 1300, RenderOptions(ec="H"))  # H holds 1273 bytes

    def test_check_digit(self):
        """Test the GS1 mod-10 check digit on published examples."""
        assert codes.gs1_check_digit("950600013435") == 2
        assert codes.gs1_check_digit("590123412345") == 7

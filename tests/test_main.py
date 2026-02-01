"""
Unit tests for the QR Code and Barcode generation service.
"""

import pytest
from main import app, validate_input, add_security_headers
from flask import Response


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestHealthCheck:
    """Tests for the health check endpoint."""

    def test_health_endpoint(self, client):
        """Test that /health returns 200 OK."""
        response = client.get('/health')
        assert response.status_code == 200
        assert response.data == b'OK'


class TestValidateInput:
    """Tests for input validation function."""

    def test_valid_qrcode_input(self):
        """Test validation with valid QR code input."""
        is_valid, error = validate_input('Hello World', 'qrcode')
        assert is_valid is True
        assert error == ''

    def test_valid_barcode_input(self):
        """Test validation with valid barcode input."""
        is_valid, error = validate_input('ABC123', 'barcode')
        assert is_valid is True
        assert error == ''

    def test_empty_content(self):
        """Test validation with empty content."""
        is_valid, error = validate_input('', 'qrcode')
        assert is_valid is False
        assert 'Missing' in error

    def test_content_too_long(self):
        """Test validation with content exceeding max length."""
        long_content = 'x' * 1001
        is_valid, error = validate_input(long_content, 'qrcode')
        assert is_valid is False
        assert 'exceeds maximum length' in error

    def test_invalid_type(self):
        """Test validation with invalid type parameter."""
        is_valid, error = validate_input('test', 'invalid_type')
        assert is_valid is False
        assert 'Invalid type' in error

    def test_barcode_special_chars_valid(self):
        """Test validation with special characters in barcode (should pass)."""
        is_valid, error = validate_input('ORDER-2026@01#001', 'barcode')
        assert is_valid is True
        assert error == ''

    def test_barcode_max_length(self):
        """Test barcode validation with 64 characters (max allowed)."""
        content_64 = 'A' * 64
        is_valid, error = validate_input(content_64, 'barcode')
        assert is_valid is True
        assert error == ''

    def test_barcode_exceeds_max_length(self):
        """Test barcode validation exceeding 64 character limit."""
        content_65 = 'A' * 65
        is_valid, error = validate_input(content_65, 'barcode')
        assert is_valid is False
        assert '64' in error

    def test_barcode_non_ascii(self):
        """Test barcode validation with non-ASCII characters (should fail)."""
        is_valid, error = validate_input('Hello世界', 'barcode')
        assert is_valid is False
        assert 'ASCII' in error


class TestSecurityHeaders:
    """Tests for security headers."""

    def test_security_headers_added(self):
        """Test that security headers are properly added."""
        with app.app_context():
            response = Response('test')
            response = add_security_headers(response)

            assert response.headers['X-Content-Type-Options'] == 'nosniff'
            assert response.headers['X-Frame-Options'] == 'DENY'
            assert response.headers['X-XSS-Protection'] == '1; mode=block'
            assert 'Content-Security-Policy' in response.headers
            assert 'Cache-Control' in response.headers


class TestGenerateEndpoint:
    """Tests for the /generate endpoint."""

    def test_generate_missing_content(self, client):
        """Test /generate without content parameter."""
        response = client.get('/generate')
        assert response.status_code == 400
        assert b'Missing' in response.data

    def test_generate_qrcode_success(self, client):
        """Test successful QR code generation."""
        response = client.get('/generate?content=TestQR&type=qrcode')
        assert response.status_code == 200
        assert response.mimetype == 'image/png'
        assert len(response.data) > 0

    def test_generate_barcode_success(self, client):
        """Test successful barcode generation."""
        response = client.get('/generate?content=123456&type=barcode')
        assert response.status_code == 200
        assert response.mimetype == 'image/png'
        assert len(response.data) > 0

    def test_generate_default_type(self, client):
        """Test that default type is qrcode."""
        response = client.get('/generate?content=Test')
        assert response.status_code == 200
        assert response.mimetype == 'image/png'

    def test_generate_invalid_type(self, client):
        """Test /generate with invalid type."""
        response = client.get('/generate?content=Test&type=invalid')
        assert response.status_code == 400
        assert b'Invalid type' in response.data

    def test_generate_content_too_long(self, client):
        """Test /generate with content exceeding max length."""
        long_content = 'x' * 1001
        response = client.get(f'/generate?content={long_content}')
        assert response.status_code == 400
        assert b'exceeds maximum length' in response.data

    def test_generate_barcode_special_chars(self, client):
        """Test barcode generation with special characters (should succeed)."""
        response = client.get('/generate?content=ABC-123&type=barcode')
        assert response.status_code == 200
        assert response.mimetype == 'image/png'

    def test_generate_barcode_too_long(self, client):
        """Test barcode generation exceeding 64 character limit."""
        long_barcode = 'A' * 65
        response = client.get(f'/generate?content={long_barcode}&type=barcode')
        assert response.status_code == 400
        assert b'64' in response.data

    def test_generate_barcode_non_ascii(self, client):
        """Test barcode generation with non-ASCII characters."""
        response = client.get('/generate?content=Hello世界&type=barcode')
        assert response.status_code == 400
        assert b'ASCII' in response.data

    def test_cors_headers_present(self, client):
        """Test that CORS headers are present in response."""
        response = client.get('/generate?content=Test')
        assert 'Access-Control-Allow-Origin' in response.headers
        assert 'Access-Control-Allow-Methods' in response.headers

    def test_security_headers_on_generate(self, client):
        """Test that security headers are present on /generate endpoint."""
        response = client.get('/generate?content=Test')
        if response.status_code == 200:
            assert 'X-Content-Type-Options' in response.headers
            assert 'X-Frame-Options' in response.headers


class TestErrorHandlers:
    """Tests for error handlers."""

    def test_404_handler(self, client):
        """Test 404 error handler."""
        response = client.get('/nonexistent')
        assert response.status_code == 404
        assert b'not found' in response.data.lower()


class TestCaseSensitivity:
    """Tests for case sensitivity handling."""

    def test_type_case_insensitive(self, client):
        """Test that type parameter is case-insensitive."""
        response1 = client.get('/generate?content=Test&type=QRCODE')
        response2 = client.get('/generate?content=Test&type=QRCode')
        response3 = client.get('/generate?content=Test&type=qrcode')

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response3.status_code == 200


class TestWhitespaceHandling:
    """Tests for whitespace handling."""

    def test_content_whitespace_trimmed(self, client):
        """Test that content whitespace is trimmed."""
        response = client.get('/generate?content=  Test  ')
        assert response.status_code == 200

    def test_empty_after_trim(self, client):
        """Test that whitespace-only content is rejected."""
        response = client.get('/generate?content=   ')
        assert response.status_code == 400
        assert b'Missing' in response.data

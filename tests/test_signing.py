"""
Tests for signed codes: signing.py, the /sign, /verify and JWKS endpoints, and key tooling.
"""

import hashlib
import io
import os
import subprocess  # nosec B404 - runs our own script in a temp dir
import sys
import time
from pathlib import Path

import pytest
import zxingcpp
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from PIL import Image

import main
import signing
from codes import CodeError
from signing import KeyRing, api_key_matches

DL = "https://id.gs1.org/01/09506000134352/10/ABC123?17=271231"
API_KEY = "test-api-key"
AUTH = {"Authorization": f"Bearer {API_KEY}"}


@pytest.fixture
def ring():
    """A key ring with a fresh signing key."""
    return KeyRing(Ed25519PrivateKey.generate())


@pytest.fixture
def client(monkeypatch, ring):
    """Flask test client with signing configured."""
    monkeypatch.setattr(main, "keyring", ring)
    monkeypatch.setattr(
        main.config, "SIGNING_API_KEY_HASHES", hashlib.sha256(API_KEY.encode()).hexdigest()
    )
    main.app.config["TESTING"] = True
    main.limiter.reset()
    with main.app.test_client() as client:
        yield client


class TestKeyRing:
    """Signing and verification."""

    def test_round_trip(self, ring):
        """Test that a signed URL verifies and keeps the original URL as its prefix."""
        signed = ring.sign(DL)
        assert signed.startswith(DL + "&kid=")
        result = ring.verify(signed)
        assert result.valid and result.url == DL and result.kid == ring.signing_kid

    def test_url_without_query_gets_question_mark(self, ring):
        """Test that kid/sig start the query when the URL has none."""
        assert "/01/09506000134352?kid=" in ring.sign("https://id.gs1.org/01/09506000134352")

    @pytest.mark.parametrize(
        "tamper",
        [
            lambda s: s.replace("ABC123", "ABC124"),  # another batch
            lambda s: s.replace("271231", "291231"),  # later expiry
            lambda s: s.replace("id.gs1.org", "id.gs1.org.evil.example"),  # other host
            lambda s: s[:-2] + ("AA" if s[-2:] != "AA" else "BB"),  # damaged signature
        ],
    )
    def test_tampering_is_detected(self, ring, tamper):
        """Test that changing any part of a signed URL invalidates it."""
        assert not ring.verify(tamper(ring.sign(DL))).valid

    def test_signature_must_be_last(self, ring):
        """Test that parameters appended after sig are rejected, not ignored."""
        result = ring.verify(ring.sign(DL) + "&x=1")
        assert not result.valid and "last parameters" in result.reason

    def test_verify_is_linear_on_hostile_input(self, ring):
        """Test that a long crafted URL is rejected fast (no regex backtracking over the base)."""
        hostile = "https://" * 500 + "?kid=" + "A" * 11 + "&sig=" + "!" * 86
        start = time.perf_counter()
        assert not ring.verify(hostile).valid
        assert time.perf_counter() - start < 0.05

    @pytest.mark.parametrize("bad_base", ["http://x.example/a", "https://", "https://a b/c"])
    def test_verify_rejects_bad_base(self, ring, bad_base):
        """Test that the unsigned part must be a plain https URL."""
        tail = ring.sign("https://x.example/a")[-signing.TAIL_LENGTH :]
        assert not ring.verify(bad_base + tail).valid

    def test_other_key_is_unknown(self, ring):
        """Test that a code signed by someone else's key is not accepted."""
        result = ring.verify(KeyRing(Ed25519PrivateKey.generate()).sign(DL))
        assert not result.valid and result.reason == "unknown key id"

    def test_rotation_keeps_old_codes_valid(self):
        """Test that a retired public key still verifies codes it signed."""
        old = Ed25519PrivateKey.generate()
        old_code = KeyRing(old).sign(DL)
        new_ring = KeyRing(Ed25519PrivateKey.generate(), [old.public_key()])
        assert new_ring.verify(old_code).valid
        assert new_ring.signing_kid != signing.key_id(old.public_key())
        assert len(new_ring.jwks()["keys"]) == 2

    @pytest.mark.parametrize(
        "url, message",
        [
            ("http://id.gs1.org/01/09506000134352", "https"),
            ("https://x.example/a b", "https"),
            ("https://x.example/#frag", "https"),
            (DL + "&kid=abc", "already contains"),
        ],
    )
    def test_rejects_unsuitable_urls(self, ring, url, message):
        """Test that only clean https URLs can be signed."""
        with pytest.raises(CodeError, match=message):
            ring.sign(url)

    def test_verify_only_ring_cannot_sign(self, ring):
        """Test that a ring with only public keys verifies but does not sign."""
        public_only = KeyRing(public_keys=[ring.signing_key.public_key()])
        assert not public_only.can_sign
        assert public_only.verify(ring.sign(DL)).valid

    def test_jwks_format(self, ring):
        """Test the JWKS entry (RFC 8037 OKP/Ed25519)."""
        (key,) = ring.jwks()["keys"]
        assert key["kty"] == "OKP" and key["crv"] == "Ed25519" and key["alg"] == "EdDSA"
        assert key["kid"] == ring.signing_kid
        assert len(signing.unb64url(key["x"])) == 32

    def test_api_key_matching(self):
        """Test the constant-time hash comparison helper."""
        digest = hashlib.sha256(b"k1").hexdigest()
        assert api_key_matches("k1", ["other", digest.upper()])
        assert not api_key_matches("k2", [digest])
        assert not api_key_matches("k1", [])


class TestKeyFiles:
    """Loading keys from PEM files."""

    def test_from_files(self, tmp_path, ring):
        """Test loading a private key and a retired public key."""
        private = tmp_path / "key.pem"
        private.write_bytes(
            ring.signing_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        retired = Ed25519PrivateKey.generate().public_key()
        public = tmp_path / "old.pub.pem"
        public.write_bytes(
            retired.public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )
        loaded = KeyRing.from_files(str(private), f" {public} ,")
        assert loaded.signing_kid == ring.signing_kid
        assert signing.key_id(retired) in loaded.public_keys

    def test_rejects_non_ed25519_key(self, tmp_path):
        """Test that an EC key is refused at startup instead of producing odd signatures."""
        path = tmp_path / "ec.pem"
        path.write_bytes(
            ec.generate_private_key(ec.SECP256R1()).private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        with pytest.raises(ValueError, match="Ed25519"):
            KeyRing.from_files(str(path))

    def test_no_files_means_no_keys(self):
        """Test the default (signing not configured)."""
        assert KeyRing.from_files().jwks() == {"keys": []}


class TestGenSigningKey:
    """scripts/gen_signing_key.py."""

    SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "gen_signing_key.py"

    def run(self, path):
        """Run the script and return the completed process."""
        return subprocess.run(  # nosec B603 - fixed interpreter and script
            [sys.executable, str(self.SCRIPT), str(path)], capture_output=True, text=True
        )

    def test_creates_private_key_0600_and_matching_hash(self, tmp_path):
        """Test the key file mode, that it loads, and that the printed hash matches the API key."""
        key = tmp_path / "secrets" / "signing_key.pem"
        result = self.run(key)
        assert result.returncode == 0, result.stderr
        api_key_file = key.with_suffix(".apikey")
        assert os.stat(key).st_mode & 0o777 == 0o600
        assert os.stat(api_key_file).st_mode & 0o777 == 0o600
        api_key = api_key_file.read_text().strip()
        assert api_key not in result.stdout  # never printed
        printed_hash = result.stdout.split("SIGNING_API_KEY_HASHES=")[1].strip()
        assert printed_hash == hashlib.sha256(api_key.encode()).hexdigest()
        assert KeyRing.from_files(str(key)).can_sign

    def test_refuses_to_overwrite(self, tmp_path):
        """Test that an existing key is never replaced."""
        key = tmp_path / "k.pem"
        assert self.run(key).returncode == 0
        before = key.read_bytes()
        assert self.run(key).returncode == 1
        assert key.read_bytes() == before


class TestApi:
    """HTTP endpoints."""

    def test_sign_requires_api_key(self, client):
        """Test 401 without, or with a wrong, Bearer key."""
        for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": API_KEY}):
            response = client.post("/sign", json={"url": DL}, headers=headers)
            assert response.status_code == 401
            assert response.headers["WWW-Authenticate"] == "Bearer"

    def test_sign_unconfigured_is_503(self, client, monkeypatch):
        """Test that a server without a private key says so (after auth)."""
        monkeypatch.setattr(main, "keyring", KeyRing())
        assert client.post("/sign", json={"url": DL}, headers=AUTH).status_code == 503

    def test_sign_url_then_verify_and_render(self, client):
        """Test the full flow: sign, render the QR, decode it, verify the decoded text."""
        signed = client.post("/sign", json={"url": DL}, headers=AUTH).get_json()["url"]
        image = client.get("/generate", query_string={"content": signed, "ec": "M"})
        assert image.status_code == 200
        scanned = zxingcpp.read_barcode(Image.open(io.BytesIO(image.data))).text
        result = client.get("/verify", query_string={"u": scanned}).get_json()
        assert result["valid"] is True
        assert result["gs1"] == {"01": "09506000134352", "10": "ABC123", "17": "271231"}

    def test_sign_gs1_fields(self, client):
        """Test signing GS1 fields builds the Digital Link first."""
        body = {"gtin": "9506000134352", "batch": "ABC123", "expiry": "2027-12-31"}
        data = client.post("/sign", json=body, headers=AUTH).get_json()
        assert data["url"].startswith(DL + "&kid=" + data["kid"] + "&sig=")

    @pytest.mark.parametrize(
        "body, status",
        [
            ("not json", 400),
            ({"url": "http://x.example"}, 400),
            ({"gtin": "9506000134353"}, 400),
        ],
    )
    def test_sign_rejects_bad_bodies(self, client, body, status):
        """Test validation errors on /sign."""
        kwargs = {"data": body} if isinstance(body, str) else {"json": body}
        assert client.post("/sign", headers=AUTH, **kwargs).status_code == status

    def test_verify_tampered(self, client):
        """Test that /verify reports a changed batch as invalid without GS1 data."""
        signed = client.post("/sign", json={"url": DL}, headers=AUTH).get_json()["url"]
        result = client.get("/verify", query_string={"u": signed.replace("ABC123", "XYZ")})
        body = result.get_json()
        assert body["valid"] is False and body["gs1"] is None

    def test_verify_requires_u(self, client):
        """Test the missing-parameter error."""
        assert client.get("/verify").status_code == 400

    def test_jwks_endpoint(self, client, ring):
        """Test the public key set is served and cacheable."""
        response = client.get("/.well-known/qr-signing-keys.json")
        assert response.get_json()["keys"][0]["kid"] == ring.signing_kid
        assert "max-age=3600" in response.headers["Cache-Control"]

    def test_cross_origin_browsers_cannot_send_auth(self, client):
        """Test that CORS does not allow the Authorization header (no browser-based signing)."""
        response = client.get("/health")
        assert "Authorization" not in response.headers["Access-Control-Allow-Headers"]
        assert "POST" not in response.headers["Access-Control-Allow-Methods"]

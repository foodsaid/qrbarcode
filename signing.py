"""
Ed25519 signatures for anti-counterfeit codes.

A signed code is an https URL whose last two query parameters are
``kid=<key id>&sig=<signature>``:

    https://id.gs1.org/01/09506000134352/10/ABC123?17=271231&kid=Ab12Cd34Ef5&sig=<86 chars>

The signature covers the exact URL text before ``[?&]kid=``, prefixed with a version tag,
so verification never depends on URL normalisation. A signature proves the code was issued
by the key holder (no one can invent a new batch or change a date); it does not stop
someone from photocopying a genuine code.
"""

import base64
import hashlib
import hmac
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from codes import CodeError

DOMAIN_TAG = b"qrbarcode-sig-v1\n"
MAX_URL_LENGTH = 1000
SIGNED_URL = re.compile(
    r"(?P<base>https://[^\s#]+?)[?&]kid=(?P<kid>[A-Za-z0-9_-]{11})&sig=(?P<sig>[A-Za-z0-9_-]{86})"
)


def b64url(data: bytes) -> str:
    """Unpadded base64url."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64url(text: str) -> bytes:
    """Decode unpadded base64url."""
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def raw_public_key(key: Ed25519PublicKey) -> bytes:
    """The 32-byte public key."""
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def key_id(key: Ed25519PublicKey) -> str:
    """Key id: base64url of the first 8 bytes of SHA-256(public key) (11 characters)."""
    return b64url(hashlib.sha256(raw_public_key(key)).digest()[:8])


def message(base: str, kid: str) -> bytes:
    """Bytes that are signed: version tag, key id, then the exact unsigned URL."""
    return DOMAIN_TAG + kid.encode() + b"\n" + base.encode()


@dataclass(frozen=True)
class Verification:
    """Result of verifying a scanned URL."""

    valid: bool
    reason: str
    kid: Optional[str] = None
    url: Optional[str] = None  # the URL without kid/sig


class KeyRing:
    """One signing key (optional) plus the public keys that verification accepts."""

    def __init__(
        self,
        signing_key: Optional[Ed25519PrivateKey] = None,
        public_keys: Iterable[Ed25519PublicKey] = (),
    ):
        """Index public keys by kid; the signing key's public key is always included."""
        self.signing_key = signing_key
        keys: List[Ed25519PublicKey] = list(public_keys)
        if signing_key is not None:
            keys.insert(0, signing_key.public_key())
        self.public_keys: Dict[str, Ed25519PublicKey] = {key_id(k): k for k in keys}

    @classmethod
    def from_files(cls, private_key_file: str = "", public_key_files: str = "") -> "KeyRing":
        """Load a PEM private key and comma-separated PEM public keys (retired keys)."""
        signing_key = None
        if private_key_file:
            loaded = serialization.load_pem_private_key(
                Path(private_key_file).read_bytes(), password=None
            )
            if not isinstance(loaded, Ed25519PrivateKey):
                raise ValueError("SIGNING_KEY_FILE must contain an Ed25519 private key")
            signing_key = loaded
        public_keys = []
        for path in filter(None, (p.strip() for p in public_key_files.split(","))):
            public = serialization.load_pem_public_key(Path(path).read_bytes())
            if not isinstance(public, Ed25519PublicKey):
                raise ValueError(f"{path} is not an Ed25519 public key")
            public_keys.append(public)
        return cls(signing_key, public_keys)

    @property
    def can_sign(self) -> bool:
        """Whether a private key is configured."""
        return self.signing_key is not None

    @property
    def signing_kid(self) -> Optional[str]:
        """Key id of the signing key, if any."""
        return key_id(self.signing_key.public_key()) if self.signing_key else None

    def sign(self, url: str) -> str:
        """Append kid and sig to an https URL. Raises CodeError for unsuitable URLs."""
        if self.signing_key is None:
            raise RuntimeError("No signing key configured")
        if not url.startswith("https://") or any(c.isspace() for c in url) or "#" in url:
            raise CodeError("Only https URLs without spaces or fragments can be signed")
        if re.search(r"[?&](kid|sig)=", url):
            raise CodeError("URL already contains kid or sig parameters")
        kid = key_id(self.signing_key.public_key())
        signature = self.signing_key.sign(message(url, kid))
        signed = f"{url}{'&' if '?' in url else '?'}kid={kid}&sig={b64url(signature)}"
        if len(signed) > MAX_URL_LENGTH:
            raise CodeError(f"Signed URL would exceed {MAX_URL_LENGTH} characters")
        return signed

    def verify(self, signed_url: str) -> Verification:
        """Check that kid/sig are the last parameters and the signature matches a known key."""
        match = SIGNED_URL.fullmatch(signed_url.strip())
        if not match:
            return Verification(False, "not a signed URL (kid and sig must be the last parameters)")
        base, kid = match["base"], match["kid"]
        public = self.public_keys.get(kid)
        if public is None:
            return Verification(False, "unknown key id", kid=kid, url=base)
        try:
            public.verify(unb64url(match["sig"]), message(base, kid))
        except (InvalidSignature, ValueError):
            return Verification(False, "signature does not match", kid=kid, url=base)
        return Verification(True, "ok", kid=kid, url=base)

    def jwks(self) -> dict:
        """Public keys as a JSON Web Key Set (OKP / Ed25519, RFC 8037)."""
        return {
            "keys": [
                {"kty": "OKP", "crv": "Ed25519", "x": b64url(raw_public_key(k)), "kid": kid}
                | {"use": "sig", "alg": "EdDSA"}
                for kid, k in self.public_keys.items()
            ]
        }


def api_key_matches(presented: str, allowed_sha256_hex: Iterable[str]) -> bool:
    """Compare SHA-256(presented API key) with the configured hashes in constant time."""
    digest = hashlib.sha256(presented.encode()).hexdigest()
    matched = False
    for allowed in allowed_sha256_hex:
        matched |= hmac.compare_digest(digest, allowed.strip().lower())
    return matched

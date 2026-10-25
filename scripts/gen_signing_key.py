"""Create an Ed25519 signing key and an API key for POST /sign.

    python scripts/gen_signing_key.py secrets/signing_key.pem

Writes the private key (mode 0600, never overwrites) and its public key next to it,
then prints the key id, a new API key (shown once) and the SHA-256 to put in
SIGNING_API_KEY_HASHES. Keep the private key and the API key out of git.
"""

import hashlib
import os
import secrets
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from signing import key_id  # noqa: E402


def main() -> int:
    """Generate the key pair and API key described in the module docstring."""
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    private_path = Path(sys.argv[1])
    public_path = private_path.with_suffix(".pub.pem")
    if private_path.exists() or public_path.exists():
        print(f"Refusing to overwrite {private_path} / {public_path}", file=sys.stderr)
        return 1
    private_path.parent.mkdir(parents=True, exist_ok=True)

    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(pem)
    public_path.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )

    api_key = secrets.token_urlsafe(32)
    print(f"Private key : {private_path} (mode 0600)")
    print(f"Public key  : {public_path}")
    print(f"Key id (kid): {key_id(key.public_key())}")
    print(f"API key     : {api_key}   <- shown once; give it to the systems that sign")
    print(f"SIGNING_API_KEY_HASHES={hashlib.sha256(api_key.encode()).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

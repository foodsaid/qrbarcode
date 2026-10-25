"""Fail if any installed distribution carries a copyleft license.

Stdlib only, so it runs inside the production image without extra packages:

    docker run --rm -i qr-service:test python - < scripts/check_licenses.py
"""

import re
import sys
from importlib.metadata import distributions

COPYLEFT = re.compile(r"\b(A?GPL|LGPL|SSPL|GNU (Affero |Lesser )?General Public)", re.IGNORECASE)


def license_of(dist) -> str:
    """Return the declared license expression, text and classifiers of a distribution."""
    meta = dist.metadata
    parts = [meta.get("License-Expression") or "", (meta.get("License") or "").splitlines()[0:1]]
    classifiers = [c for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    flat = [parts[0], *parts[1], *classifiers]
    return " | ".join(p for p in flat if p)


def main() -> int:
    """Print each distribution's license and return 1 if any is copyleft."""
    bad = []
    for dist in sorted(distributions(), key=lambda d: d.metadata["Name"].lower()):
        lic = license_of(dist)
        print(f"{dist.metadata['Name']}=={dist.version}: {lic or 'UNKNOWN'}")
        if COPYLEFT.search(lic):
            bad.append(dist.metadata["Name"])
    if bad:
        print(f"Copyleft licenses found: {', '.join(bad)}", file=sys.stderr)
        return 1
    print("No copyleft licenses found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

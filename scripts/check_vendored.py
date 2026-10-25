"""Check vendored front-end code (Swagger UI and what it bundles) against OSV.

Dependabot and pip-audit only see Python packages, so the vendored Swagger UI and the
DOMPurify copy inside its bundle are checked here. Fails on any advisory that is not in
scripts/vendored_vuln_allowlist.json, so new issues get reviewed.

    python scripts/check_vendored.py
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "static" / "vendor"
ALLOWLIST = Path(__file__).with_name("vendored_vuln_allowlist.json")


def vendored_packages() -> list:
    """Return (npm package, version) pairs for the vendored code."""
    packages = []
    for swagger_dir in sorted(VENDOR.glob("swagger-ui-*")):
        packages.append(("swagger-ui-dist", swagger_dir.name.removeprefix("swagger-ui-")))
        licenses = swagger_dir / "swagger-ui-bundle.js.LICENSE.txt"
        match = re.search(r"DOMPurify (\d+\.\d+\.\d+)", licenses.read_text(encoding="utf-8"))
        if match:
            packages.append(("dompurify", match.group(1)))
    return packages


def osv_vulns(name: str, version: str) -> list:
    """Query OSV for advisories affecting an npm package version."""
    query = {"package": {"name": name, "ecosystem": "npm"}, "version": version}
    request = urllib.request.Request(
        "https://api.osv.dev/v1/query",
        data=json.dumps(query).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310 - fixed https URL
        vulns: list = json.load(response).get("vulns", [])
    return vulns


def main() -> int:
    """Print advisories for each vendored package; return 1 if any is not allowlisted."""
    allowed = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    unreviewed = []
    for name, version in vendored_packages():
        vulns = osv_vulns(name, version)
        print(f"{name}@{version}: {len(vulns)} advisories")
        for vuln in vulns:
            severity = vuln.get("database_specific", {}).get("severity", "UNKNOWN")
            status = "reviewed" if vuln["id"] in allowed else "NOT REVIEWED"
            print(f"  {vuln['id']} {severity} [{status}] {vuln.get('summary', '')[:80]}")
            if vuln["id"] not in allowed:
                unreviewed.append(vuln["id"])
    if unreviewed:
        print(f"Unreviewed advisories: {', '.join(unreviewed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

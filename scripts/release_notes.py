"""Print the CHANGELOG.md section for one version, for use as GitHub release notes.

    python scripts/release_notes.py 0.1.3        # or v0.1.3

Exits 1 if the version has no section, so a release cannot go out undocumented.
"""

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def section(version: str, text: str) -> str:
    """Return the body under `## [version]` up to the next `## [` heading or `---` rule."""
    match = re.search(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|^---\s*$|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def main() -> int:
    """Print the notes for the version given on the command line."""
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    version = sys.argv[1].removeprefix("v")
    notes = section(version, CHANGELOG.read_text(encoding="utf-8"))
    if not notes:
        print(f"No CHANGELOG.md section for {version}", file=sys.stderr)
        return 1
    print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())

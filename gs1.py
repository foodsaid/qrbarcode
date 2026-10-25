"""
GS1 Digital Link and GS1 element strings for trade items (GTIN + batch/serial + dates).

Pure functions, no third-party dependencies. Validation follows the GS1 General
Specifications: GTIN check digit, GS1 character set 82 for batch/serial, YYMMDD dates.

    >>> item = build({"gtin": "9506000134352", "batch": "ABC123", "expiry": "271231"})
    >>> item.digital_link()
    'https://id.gs1.org/01/09506000134352/10/ABC123?17=271231'
    >>> item.element_string()
    '(01)09506000134352(17)271231(10)ABC123'
"""

import calendar
import re
from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional
from urllib.parse import parse_qsl, quote, unquote, urlsplit

from codes import CodeError, gs1_check_digit

DEFAULT_RESOLVER = "https://id.gs1.org"

# Query/field name -> (AI, description). Order inside each group is the GS1 Digital Link
# order: key qualifiers 10 then 21 in the path, date attributes in the query string.
QUALIFIERS = {"batch": "10", "serial": "21"}
DATES = {"prod_date": "11", "pack_date": "13", "best_before": "15", "expiry": "17"}
ALIASES = {"lot": "batch"}
AI_NAMES = {
    "01": "gtin",
    **{ai: name for name, ai in QUALIFIERS.items()},
    **{ai: name for name, ai in DATES.items()},
}

# GS1 AI encodable character set 82 (General Specifications, figure 7.11-1)
CSET82 = re.compile(r"""[!"%&'()*+,\-./0-9:;<=>?A-Z_a-z]{1,20}""")
ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


@dataclass(frozen=True)
class TradeItem:
    """A validated GTIN with optional batch/serial and dates (all values as GS1 strings)."""

    gtin: str
    batch: Optional[str] = None
    serial: Optional[str] = None
    dates: Dict[str, str] = field(default_factory=dict)  # AI -> YYMMDD

    def ais(self) -> Dict[str, str]:
        """All application identifiers with their values, in Digital Link order."""
        result = {"01": self.gtin}
        if self.batch:
            result["10"] = self.batch
        if self.serial:
            result["21"] = self.serial
        result.update(sorted(self.dates.items()))
        return result

    def element_string(self) -> str:
        """Human-readable GS1 element string, fixed-length AIs first to save FNC1 separators."""
        fixed = "".join(f"({ai}){value}" for ai, value in sorted(self.dates.items()))
        variable = "".join(f"({ai}){v}" for ai, v in (("10", self.batch), ("21", self.serial)) if v)
        return f"(01){self.gtin}{fixed}{variable}"

    def digital_link(self, resolver: str = DEFAULT_RESOLVER) -> str:
        """GS1 Digital Link URI on `resolver` (validated with `normalize_resolver`)."""
        path = f"/01/{self.gtin}"
        for ai, value in (("10", self.batch), ("21", self.serial)):
            if value:
                path += f"/{ai}/{quote(value, safe='')}"
        query = "&".join(f"{ai}={value}" for ai, value in sorted(self.dates.items()))
        return f"{normalize_resolver(resolver)}{path}" + (f"?{query}" if query else "")


def normalize_gtin(raw: str) -> str:
    """Validate a GTIN-8/12/13/14 and return it as 14 digits."""
    if not raw.isascii() or not raw.isdigit() or len(raw) not in (8, 12, 13, 14):
        raise CodeError("GTIN must be 8, 12, 13 or 14 digits")
    gtin = raw.zfill(14)
    expected = gs1_check_digit(gtin[:13])
    if int(gtin[13]) != expected:
        raise CodeError(f"Invalid GTIN check digit '{gtin[13]}', expected '{expected}'")
    return gtin


def normalize_date(name: str, raw: str) -> str:
    """Accept YYMMDD or YYYY-MM-DD; return YYMMDD. DD=00 means 'end of month' per GS1."""
    iso = ISO_DATE.fullmatch(raw)
    if iso:
        raw = iso.group(1)[2:] + iso.group(2) + iso.group(3)
    if not re.fullmatch(r"\d{6}", raw):
        raise CodeError(f"'{name}' must be YYMMDD or YYYY-MM-DD")
    year, month, day = 2000 + int(raw[:2]), int(raw[2:4]), int(raw[4:])
    if not 1 <= month <= 12:
        raise CodeError(f"'{name}' has an invalid month")
    if day != 0 and day > calendar.monthrange(year, month)[1]:
        raise CodeError(f"'{name}' has an invalid day")
    return raw


def normalize_text(name: str, raw: str) -> str:
    """Batch/serial: 1-20 characters from GS1 character set 82."""
    if not CSET82.fullmatch(raw):
        raise CodeError(f"'{name}' must be 1-20 characters from the GS1 character set 82")
    return raw


def normalize_resolver(raw: str) -> str:
    """An https origin with an optional path prefix, no query, fragment or credentials."""
    parts = urlsplit(raw.strip())
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.query
        or parts.fragment
        or parts.username
        or parts.password
        or not re.fullmatch(r"[A-Za-z0-9.-]+", parts.hostname)
    ):
        raise CodeError("'domain' must be an https URL without query, fragment or credentials")
    return f"https://{parts.netloc}{parts.path.rstrip('/')}"


def build(args: Mapping[str, str]) -> TradeItem:
    """Validate request parameters (gtin, batch/lot, serial, dates) into a TradeItem."""
    values = {ALIASES.get(k, k): v.strip() for k, v in args.items() if v and v.strip()}
    if "gtin" not in values:
        raise CodeError("Missing 'gtin' parameter")
    return TradeItem(
        gtin=normalize_gtin(values["gtin"]),
        batch=normalize_text("batch", values["batch"]) if "batch" in values else None,
        serial=normalize_text("serial", values["serial"]) if "serial" in values else None,
        dates={ai: normalize_date(n, values[n]) for n, ai in DATES.items() if n in values},
    )


def parse_digital_link(uri: str) -> TradeItem:
    """Parse and validate a GS1 Digital Link URI (any resolver); extra query keys are ignored."""
    parts = urlsplit(uri)
    segments = parts.path.split("/")
    try:
        start = len(segments) - 1 - segments[::-1].index("01")
    except ValueError:
        raise CodeError("Not a GS1 Digital Link: no /01/{gtin} in the path") from None
    tail = segments[start:]
    if len(tail) % 2:
        raise CodeError("GS1 Digital Link path must be /AI/value pairs")
    path_ais = {tail[i]: unquote(tail[i + 1]) for i in range(0, len(tail), 2)}
    if not set(path_ais) <= {"01", "10", "21"}:
        raise CodeError("Unsupported AI in GS1 Digital Link path")
    fields = {AI_NAMES[ai]: value for ai, value in path_ais.items()}
    for key, value in parse_qsl(parts.query):
        if key in DATES.values():
            fields[AI_NAMES[key]] = value
    return build(fields)

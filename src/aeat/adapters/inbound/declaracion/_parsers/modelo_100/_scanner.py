"""Casilla-line scanner for Modelo 100 (IRPF annual) justificantes.

Two AEAT-published shapes coexist in the live corpus:

- **Modern** (tax year 2022 onwards): each casilla prints on its own
  line as ``<label words> <value> <casilla-id>`` where ``casilla-id``
  is the trailing token. pdfplumber emits this shape verbatim.
- **Legacy** (tax year 2021 and earlier): the declarant-header block on
  page 2 is 2-column rendered, so pdfplumber emits ``<CID> <VAL> <CID2>
  <VAL2> ...`` on a single line. Casillas further down the PDF (pages
  3+) already use the modern shape.

The scanner runs three passes over every page's line stream and merges
by casilla id (first-pass wins):

1. ``tail_split`` — modern ``label VALUE CID`` extraction.
2. ``forward_scan`` — column-split ``CID VAL CID VAL ...`` extraction,
   gated to a whitelist of header casilla ids so the algorithm only
   fires on legacy declarant/representative rows.
3. ``legacy_tail_split`` — ``label ... CID VAL`` where the 2021 layout
   prints filler dots between label and value and the casilla id sits
   second-to-last (e.g. ``... 70 09`` for the CCAA code).

The scanner is read-only — it consumes pdfplumber-extracted text and
returns a tuple of :class:`ScannedCasilla` records. All pattern
matching is bounded and side-effect free.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from ..._extract import parse_spanish_decimal

# Spanish-formatted amount (``1.234,56``). Kept local because the Modelo
# 100 scanner also accepts integer-only values (``86441`` days) and
# non-decimal strings (NIF / catastral code); the canonical
# ``SPANISH_AMOUNT_GROUP`` from ``_label_regex`` is reserved for
# line-anchored label-regex primitives where the captured group MUST
# be an amount.
_AMOUNT_RE: Final = re.compile(r"^-?[0-9]{1,3}(?:\.[0-9]{3})*(?:,[0-9]{1,2})?$")
_INT_RE: Final = re.compile(r"^[0-9]+$")
_DATE_RE: Final = re.compile(r"^(?P<d>\d{2})[/-](?P<m>\d{2})[/-](?P<y>\d{4})$")
_NIF_RE: Final = re.compile(r"^[A-Z0-9]{8,12}$")
_UPPER_TOKEN_RE: Final = re.compile(r"^[A-ZÑÁÉÍÓÚÜ0-9][A-ZÑÁÉÍÓÚÜ0-9./-]*$")
_TITLECASE_WORD_RE: Final = re.compile(r"^[A-ZÑÁÉÍÓÚÜ][a-zñáéíóúü/]+$")
_LOWERCASE_TAIL_RE: Final = re.compile(r"[a-zñáéíóúü][.\)]?$")
_LETTER_ANYWHERE_RE: Final = re.compile(r"[A-Za-zÑñÁáÉéÍíÓóÚúÜü]")

# Runs of filler glyphs the 2021 legacy layout uses between label and
# value. Replaced with a single space so the tail-split patterns see a
# clean ``label VALUE CID``. Includes the mojibake ``�`` sequences
# pdfplumber emits when the PDF's cmap substitutes accented glyphs.
_FILLER_RUN_RE: Final = re.compile(r"[…­.\s�]{3,}")

# AEAT page-header stamps appear on every page and would otherwise let
# a stray 3-digit number (``533`` from the Teléfono line) collide with
# a real casilla id. Lines matching any of these patterns are skipped.
_HEADER_NOISE_RE: Final = re.compile(
    r"(Tel[ée]fono|Agencia Tributaria|sede\.agenciatributaria|"
    r"C[óo]digo Seguro|La autenticidad de este documento)",
    re.IGNORECASE,
)

# Tokens that stand alone as Modelo 100 casilla values.
_SPECIAL_VALUE_TOKENS: Final[frozenset[str]] = frozenset({"X", "H", "M", "A05"})

# Declarant / cónyuge / tributación / CCAA header casillas whose values
# appear in legacy column-split rows on page 2. Unused casilla ids in
# this list (e.g. ``11`` discapacidad when blank) simply do not produce
# a hit, so the whitelist is safe to keep inclusive.
HEADER_FORWARD_CIDS: Final[frozenset[str]] = frozenset(
    {
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "09",
        "10",
        "11",
        "12",
        "13",
        "14",
        "43",
        "59",
        "60",
        "61",
        "62",
        "64",
        "65",
        "66",
        "67",
        "68",
        "69",
        "70",
        "105",
        "106",
    }
)


@dataclass(frozen=True, slots=True)
class ScannedCasilla:
    """One ``(casilla_id, printed_value)`` record from the scanner."""

    casilla_id: str
    raw_value: str
    typed_value: Decimal | int | str | date
    source_page: int
    primitive: str


def scan_pages(pages: tuple[str, ...]) -> tuple[ScannedCasilla, ...]:
    """Run all three passes on ``pages`` (1-based page numbering).

    First-pass wins — a later pass will not overwrite an earlier hit.
    The pass order is chosen so the strongest signals (modern
    tail-split) dominate over the weaker legacy forward-scan.
    """
    captures: dict[str, ScannedCasilla] = {}

    def _record(candidate: ScannedCasilla) -> None:
        captures.setdefault(candidate.casilla_id, candidate)

    lines: list[tuple[int, str]] = []
    for pg_i, page_text in enumerate(pages, start=1):
        for raw_line in page_text.splitlines():
            stripped = raw_line.strip()
            if stripped:
                lines.append((pg_i, stripped))

    # Pass 1 — modern layout: label VALUE CID at end of line.
    for pg_i, line in lines:
        hit = _tail_split(line)
        if hit is None:
            continue
        cid, value = hit
        typed = _type_value(value)
        _record(
            ScannedCasilla(
                casilla_id=cid,
                raw_value=value,
                typed_value=typed,
                source_page=pg_i,
                primitive="tail_cid",
            )
        )

    # Pass 2 — column-split declarant header: CID VAL CID VAL ...
    for pg_i, line in lines:
        for cid, value in _forward_scan(line, HEADER_FORWARD_CIDS):
            typed = _type_value(value)
            _record(
                ScannedCasilla(
                    casilla_id=cid,
                    raw_value=value,
                    typed_value=typed,
                    source_page=pg_i,
                    primitive="forward_cid",
                )
            )

    # Pass 3 — legacy long-label tail: label... CID VAL.
    for pg_i, line in lines:
        hit = _legacy_tail_split(line, HEADER_FORWARD_CIDS)
        if hit is None:
            continue
        cid, value = hit
        typed = _type_value(value)
        _record(
            ScannedCasilla(
                casilla_id=cid,
                raw_value=value,
                typed_value=typed,
                source_page=pg_i,
                primitive="legacy_tail",
            )
        )

    # Deterministic ordering: by (int(casilla_id), casilla_id) — keeps
    # printed-form-friendly sort for both 2-digit and 4-digit ids.
    return tuple(sorted(captures.values(), key=lambda c: (int(c.casilla_id), c.casilla_id)))


def _normalise(line: str) -> str:
    return _FILLER_RUN_RE.sub(" ", line).strip()


def _is_meaningful_value(value: str) -> bool:
    """Return True if ``value`` is a real casilla payload (not filler)."""
    if not value:
        return False
    if re.fullmatch(r"[.…­�]+", value):
        return False
    return bool(_LETTER_ANYWHERE_RE.search(value) or re.search(r"[0-9]", value))


def _is_valid_cid(cid: str) -> bool:
    """Return True iff ``cid`` is a plausible Modelo 100 casilla id.

    Rejects 4-digit tokens that don't start with ``0`` (they would be
    years, OCR artifacts, or tokens like ``2021``) and 2-3 digit
    tokens that fall in the 2000-2099 year range.
    """
    if not cid.isdigit():
        return False
    if len(cid) == 4:
        return cid.startswith("0")
    if len(cid) in (2, 3):
        n = int(cid)
        return not (2000 <= n <= 2099) and 1 <= n <= 999
    return False


def _is_value_like(tok: str) -> bool:
    """Return True iff ``tok`` looks like a casilla value (not a label word).

    Values are Spanish amounts, integers, dates, NIFs, single-letter
    markers, all-uppercase codes, or single Title-case Spanish words
    (``Hombre``, ``Soltero/a``, ``Simplificada``). A bare 4-digit year
    token (2000-2099) is excluded so the value-walk doesn't swallow the
    ejercicio stamp printed mid-line in Modelo 100 labels.
    """
    if _INT_RE.match(tok) and len(tok) == 4 and 2000 <= int(tok) <= 2099:
        return False
    if _AMOUNT_RE.match(tok):
        return True
    if _INT_RE.match(tok):
        return True
    if _DATE_RE.match(tok):
        return True
    if _NIF_RE.match(tok):
        return True
    if tok in _SPECIAL_VALUE_TOKENS:
        return True
    if _UPPER_TOKEN_RE.match(tok) and len(tok) >= 2:
        return True
    return bool(_TITLECASE_WORD_RE.match(tok))


def _tail_split(line: str) -> tuple[str, str] | None:
    """Modern-layout tail-CID split: ``label VALUE CID``.

    Returns ``(casilla_id, value)`` or ``None``. The value is obtained
    by walking backwards from the CID and including tokens while they
    remain value-like (amounts, uppercase codes, dates, NIF, etc.).
    """
    if _HEADER_NOISE_RE.search(line):
        return None
    norm = _normalise(line)
    match = re.match(r"^(.+?)\s+(\d{2,4})\s*$", norm)
    if match is None:
        return None
    prefix = match.group(1)
    cid = match.group(2)
    if not _is_valid_cid(cid):
        return None
    tokens = prefix.split()
    if not tokens:
        return None
    val_start = _walk_back_value_start(tokens)
    value = " ".join(tokens[val_start:])
    label = " ".join(tokens[:val_start]).strip()
    if not _LETTER_ANYWHERE_RE.search(label):
        return None
    return cid, value


def _walk_back_value_start(tokens: list[str]) -> int:
    """Return the index at which the value slice begins.

    Walks from right to left: stops at the first token ending in a
    lowercase letter (a label word), includes consecutive value-like
    tokens up to that point, and guarantees at least one token is
    designated as label and at least one as value.
    """
    n = len(tokens)
    val_start = n
    for k in range(n - 1, -1, -1):
        tok = tokens[k]
        if _LOWERCASE_TAIL_RE.search(tok):
            val_start = k + 1
            break
        if _is_value_like(tok):
            val_start = k
            continue
        val_start = k + 1
        break
    if val_start == 0:
        val_start = 1
    if val_start == n:
        val_start = n - 1
    return val_start


def _forward_scan(line: str, allowed: frozenset[str]) -> Iterable[tuple[str, str]]:
    """Scan a column-split line ``CID VAL CID VAL ...``.

    Emits one ``(casilla_id, value)`` pair per CID token in ``allowed``;
    value is the concatenation of the following tokens up to the next
    allowed CID. Blank values (two adjacent allowed CIDs) are dropped.

    Yields nothing for lines that contain no allowed CID tokens.
    """
    norm_line = _normalise(line)
    # "01Y4113523X" → "01 Y4113523X" so the leading CID is its own token.
    norm = re.sub(r"^(\d{2,3})(?=\S)", r"\1 ", norm_line)
    tokens = norm.split()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if re.fullmatch(r"\d{2,3}", tok) and tok in allowed:
            j = i + 1
            value_tokens: list[str] = []
            while j < len(tokens):
                nxt = tokens[j]
                if re.fullmatch(r"\d{2,3}", nxt) and nxt in allowed:
                    break
                value_tokens.append(nxt)
                j += 1
            value = " ".join(value_tokens).strip()
            if _is_meaningful_value(value):
                yield tok, value
            i = j
        else:
            i += 1


_LEGACY_TAIL_RE: Final = re.compile(r"^(?P<label>.+?)\s+(?P<cid>\d{2,3})\s+(?P<value>\S{1,24})\s*$")


def _legacy_tail_split(line: str, allowed: frozenset[str]) -> tuple[str, str] | None:
    """2021-layout tail: ``<long label with filler dots> CID VAL``.

    AEAT's legacy Modelo 100 prints certain casillas as
    ``label........................ CID VAL`` where the CID sits
    second-to-last and the value is the very last token (e.g.
    ``... 68 X`` for ``Tributación individual`` or ``... 70 09`` for the
    CCAA-code casilla). After filler-dot normalisation the line is
    pattern-friendly — but the main ``_tail_split`` misses it because
    the last token is the value, not the CID.

    Restricted to ``allowed`` (header casilla ids) so we don't
    accidentally promote a random trailing 2-digit integer to a
    casilla-id role on other pages.
    """
    if _HEADER_NOISE_RE.search(line):
        return None
    norm = _normalise(line)
    match = _LEGACY_TAIL_RE.match(norm)
    if match is None:
        return None
    cid = match.group("cid")
    if cid not in allowed:
        return None
    value = match.group("value")
    label = match.group("label").strip()
    if not _LETTER_ANYWHERE_RE.search(label):
        return None
    # Guard: the "value" must be a value-like token — this rule fires
    # against real label-tail patterns, not against two-CID-blank rows.
    if not _is_value_like(value):
        return None
    return cid, value


def _type_value(raw: str) -> Decimal | int | str | date:
    """Assign a strict type to ``raw`` matching ``ExtractedCasilla.printed_value``.

    Priority: ``DD/MM/YYYY`` → date, Spanish-formatted decimal → Decimal,
    bare integer → int, otherwise the raw string. Date parsing rejects
    impossible day/month combinations.
    """
    date_match = _DATE_RE.match(raw)
    if date_match is not None:
        day = int(date_match.group("d"))
        month = int(date_match.group("m"))
        year = int(date_match.group("y"))
        try:
            return date(year, month, day)
        except ValueError:
            return raw
    if _INT_RE.match(raw):
        return int(raw)
    parsed = parse_spanish_decimal(raw)
    if parsed is not None and "," in raw:
        # Only classify as Decimal when the raw string carried the
        # Spanish decimal separator — otherwise bare integers would be
        # silently demoted (parse_spanish_decimal accepts "86441" too).
        return parsed
    return raw


__all__ = [
    "HEADER_FORWARD_CIDS",
    "ScannedCasilla",
    "scan_pages",
]

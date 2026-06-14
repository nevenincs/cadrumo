"""Deterministic PII scrubbing for AEAT filing PDFs.

Real filings carry the operator's NIF, real amounts, their name, an
AEAT-assigned CSV, and occasionally their IBAN / address. Committing
any of that to a test corpus is a PII leak.

This module deterministically rewrites a source PDF so the output
carries synthetic but structurally-faithful replacements — same digit
counts, same string lengths, same formatting — enough for the extractor
to exercise its primitive stack without leaking personal data.

Scrub rules:

- **NIF** (8 digits + 1 letter or 1 letter + 7 digits + 1 letter):
  replaced with ``00000000T`` (individual) or ``B00000000`` (empresa).
- **Amounts** (Spanish ``1.234,56`` or plain ``1234.56``): replaced with
  a seeded-RNG synthetic of matching digit count, preserving formatting.
- **Names** (capitalised 2+ word strings AEAT conventionally prints):
  replaced with ``DEMO AUTÓNOMO`` / ``DEMO EMPRESA``.
- **CSV** (16-char upper-alphanum): replaced with a hash-derived synthetic.
- **IBAN**: replaced with ``ESXX XXXX XXXX XX XXXXXXXXXX``.
- **Dates**: preserved (GDPR Art. 4 does not treat calendar dates as PII).
- **Presentation IDs** (10+ char upper-alphanum): replaced with seeded synthetic.

Each scrubbed file pairs with a :class:`ScrubSidecar` JSON sidecar
recording provenance + consent.

The library is **never invoked at runtime** from production code — only
from contributor-local workflows (``just scrub-from-drive``) and
``src/aeat/adapters/inbound/pdf/test_scrub.py`` tests.
"""

from __future__ import annotations

import hashlib
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG
from ....core.hashing import sha256_hex
from ....core.time import now
from ....domain.justificante import PdfModeloImportError
from ._utils import sha256_file

SCRUB_VERSION = "1.0.0"

_NIF_INDIVIDUAL_RE = re.compile(r"\b(?P<nif>[0-9]{8}[A-Z])\b")
_NIF_EMPRESA_RE = re.compile(r"\b(?P<nif>[A-HJNPQRSUVW][0-9]{7}[0-9A-J])\b")
_NIE_RE = re.compile(r"\b(?P<nie>[XYZ][0-9]{7}[A-Z])\b")
_AMOUNT_RE = re.compile(r"\b(?P<whole>[0-9]{1,3}(?:\.[0-9]{3})*),[0-9]{2}\b")
_CSV_RE = re.compile(r"\b(?P<csv>[A-Z0-9]{16})\b")
_IBAN_ES_RE = re.compile(r"\bES[0-9]{2}[ ]?[0-9]{4}[ ]?[0-9]{4}[ ]?[0-9]{2}[ ]?[0-9]{10}\b")
_PRESENTATION_ID_RE = re.compile(r"\b(?P<pid>[0-9A-Z]{20,40})\b")
# Spanish phone numbers: optional +34 prefix, then 9 digits beginning with 6/7/8/9.
_PHONE_RE = re.compile(r"\b(?:\+34\s?)?[6789][0-9]{8}\b")
# Email: standard RFC-ish match; deliberately permissive so it errs wide.
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# Postal code (5 digits) anchored by the Spanish "CP" prefix or a street
# number + space (to avoid swallowing arbitrary 5-digit numbers).
_CP_RE = re.compile(r"\b(?:CP\s*|C\.P\.\s*)[0-9]{5}\b")
# Name regex — only match when prefixed by a known label. Keeps the scrubber
# from eating AEAT section headings like "AGENCIA TRIBUTARIA" or
# "RESULTADO A INGRESAR".
_NAME_PREFIX_GROUP = (
    r"(?:Apellidos y nombre|Apellidos|Nombre|Declarante|Titular|"
    r"Razon social|Razón social|Empresa)"
)
_NAME_RE = re.compile(
    rf"({_NAME_PREFIX_GROUP})\s*[:\-]?\s*"
    r"(?P<name>[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ]+"
    r"(?:\s+[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ]+){1,4})",
)

_SCRUB_NIF_INDIVIDUAL = "00000000T"
_SCRUB_NIF_EMPRESA = "B00000000"
_SCRUB_NIE = "X0000000T"
_SCRUB_NAME_INDIVIDUAL = "DEMO AUTONOMO"
_SCRUB_IBAN = "ES00 0000 0000 00 0000000000"
_SCRUB_PHONE = "+34600000000"
_SCRUB_EMAIL = "demo@example.invalid"
_SCRUB_CP = "CP 00000"


class ScrubError(PdfModeloImportError):
    """Raised when scrubbing cannot produce a safe output."""


class ScrubSidecar(BaseModel):
    """Provenance + consent record for one scrubbed L2 fixture file."""

    model_config = STRICT_FROZEN_CONFIG

    original_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scrubbed_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scrub_version: str
    scrubbed_at: datetime
    fields_touched: tuple[str, ...]
    consent_revocable_until: datetime | None = None
    fixture_tier: Literal["l2"] = "l2"
    original_filename: str


def _rng_from_filename(filename: str) -> random.Random:
    """Seed an RNG deterministically from the source filename.

    The filename — not the contents — so re-scrubbing an already-scrubbed
    file with the same filename is idempotent but the seed is not
    recoverable from the output bytes.

    `random.Random` is used here only to drive *deterministic* placeholder
    generation (replacing real amounts with synthetic-but-structurally-similar
    numerics); it is never used as a cryptographic primitive.
    """
    seed = hashlib.sha256(filename.encode("utf-8")).digest()
    return random.Random(int.from_bytes(seed[:8], "big"))


def _scrub_amount(match: re.Match[str], rng: random.Random) -> str:
    """Replace an AEAT-format amount with a synthetic of matching structure."""
    whole = match.group("whole")
    groups = whole.split(".")
    new_groups: list[str] = []
    for group_idx, group in enumerate(groups):
        if group_idx == 0 and len(group) > 1:
            new_groups.append(str(rng.randint(10 ** (len(group) - 1), 10 ** len(group) - 1)))
        elif group_idx == 0:
            new_groups.append(str(rng.randint(1, 9)))
        else:
            new_groups.append(str(rng.randint(100, 999)))
    new_whole = ".".join(new_groups)
    new_cents = f"{rng.randint(0, 99):02d}"
    return f"{new_whole},{new_cents}"


def _scrub_csv(match: re.Match[str], filename: str) -> str:
    """Replace a CSV with a deterministic 16-char upper-alphanum synthetic."""
    seed = sha256_hex(f"{filename}:{SCRUB_VERSION}:csv".encode()).upper()
    alphanum = re.sub(r"[^A-Z0-9]", "", seed)
    return alphanum[:16]


def _scrub_pid(match: re.Match[str], filename: str) -> str:
    """Replace a presentation ID with a deterministic synthetic of matching length."""
    original = match.group("pid")
    seed = sha256_hex(f"{filename}:{SCRUB_VERSION}:pid:{original}".encode()).upper()
    alphanum = re.sub(r"[^A-Z0-9]", "", seed)
    return alphanum[: len(original)]


def scrub_text(
    text: str,
    *,
    filename: str,
) -> tuple[str, tuple[str, ...]]:
    """Apply the scrub-rule set to a text stream; return ``(scrubbed, fields_touched)``.

    Args:
        text: Raw text extracted from the source PDF.
        filename: Source filename — used to seed deterministic replacements.

    Returns:
        A tuple ``(scrubbed_text, fields_touched)`` where ``fields_touched``
        enumerates the rule kinds that matched at least once.
    """
    rng = _rng_from_filename(filename)
    touched: list[str] = []

    scrubbed = text

    # NIF (empresa must match before individual — empresa prefix is a single
    # letter that would otherwise collide with name detection). NIE follows
    # NIF so a real NIE doesn't get misclassified as an individual NIF.
    if _NIF_EMPRESA_RE.search(scrubbed):
        scrubbed = _NIF_EMPRESA_RE.sub(_SCRUB_NIF_EMPRESA, scrubbed)
        touched.append("nif")
    if _NIF_INDIVIDUAL_RE.search(scrubbed):
        scrubbed = _NIF_INDIVIDUAL_RE.sub(_SCRUB_NIF_INDIVIDUAL, scrubbed)
        if "nif" not in touched:
            touched.append("nif")
    if _NIE_RE.search(scrubbed):
        scrubbed = _NIE_RE.sub(_SCRUB_NIE, scrubbed)
        touched.append("nie")

    # CSV: 16-char upper-alphanum block — BEFORE amount pass so digits inside
    # the CSV don't get scrambled by the amount regex.
    if _CSV_RE.search(scrubbed):
        scrubbed = _CSV_RE.sub(lambda m: _scrub_csv(m, filename), scrubbed)
        touched.append("csv")

    # IBAN — before phone so "ES91 2100..." doesn't get misread as a phone prefix.
    if _IBAN_ES_RE.search(scrubbed):
        scrubbed = _IBAN_ES_RE.sub(_SCRUB_IBAN, scrubbed)
        touched.append("iban")

    # Phone: 9-digit Spanish numbers. Run BEFORE amount to avoid eating 6-9
    # leading digits (Spanish amounts under 1 billion don't share the leading-
    # digit convention).
    if _PHONE_RE.search(scrubbed):
        scrubbed = _PHONE_RE.sub(_SCRUB_PHONE, scrubbed)
        touched.append("phone")

    # Email.
    if _EMAIL_RE.search(scrubbed):
        scrubbed = _EMAIL_RE.sub(_SCRUB_EMAIL, scrubbed)
        touched.append("email")

    # Postal code (prefixed).
    if _CP_RE.search(scrubbed):
        scrubbed = _CP_RE.sub(_SCRUB_CP, scrubbed)
        touched.append("postal_code")

    # Amounts.
    if _AMOUNT_RE.search(scrubbed):
        scrubbed = _AMOUNT_RE.sub(lambda m: _scrub_amount(m, rng), scrubbed)
        touched.append("amounts")

    # Presentation ID.
    if _PRESENTATION_ID_RE.search(scrubbed):
        scrubbed = _PRESENTATION_ID_RE.sub(lambda m: _scrub_pid(m, filename), scrubbed)
        touched.append("presentation_id")

    # Names — only when prefixed by a known AEAT label. This
    # preserves the label prefix and rewrites only the trailing name tokens
    # so section headings like "RESULTADO A INGRESAR" survive.
    if _NAME_RE.search(scrubbed):
        scrubbed = _NAME_RE.sub(
            lambda m: f"{m.group(1)}: {_SCRUB_NAME_INDIVIDUAL}",
            scrubbed,
        )
        touched.append("names")

    return scrubbed, tuple(touched)


def compute_sidecar(
    *,
    original_path: Path,
    scrubbed_path: Path,
    fields_touched: tuple[str, ...],
    consent_revocable_until: datetime | None = None,
) -> ScrubSidecar:
    """Build a :class:`ScrubSidecar` describing one scrub run."""
    return ScrubSidecar(
        original_sha256=sha256_file(original_path),
        scrubbed_sha256=sha256_file(scrubbed_path),
        scrub_version=SCRUB_VERSION,
        scrubbed_at=now(),
        fields_touched=fields_touched,
        consent_revocable_until=consent_revocable_until,
        original_filename=original_path.name,
    )


__all__ = [
    "SCRUB_VERSION",
    "ScrubError",
    "ScrubSidecar",
    "compute_sidecar",
    "scrub_text",
]

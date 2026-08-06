"""Residual-identity detection over a sanitised PDF, without the cleartext.

The sanitiser replaces exactly what a ``TokenMap`` names, so an identity nobody
listed passes through untouched. The existing adversarial gate cannot see that:
it asserts the synthetic placeholders LANDED, never that no real identity
SURVIVED, and it justifies the omission with "the adversarial test does NOT have
the cleartext".

Detection needs no cleartext. A residual is any string that

1. matches an identity pattern,
2. passes that pattern's checksum, and
3. is not accounted for by the sidecar's own ``replacements_applied``.

Step 3 is what makes the whole thing work blind: anything identity-shaped that
the sanitiser did not itself write is, by definition, unaccounted for. Step 2 is
what keeps false positives near zero -- an arbitrary eight-digit run inside a
content stream is overwhelmingly unlikely to carry a valid AEAT control letter,
and an arbitrary ``ES``-prefixed run is overwhelmingly unlikely to satisfy
mod-97.

Both checksums are the project's existing authorities, imported rather than
restated: :func:`~cadrumo.core.identity.validate_identity` for NIF/NIE/CIF and
:func:`~cadrumo.core.iban_mod_97` with :data:`~cadrumo.core.IBAN_SHAPE_RE` for
IBAN. Re-deriving either here would be a second authority for the same rule.

HANDLING RULE, ABSOLUTE. A finding NEVER carries the matched text. It carries
the pattern class, the surface it was found on, and a byte offset. Anything that
reads a finding -- an assertion message, a log line, a report -- is therefore
incapable of disclosing the value it found, which is the only safe design for a
detector whose whole purpose is to run over material that may contain real
taxpayer identities.
"""

from __future__ import annotations

import contextlib
import io
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import pikepdf

from .....core import IBAN_SHAPE_RE, iban_mod_97
from .....core.identity import IdentityError, validate_identity


class ResidualKind(StrEnum):
    """Identity pattern classes this scanner recognises.

    Attributes:
        NIF_NIE: Spanish identity document, control-letter verified.
        IBAN: ISO 13616 account number, mod-97 verified.
        EMAIL: RFC-shaped address. No checksum exists, so this is
            advisory-tier -- see :data:`CHECKSUM_VERIFIED_KINDS`.
        PHONE: Spanish-shaped telephone number. No checksum exists, and
            digit runs are dense in PDF content streams, so this is the
            noisiest class and is advisory-tier.
    """

    NIF_NIE = "nif_nie"
    IBAN = "iban"
    EMAIL = "email"
    PHONE = "phone"


#: Kinds whose match is confirmed by an arithmetic check, not shape alone.
#:
#: Only these are safe to BLOCK on. A shape-only pattern cannot distinguish a
#: real leak from a coincidence, and a gate that cries wolf gets silenced --
#: which is how the surviving-identity hole stayed open behind a green gate in
#: the first place. The advisory kinds are still reported, so a reviewer can
#: look, but they do not fail the build on their own.
CHECKSUM_VERIFIED_KINDS: frozenset[ResidualKind] = frozenset({ResidualKind.NIF_NIE, ResidualKind.IBAN})


@dataclass(frozen=True, slots=True)
class ResidualFinding:
    """One identity-shaped, checksum-valid, unaccounted-for match.

    Deliberately carries NO matched text. ``surface`` and ``offset`` are enough
    to locate the match by hand in a controlled setting; nothing that formats a
    finding can leak the value.
    """

    kind: ResidualKind
    surface: str
    offset: int

    def describe(self) -> str:
        """Render the finding for an assertion message, value redacted."""
        return f"{self.kind.value} at {self.surface}:{self.offset}, redacted"


# A NIF/NIE candidate: 8 digits + letter, or [XYZ] + 7 digits + letter. Word
# boundaries keep a longer digit run from yielding a spurious 8-digit window.
_NIF_NIE_CANDIDATE = re.compile(r"(?<![0-9A-Za-z])((?:\d{8}|[XYZxyz]\d{7})[A-Za-z])(?![0-9A-Za-z])")
# An IBAN candidate. Spanish IBANs are ES + 22 digits; the generic ISO shape is
# also accepted so a non-ES account in a bundled statement is not missed.
_IBAN_CANDIDATE = re.compile(r"(?<![0-9A-Za-z])([A-Z]{2}\d{2}[A-Z0-9]{11,30})(?![0-9A-Za-z])")
_EMAIL_CANDIDATE = re.compile(r"(?<![0-9A-Za-z._%+-])([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
# Spanish phone: optional +34/0034, then 6/7/8/9 + 8 digits, allowing separators.
_PHONE_CANDIDATE = re.compile(r"(?<![0-9])((?:\+34|0034)?[\s.-]?[6789](?:[\s.-]?\d){8})(?![0-9])")


def _is_valid_nif_nie(candidate: str) -> bool:
    """True when ``candidate`` passes the AEAT control-letter algorithm."""
    try:
        validate_identity(candidate)
    except IdentityError:
        return False
    return True


def _is_valid_iban(candidate: str) -> bool:
    """True when ``candidate`` is ISO 13616-shaped and mod-97 clean."""
    normalised = candidate.upper()
    if IBAN_SHAPE_RE.match(normalised) is None:
        return False
    try:
        return iban_mod_97(normalised) == 1
    except (ValueError, IndexError):
        return False


_VALIDATORS = {
    ResidualKind.NIF_NIE: (_NIF_NIE_CANDIDATE, _is_valid_nif_nie),
    ResidualKind.IBAN: (_IBAN_CANDIDATE, _is_valid_iban),
    # No checksum exists for these two, so shape IS the whole test and they are
    # advisory-tier by construction.
    ResidualKind.EMAIL: (_EMAIL_CANDIDATE, lambda _candidate: True),
    ResidualKind.PHONE: (_PHONE_CANDIDATE, lambda _candidate: True),
}


def accounted_for_values(sidecar: dict[str, Any]) -> frozenset[str]:
    """Every value the sanitiser recorded itself as having written.

    This is the set that makes cleartext-free detection possible. A synthetic
    placeholder is itself identity-shaped and often checksum-valid by design, so
    without subtracting the sanitiser's own output every scan would drown in its
    own replacements. Comparison is case-folded and separator-free so a
    placeholder written as ``ES91 2100 ...`` still matches a match found as
    ``ES912100...``.
    """
    values: set[str] = set()
    for replacement in sidecar.get("replacements_applied", ()) or ():
        synthetic = replacement.get("synthetic")
        if isinstance(synthetic, str) and synthetic:
            values.add(_canonical(synthetic))
    return frozenset(values)


def _canonical(value: str) -> str:
    """Case-fold and strip separators so equal identities compare equal."""
    return re.sub(r"[\s.\-]", "", value).upper()


def decompressed_streams(pdf_bytes: bytes) -> bytes:
    """Concatenated decompressed content streams of every page."""
    pdf = pikepdf.Pdf.open(io.BytesIO(pdf_bytes))
    chunks: list[bytes] = []
    for page in pdf.pages:
        contents = page.obj.get("/Contents")
        if contents is None:
            continue
        if isinstance(contents, pikepdf.Array):
            chunks.extend(bytes(contents[index].read_bytes()) for index in range(len(contents)))
        else:
            chunks.append(bytes(contents.read_bytes()))
    return b"\n".join(chunks)


def scan_for_residual_identities(
    pdf_bytes: bytes,
    sidecar: dict[str, Any],
    *,
    kinds: frozenset[ResidualKind] | None = None,
) -> tuple[ResidualFinding, ...]:
    """Find identity-shaped, checksum-valid values the sidecar does not account for.

    Args:
        pdf_bytes: The sanitised PDF's bytes.
        sidecar: Its parsed ``.json`` sidecar.
        kinds: Restrict the scan to these pattern classes. Defaults to
            :data:`CHECKSUM_VERIFIED_KINDS`, the blocking tier, because the
            shape-only classes carry no checksum and are advisory.

    Returns:
        Every finding, value-free, sorted for deterministic assertion output.
    """
    selected = CHECKSUM_VERIFIED_KINDS if kinds is None else kinds
    accounted = accounted_for_values(sidecar)
    surfaces: list[tuple[str, bytes]] = [("raw", pdf_bytes)]
    # A file that will not open is a different defect, owned by the structural
    # half of the adversarial gate; the raw-byte surface is still scanned.
    with contextlib.suppress(pikepdf.PdfError, RuntimeError):
        surfaces.append(("stream", decompressed_streams(pdf_bytes)))

    findings: list[ResidualFinding] = []
    for surface_name, payload in surfaces:
        text = payload.decode("latin-1", errors="replace")
        for kind in sorted(selected):
            pattern, is_valid = _VALIDATORS[kind]
            for match in pattern.finditer(text):
                candidate = match.group(1)
                if _canonical(candidate) in accounted:
                    continue
                if not is_valid(candidate):
                    continue
                findings.append(ResidualFinding(kind=kind, surface=surface_name, offset=match.start(1)))
    return tuple(sorted(findings, key=lambda f: (f.surface, f.kind.value, f.offset)))

"""Generic quarterly-declaración extractor (EPIC #305 cluster D).

Every quarterly / monthly AEAT declaración the project supports shares
the same shape: an NIF + ejercicio + período header, then each casilla
as a line with its ID + label + a Spanish-formatted amount.
:class:`GenericDeclaracionExtractor` lets new modelos land as a
7-line subclass defining only the modelo, the template revision, and
the list of casilla IDs.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from .._pdf_import._label_regex import (
    SPANISH_AMOUNT_GROUP,
    TEXT_VALUE_GROUP,
    apply_label_regex,
    parse_spanish_decimal,
)
from .._pdf_import._shared import ExtractedCasilla
from ._errors import DeclaracionParseError
from ._extractor import DeclaracionExtractor
from ._parsers import extract_pages_text
from ._schema import (
    DeclaracionFiling,
    ExtractionStatus,
    ExtractionWarning,
    TemplateRevision,
)

_TAX_ID_RE = re.compile(r"NIF\s*[:\-]?\s*([0-9A-Z]{8,12})", re.IGNORECASE)
_EJERCICIO_RE = re.compile(r"Ejercicio\s*[:\-]?\s*([0-9]{4})", re.IGNORECASE)
_PERIOD_RE = re.compile(r"Per[íi]odo\s*[:\-]?\s*([0-9A-Z]{1,8})", re.IGNORECASE)


class GenericDeclaracionExtractor(DeclaracionExtractor):
    """Line-anchored regex extractor shared across quarterly modelos.

    Subclasses declare:

    - ``template_revision``: one :class:`TemplateRevision` ClassVar.
    - ``casilla_ids``: ordered tuple of casilla IDs the modelo prints
      with Spanish-decimal payloads.
    - (optional) ``text_casilla_ids``: ordered tuple of casilla IDs
      whose payloads are text (fechas, códigos, municipios, régimen,
      S/N flags). Captured as ``str`` into
      :class:`ExtractedCasilla.printed_value`.
    - (optional) ``casilla_width``: width of the casilla-ID prefix
      ``{int(casilla_id):02d}`` by default (Modelo 100 overrides to 4,
      Modelo 200 to 5).
    """

    template_revision: ClassVar[TemplateRevision]
    casilla_ids: ClassVar[tuple[str, ...]]
    text_casilla_ids: ClassVar[tuple[str, ...]] = ()
    text_labels: ClassVar[dict[str, str]] = {}
    """Map ``text_casilla_id → expected label text``. Required when the
    label is multi-word so the truncation-detection pass can calculate
    the expected value-token count. Omitting a label means
    truncation-detection is skipped for that casilla (wave 29 HIGH-3)."""
    casilla_width: ClassVar[int] = 2
    named_field_patterns: ClassVar[dict[str, str]] = {}
    """Map ``field_id → raw regex pattern`` for modelos whose summary
    blocks do NOT print numbered casilla IDs (e.g. 036/037/232/369/720).
    The pattern must include exactly one capture group for the value.
    Wave 27: third primitive path complementing the decimal casilla_ids
    and the text_casilla_ids primitives."""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        decimal_ids = getattr(cls, "casilla_ids", ())
        text_ids = getattr(cls, "text_casilla_ids", ())
        named_ids = tuple(getattr(cls, "named_field_patterns", {}).keys())
        all_ids: tuple[tuple[str, ...], ...] = (
            tuple(decimal_ids),
            tuple(text_ids),
            named_ids,
        )
        # Every pair must be disjoint: the required-set must be unique.
        seen: set[str] = set()
        for group in all_ids:
            overlap = set(group) & seen
            if overlap:
                raise ValueError(
                    f"{cls.__name__}: casilla_ids, text_casilla_ids, and "
                    f"named_field_patterns must be pair-wise disjoint; "
                    f"overlapping IDs: {sorted(overlap)!r}"
                )
            seen.update(group)

        # Wave 46 LOW: pre-compile named_field regexes once at subclass
        # definition rather than on every `extract()` call. The five
        # named-field modelos (036/037/232/369/720) amortise this
        # across every PDF ingested.
        raw_patterns = getattr(cls, "named_field_patterns", {})
        cls._named_field_compiled: dict[str, re.Pattern[str]] = {
            field_id: re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
            for field_id, pattern_str in raw_patterns.items()
        }

    def _compiled_patterns(self) -> dict[str, re.Pattern[str]]:
        width = type(self).casilla_width
        return {
            casilla_id: re.compile(
                rf"(?m)^\s*{int(casilla_id):0{width}d}\s[^\n]{{0,80}}?{SPANISH_AMOUNT_GROUP}",
                re.IGNORECASE,
            )
            for casilla_id in type(self).casilla_ids
        }

    def _compiled_text_patterns(self) -> dict[str, re.Pattern[str]]:
        """Compile patterns that capture the last-token value on the casilla line.

        pdfplumber collapses column-separator whitespace to single spaces,
        so "value to the right of the label" reduces to "the final token
        on the line". Single-token values only — multi-word payloads
        (e.g. ``"La Rioja"``) need the richer bbox-anchored primitive,
        but the truncation-detection (wave 29 HIGH-3) warns when a
        multi-token payload is silently collapsed to its last token.
        """
        width = type(self).casilla_width
        return {
            casilla_id: re.compile(
                rf"(?m)^\s*{int(casilla_id):0{width}d}\s+\S[^\n]{{0,80}}\s{TEXT_VALUE_GROUP}",
                re.IGNORECASE,
            )
            for casilla_id in type(self).text_casilla_ids
        }

    def _compiled_text_line_patterns(self) -> dict[str, re.Pattern[str]]:
        """Patterns that capture the FULL line from the casilla prefix to EOL.

        Used by :meth:`extract` to measure the total token count on the
        casilla's line and compare it against the single-token value
        captured by ``TEXT_VALUE_GROUP``. A significantly higher line
        token count ⇒ the value was likely multi-token and truncated.
        """
        width = type(self).casilla_width
        return {
            casilla_id: re.compile(
                rf"(?m)^\s*{int(casilla_id):0{width}d}\s+(.+?)\s*$",
                re.IGNORECASE,
            )
            for casilla_id in type(self).text_casilla_ids
        }

    def extract(self, pdf_path: Path) -> DeclaracionFiling:
        pages = extract_pages_text(pdf_path)
        full_text = _normalise_pdf_text("\n".join(pages))

        tax_id = _require_match(_TAX_ID_RE, full_text, "tax_id (NIF)")
        ejercicio = _require_match(_EJERCICIO_RE, full_text, "ejercicio")
        period_raw = _require_match(_PERIOD_RE, full_text, "período")
        period = _canonical_period(ejercicio, period_raw)

        hits = apply_label_regex(full_text, self._compiled_patterns())
        text_hits = apply_label_regex(full_text, self._compiled_text_patterns())

        values: list[ExtractedCasilla] = []
        warnings: list[ExtractionWarning] = []
        for casilla_id in type(self).casilla_ids:
            hit = hits.get(casilla_id)
            if hit is None:
                warnings.append(_not_found_warning(casilla_id))
                continue
            parsed = hit.decimal_value or parse_spanish_decimal(hit.raw_value)
            if parsed is None:
                warnings.append(_unparseable_warning(casilla_id, hit.raw_value))
                continue

            confidence = 0.5 if hit.match_count > 1 else 1.0
            if hit.match_count > 1:
                warnings.append(_ambiguous_warning(casilla_id, hit.match_count))

            values.append(
                ExtractedCasilla(
                    casilla_id=casilla_id,
                    printed_value=parsed,
                    source_page=1,
                    source_bbox=None,
                    extraction_confidence=confidence,
                )
            )

        # Text-casilla path: capture free-form string payloads.
        text_line_patterns = self._compiled_text_line_patterns()
        for casilla_id in type(self).text_casilla_ids:
            hit = text_hits.get(casilla_id)
            if hit is None:
                warnings.append(_not_found_warning(casilla_id))
                continue
            confidence = 0.5 if hit.match_count > 1 else 1.0
            if hit.match_count > 1:
                warnings.append(_ambiguous_warning(casilla_id, hit.match_count))

            # Wave 29 HIGH-3: detect likely-truncated multi-word values
            # (e.g. "La Rioja" → captures only "Rioja"). The subclass
            # declares the label text in ``text_labels``; we re-scan the
            # full casilla line, subtract the label's token count, and
            # expect the remaining tokens to equal 1 (the captured value).
            # Extra tokens ⇒ the value was multi-word and got truncated.
            expected_label = type(self).text_labels.get(casilla_id)
            if expected_label is not None:
                line_match = text_line_patterns[casilla_id].search(full_text)
                if line_match is not None:
                    payload = line_match.group(1).strip()
                    label_tokens = len(expected_label.split())
                    line_tokens = len(payload.split())
                    value_tokens = max(line_tokens - label_tokens, 0)
                    if value_tokens > 1:
                        confidence = min(confidence, 0.5)
                        warnings.append(_truncated_text_warning(casilla_id, payload, hit.raw_value))

            values.append(
                ExtractedCasilla(
                    casilla_id=casilla_id,
                    printed_value=hit.raw_value,
                    source_page=1,
                    source_bbox=None,
                    extraction_confidence=confidence,
                )
            )

        # Named-field path: arbitrary regex captures for summary blocks
        # that do NOT print numbered casilla IDs (036/037/232/369/720).
        # Patterns pre-compiled at subclass-definition time (wave 46 LOW).
        compiled_named: dict[str, re.Pattern[str]] = type(self)._named_field_compiled
        for field_id, pattern in compiled_named.items():
            matches = list(pattern.finditer(full_text))
            if not matches:
                warnings.append(_not_found_warning(field_id))
                continue
            confidence = 0.5 if len(matches) > 1 else 1.0
            if len(matches) > 1:
                warnings.append(_ambiguous_warning(field_id, len(matches)))
            captured = matches[0].group(1).strip()
            values.append(
                ExtractedCasilla(
                    casilla_id=field_id,
                    printed_value=captured,
                    source_page=1,
                    source_bbox=None,
                    extraction_confidence=confidence,
                )
            )

        required = (
            tuple(type(self).casilla_ids)
            + tuple(type(self).text_casilla_ids)
            + tuple(type(self).named_field_patterns.keys())
        )
        status = _derive_status(values, required)

        return DeclaracionFiling(
            modelo=type(self).template_revision.modelo,
            period=period,
            ejercicio=ejercicio,
            tax_id=tax_id.upper(),
            template_revision=type(self).template_revision,
            values=tuple(values),
            warnings=tuple(warnings),
            source_pdf_path=pdf_path.resolve(),
            source_pdf_sha256=_sha256_file(pdf_path),
            parsed_at=datetime.now(tz=UTC),
            extraction_status=status,
        )


# Wave 59a H1: restrict the lookarounds to LETTERS (not \w, which also
# matches digits and underscore). AEAT's amount / casilla-ID tokens are
# digits, and an adversarial wrap like ``9-\n10`` would be collapsed
# to ``910`` under a looser regex. Keeping this to Unicode letters
# (A-Z, a-z, accented Latin) and the soft-hyphen / ASCII hyphen pair
# preserves the wave 51 H2 label-stitching use-case without touching
# digit boundaries.
_SOFT_HYPHEN_BREAK_RE = re.compile(r"(?<=[A-Za-zÀ-ÿ])[-­]\n(?=[A-Za-zÀ-ÿ])")


def _normalise_pdf_text(text: str) -> str:
    """Pre-normalise pdfplumber text for the label-regex primitives.

    Wave 51 H2: AEAT's multi-column PDFs hyphenate long labels across
    line breaks (``Cuota reper-\\ncutida``). Stitching the hyphen-newline
    pair back together keeps the label-anchored regex from silently
    missing the casilla. The soft-hyphen character (U+00AD) is also
    rendered as a regular ``-`` by pdfplumber in some PDFs, so strip
    both variants.

    Wave 56 M1: narrowed to require alphanumeric context on BOTH sides
    of the hyphen-newline pair. A leading bullet-style ``-\\nitem``
    (where the hyphen starts a line) no longer collapses into the
    following word — the lookbehind guarantees we only stitch real
    word-continuations.

    Wave 59a H1: lookarounds further tightened to Unicode LETTERS only
    (not digits / underscore). Prevents an adversarial digit wrap
    ``9-\\n10`` from collapsing to ``910``.
    """
    return _SOFT_HYPHEN_BREAK_RE.sub("", text)


def _not_found_warning(casilla_id: str) -> ExtractionWarning:
    return ExtractionWarning(
        casilla_id=casilla_id,
        code="casilla-not-found",
        message={
            "es": f"Casilla {casilla_id}: no se ha encontrado el valor en el PDF.",
            "en": f"Casilla {casilla_id}: value not found in the PDF.",
            "hu": f"{casilla_id} casilla: érték nem található a PDF-ben.",
        },
        primitive_attempted="label_regex",
    )


def _unparseable_warning(casilla_id: str, raw: str) -> ExtractionWarning:
    return ExtractionWarning(
        casilla_id=casilla_id,
        code="value-unparseable",
        message={
            "es": f"Casilla {casilla_id}: el valor {raw!r} no es numérico.",
            "en": f"Casilla {casilla_id}: value {raw!r} is not a number.",
            "hu": f"{casilla_id} casilla: {raw!r} érték nem szám.",
        },
        primitive_attempted="label_regex",
    )


def _truncated_text_warning(
    casilla_id: str,
    full_line_payload: str,
    captured: str,
) -> ExtractionWarning:
    """Emit when the text primitive likely truncated a multi-word value."""
    return ExtractionWarning(
        casilla_id=casilla_id,
        code="text-value-possibly-truncated",
        message={
            "es": (
                f"Casilla {casilla_id}: se capturó {captured!r} pero la línea "
                f"contiene {full_line_payload!r}; el valor real puede ser multi-palabra."
            ),
            "en": (
                f"Casilla {casilla_id}: captured {captured!r} but the line holds "
                f"{full_line_payload!r}; the real value may be multi-word."
            ),
            "hu": (
                f"{casilla_id} casilla: rögzítve {captured!r}, a sor "
                f"{full_line_payload!r}; a valódi érték több szóból állhat."
            ),
        },
        primitive_attempted="label_regex",
    )


def _ambiguous_warning(casilla_id: str, count: int) -> ExtractionWarning:
    return ExtractionWarning(
        casilla_id=casilla_id,
        code="ambiguous-label",
        message={
            "es": f"Casilla {casilla_id}: el patrón coincide {count} veces; se usa la primera.",
            "en": f"Casilla {casilla_id}: label pattern matched {count} times; the first hit was used.",
            "hu": f"{casilla_id} casilla: a minta {count} helyen illeszkedik; az elsőt használjuk.",
        },
        primitive_attempted="label_regex",
    )


def _require_match(pattern: re.Pattern[str], text: str, field: str) -> str:
    match = pattern.search(text)
    if match is None:
        raise DeclaracionParseError(f"could not locate required field: {field}")
    return match.group(1).strip()


def _canonical_period(ejercicio: str, raw_period: str) -> str:
    if re.fullmatch(r"[1-4]T", raw_period, re.IGNORECASE):
        return f"{ejercicio}Q{raw_period[0]}"
    if re.fullmatch(r"(0[1-9]|1[0-2])", raw_period):
        return f"{ejercicio}-{raw_period}"
    if raw_period.upper() == "0A":
        return f"{ejercicio}A"
    return raw_period


def _derive_status(
    values: list[ExtractedCasilla],
    required: tuple[str, ...],
) -> ExtractionStatus:
    # Wave 23 HIGH-1/HIGH-2 closure: header-only extractors (`casilla_ids=()`)
    # must NEVER report COMPLETE — they have no casilla-level data to verify.
    if not required:
        return ExtractionStatus.UNVERIFIABLE
    resolved_ids = {v.casilla_id for v in values}
    required_set = set(required)
    # M1 closure: multi-hit casillas with confidence < 1 count as unresolved
    # for status-derivation purposes — the verification classifier still sees
    # them as EXTRACTION_UNRELIABLE, but the status downgrades accordingly.
    reliable_ids = {v.casilla_id for v in values if v.extraction_confidence >= 1.0}
    if reliable_ids >= required_set:
        return ExtractionStatus.COMPLETE
    coverage = len(resolved_ids) / len(required_set)
    if coverage >= 0.5:
        return ExtractionStatus.PARTIAL
    return ExtractionStatus.FAILED


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


__all__ = ["GenericDeclaracionExtractor"]

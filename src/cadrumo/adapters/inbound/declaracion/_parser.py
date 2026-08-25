"""Public ``parse_declaracion`` entry points for declaration-copy PDFs.

Parsing is registry-profile-driven: template detection resolves the
modelo/year/revision coordinate, then a
:class:`~domain.calculations.registry.RegistrySnapshot` supplies the single
``declaracion_pdf``
:class:`~domain.calculations.registry._schema_extraction.ExtractionProfileDefinition`
used to extract casillas. There is deliberately no per-modelo extractor class
registry here.

When callers do not supply a snapshot, the parser loads one through
:class:`~domain.calculations.registry.ValidatedRegistryAuthority`. The
snapshot's :class:`~domain.calculations.registry.ModeloRevision` owns the
canonical casilla declarations and the returned
:class:`~adapters.inbound.declaracion.InboundDeclaracionObservation` stamps the
exact :class:`~domain.calculations.registry.RegistrySnapshotRef`. The bytes
entry point keeps decrypted live-read PDF content in memory rather than
materialising a plaintext temporary file.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from cadrumo.domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_extraction import (
    BboxAnchorSpec,
    ExtractionProfileDefinition,
    ExtractionTargetDefinition,
)
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef

from ....core import (
    CasillaId,
    Period,
    RegistryAuthorityGrade,
    fold_diacritics,
    is_administrative_period_token,
)
from ....core.decimal import european_thousands_reading_is_ambiguous
from ....core.hashing import sha256_hex
from ....core.identity import IdentityError, validate_spanish_tax_id
from ....core.logging import get_logger
from ....core.resources import bundled_path
from ....core.time import now
from ....domain.calculations.registry.authority import ValidatedRegistryAuthority
from ....domain.calculations.registry.casilla_membership import casillas_by_id
from ....domain.calculations.registry.errors import RegistrySnapshotError
from ..pdf import (
    PRESENTADOR_NIF_LABEL,
    SPANISH_AMOUNT_GROUP,
    TEXT_VALUE_GROUP,
    ExtractedCasilla,
    parse_spanish_decimal,
    sha256_file,
    source_pdf_reference_path,
)
from ._detect import detect_template_revision, detect_template_revision_from_pages
from ._parsers import extract_pages_text, extract_pages_text_from_bytes
from ._schema import InboundDeclaracionObservation, TemplateRevision
from .errors import DeclaracionParseError, TemplateNotDetectedError

# ADAPTER-INTERNAL-ALIAS-RATIONALE-PDFWORD: pdfplumber's Page.extract_words()
# returns dicts whose full key-set varies by version and page content.  A
# TypedDict would require listing every optional key with total=False and
# would break silently on upstream pdfplumber releases.  Moving to
# cadrumo.core._types is unwarranted because _PdfWord is consumed exclusively
# within this adapter module.  This alias is correct-by-containment: it
# documents the caller's expectations without over-constraining the library
# boundary.
_PdfWord = dict[str, Any]

_logger = get_logger(__name__)
_INPUT_PDF_SOURCE_LABEL = "<input-pdf>"


def _pdf_word_text(word: _PdfWord) -> str:
    """Return the textual value required from a pdfplumber word."""
    value = word.get("text")
    if not isinstance(value, str):
        raise DeclaracionParseError("pdf word is missing textual content")
    return value


def _pdf_word_float(word: _PdfWord, key: str) -> float:
    """Return a numeric pdfplumber word coordinate as a concrete float."""
    value = word.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    raise DeclaracionParseError(f"pdf word field {key!r} is not numeric")


# AEAT tax-id shape: a natural-person NIF/NIE or a legal-entity CIF. Held here
# as one fragment so the label-order variants below cannot drift apart, and so
# accepting a new label rendering can never widen the accepted value.
_TAX_ID_GROUP = r"(?P<tax_id>(?:[A-Z][0-9]{7}[0-9A-Z]|[0-9]{8}[A-Z]))"

_TAX_ID_RE = re.compile(
    rf"\b{PRESENTADOR_NIF_LABEL}\s*[:\-]\s*{_TAX_ID_GROUP}\b",
    re.IGNORECASE,
)
# 2021-2022 corpus PDFs use a column-split layout where pdfplumber's left-right
# traversal lifts the tax ID onto the line immediately BEFORE its label rather
# than after it. The leading word boundary keeps the value class from matching
# the tail of a longer alphanumeric run (the expediente/referencia number
# "202139013520268G" ends in a NIF-shaped "13520268G").
_TAX_ID_BEFORE_LABEL_RE = re.compile(
    rf"\b{_TAX_ID_GROUP}\s*\n\s*{PRESENTADOR_NIF_LABEL}\s*[:\-]",
    re.IGNORECASE,
)
_PERIOD_RE = re.compile(
    r"\bPer[ií]odo\s*[:\-]?\s*(?P<period>[1-4]T|0A|[0-1][0-9]|[A-Z0-9]{1,4})\b",
    re.IGNORECASE,
)
_DECLARANT_ROW_RE = re.compile(
    r"\b(?P<tax_id>[XYZ]?[0-9]{7,8}[A-Z])\s+(?P<year>20[0-9]{2})\s+(?P<period>[1-4]T|0A|[0-1][0-9])\b",
    re.IGNORECASE,
)


def parse_declaracion(
    pdf_path: Path,
    *,
    modelo_override: str | None = None,
    template_revision_override: str | None = None,
    año_override: int | None = None,
    period_override: str | None = None,
    extraction_profile_id: str | None = None,
    registry_snapshot: RegistrySnapshot | None = None,
    registry_root: Path | None = None,
    source_root: Path | None = None,
) -> InboundDeclaracionObservation:
    """Parse an AEAT declaración PDF into a :class:`InboundDeclaracionObservation`.

    Use this filesystem entry point when the declaration copy is already on
    disk. The observation carries a digest-backed PDF source reference and a
    :class:`RegistrySnapshotRef` so downstream filing checks can identify the
    registry coordinate that interpreted the printed values.

    Args:
        pdf_path: Path to the declaración PDF.
        modelo_override: Explicit modelo identifier (skips detection).
        template_revision_override: Explicit revision string (skips detection).
        año_override: Explicit four-digit tax year (skips detection).
        period_override: Explicit printed period when the PDF text does
            not expose a stable period marker.
        extraction_profile_id: Registry extraction profile to use when
            the selected snapshot contains more than one declaration-PDF
            profile.
        registry_snapshot: Pre-built validated :class:`RegistrySnapshot`. When
            omitted, the parser loads the committed registry and builds
            one from the detected modelo, tax year, and period.
        registry_root: Optional registry TOML root used when
            ``registry_snapshot`` is omitted.
        source_root: Optional source root used for source integrity
            checks while building a snapshot.

    Returns:
        A strict :class:`InboundDeclaracionObservation` populated with the extracted
        casillas, warnings, and provenance metadata.

    Raises:
        DeclaracionParseError: When text extraction, template/period detection,
            registry snapshot loading, or registry-profile extraction fails.

    """
    path = Path(pdf_path)
    pages = extract_pages_text(path)
    source_pdf_sha256 = sha256_file(path)
    return _parse_declaracion_pages(
        pages=pages,
        source_path=path.resolve(),
        source_pdf_path=source_pdf_reference_path(source_pdf_sha256),
        source_pdf_sha256=source_pdf_sha256,
        modelo_override=modelo_override,
        template_revision_override=template_revision_override,
        año_override=año_override,
        period_override=period_override,
        extraction_profile_id=extraction_profile_id,
        registry_snapshot=registry_snapshot,
        registry_root=registry_root,
        source_root=source_root,
    )


def parse_declaracion_bytes(
    pdf_bytes: bytes,
    *,
    source_label: str = "in-memory declaracion PDF",
    modelo_override: str | None = None,
    template_revision_override: str | None = None,
    año_override: int | None = None,
    period_override: str | None = None,
    extraction_profile_id: str | None = None,
    registry_snapshot: RegistrySnapshot | None = None,
    registry_root: Path | None = None,
    source_root: Path | None = None,
) -> InboundDeclaracionObservation:
    """Parse declaración PDF bytes without writing them to a plaintext temp file.

    This is the live-read path for already-decrypted artefacts. Page text and
    bbox word extraction operate on the supplied bytes, and the observation uses
    a digest-derived source reference instead of a real filesystem path.

    Args:
        pdf_bytes: Raw PDF bytes to parse.
        source_label: Label identifying the in-memory source for log messages.
        modelo_override: Explicit modelo identifier (skips detection).
        template_revision_override: Explicit revision string (skips detection).
        año_override: Explicit four-digit tax year (skips detection).
        period_override: Explicit printed period when the PDF text does
            not expose a stable period marker.
        extraction_profile_id: Registry extraction profile to use when
            the selected snapshot contains more than one declaration-PDF
            profile.
        registry_snapshot: Pre-built validated :class:`RegistrySnapshot`. When
            omitted, the parser loads the committed registry and builds
            one from the detected modelo, tax year, and period.
        registry_root: Optional registry TOML root used when
            ``registry_snapshot`` is omitted.
        source_root: Optional source root used for source integrity
            checks while building a snapshot.

    Returns:
        A :class:`InboundDeclaracionObservation` populated with the extracted casillas,
        warnings, and provenance metadata.

    Raises:
        DeclaracionParseError: When text extraction, template/period detection,
            registry snapshot loading, or registry-profile extraction fails.
    """
    pages = extract_pages_text_from_bytes(pdf_bytes, source_label=source_label)
    digest = sha256_hex(pdf_bytes)
    source_pdf_path = source_pdf_reference_path(digest)
    return _parse_declaracion_pages(
        pages=pages,
        source_path=source_pdf_path,
        source_pdf_path=source_pdf_path,
        source_pdf_sha256=digest,
        pdf_bytes=pdf_bytes,
        modelo_override=modelo_override,
        template_revision_override=template_revision_override,
        año_override=año_override,
        period_override=period_override,
        extraction_profile_id=extraction_profile_id,
        registry_snapshot=registry_snapshot,
        registry_root=registry_root,
        source_root=source_root,
    )


def _parse_declaracion_pages(
    *,
    pages: tuple[str, ...],
    source_path: Path,
    source_pdf_path: Path,
    source_pdf_sha256: str,
    modelo_override: str | None,
    template_revision_override: str | None,
    año_override: int | None,
    period_override: str | None,
    extraction_profile_id: str | None,
    registry_snapshot: RegistrySnapshot | None,
    registry_root: Path | None,
    source_root: Path | None,
    pdf_bytes: bytes | None = None,
) -> InboundDeclaracionObservation:
    """Assemble the shared registry-grounded parse result.

    Both public entry points converge here after obtaining per-page text. The
    routine resolves the :class:`TemplateRevision`, filing period,
    :class:`RegistrySnapshot`, selected ``declaracion_pdf`` profile, tax ID, and
    extracted :class:`ExtractedCasilla` tuple before stamping the
    :class:`RegistrySnapshotRef` on the observation.
    """
    text = "\n".join(pages)

    template = _resolve_template(
        path=source_path,
        pages=pages,
        modelo_override=modelo_override,
        template_revision_override=template_revision_override,
        año_override=año_override,
    )
    period = _resolve_period(text, period_override=period_override)
    snapshot = registry_snapshot or _load_registry_snapshot(
        template=template,
        period=period,
        registry_root=registry_root,
        source_root=source_root,
    )
    _validate_snapshot_matches_template(snapshot, template)
    profile = _select_extraction_profile(snapshot, extraction_profile_id=extraction_profile_id)
    tax_id = _extract_tax_id(text)
    values = _extract_profile_values(
        pages,
        profile,
        revision=snapshot.revision,
        source_pdf_path=source_path,
        pdf_bytes=pdf_bytes,
    )
    _logger.debug(
        "parse_declaracion: source=<input-pdf> modelo=%s año=%s period=%s revision=%s profile=%s",
        template.modelo,
        template.año,
        period,
        template.revision,
        profile.id,
    )

    snapshot_ref = RegistrySnapshotRef(
        modelo=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
        modelo_year=snapshot.filing_year,
        period=snapshot.period,
    )
    return InboundDeclaracionObservation(
        modelo=template.modelo,
        period=_filing_period_for_observation(template.año, period),
        ejercicio=str(template.año),
        tax_id=tax_id,
        template_revision=template,
        registry_snapshot_ref=snapshot_ref,
        values=values,
        warnings=(),
        extraction_profile_id=profile.id,
        extraction_profile_provisional=profile.provisional_pending_specimen,
        source_pdf_path=source_pdf_path,
        source_pdf_sha256=source_pdf_sha256,
        parsed_at=now(),
    )


def _filing_period_for_observation(filing_year: int, registry_selector: str) -> Period:
    """Resolve the parser's registry selector to the stored filing period.

    An administrative censo selector names a registration event, not a period a
    filing occupies, so it is stored as ``AD-HOC``. Membership is asked of
    :func:`~cadrumo.core.is_administrative_period_token` rather than a local set:
    a hand-copied set here already drifted two members behind the authority, and
    the drift was invisible because the two it lacked belong to a modelo that
    ships no extraction profile yet.

    Accents are folded before the question is asked because AEAT prints these
    tokens in correct Spanish (``MODIFICACIÓN``, ``COMUNICACIÓN``, ``VARIACIÓN``)
    while the registry declares them unaccented. Folding every token is safe: the
    rest of the vocabulary is ASCII, so the fold is a no-op there.
    """
    normalized = fold_diacritics(registry_selector).strip().upper()
    if is_administrative_period_token(normalized):
        return Period.from_year_and_code(filing_year, "AD-HOC")
    return Period.from_year_and_code(filing_year, "0A" if normalized == str(filing_year) else normalized)


def _resolve_template(
    *,
    path: Path,
    pages: tuple[str, ...] | None = None,
    modelo_override: str | None,
    template_revision_override: str | None,
    año_override: int | None,
) -> TemplateRevision:
    """Resolve a :class:`TemplateRevision` from overrides plus detection.

    Override precedence: when modelo, año, AND revision are all
    supplied, detection is skipped entirely. Otherwise the detected
    triple is reconciled against any partial override; conflicts raise
    :exc:`DeclaracionParseError`.

    Args:
        path: Path to the source PDF.
        pages: Optional tuple of page-number strings used to restrict text
            extraction to specific pages; ``None`` extracts all pages.
        modelo_override: Explicit modelo identifier or ``None``.
        template_revision_override: Explicit revision string or ``None``.
        año_override: Explicit four-digit tax year or ``None``.

    Returns:
        The resolved :class:`TemplateRevision`.

    Raises:
        TemplateNotDetectedError: When detection fails and the caller did not supply both
            modelo and año.
        DeclaracionParseError: When an override conflicts with the detected metadata.
    """
    if modelo_override and año_override and template_revision_override:
        return TemplateRevision(
            modelo=modelo_override,
            año=año_override,
            revision=template_revision_override,
            detected_from="explicit_override",
        )

    detected = detect_template_revision_from_pages(pages) if pages is not None else detect_template_revision(path)
    if detected is None and not (modelo_override and año_override):
        raise TemplateNotDetectedError(
            translated_message="adapters.inbound.declaracion.errors.template_not_detected",
            context={"path": _INPUT_PDF_SOURCE_LABEL},
        )

    if detected is None:
        assert modelo_override and año_override  # narrowed by the check above
        return TemplateRevision(
            modelo=modelo_override,
            año=año_override,
            revision=template_revision_override or f"{año_override}.01",
            detected_from="explicit_override",
        )

    if modelo_override and modelo_override != detected.modelo:
        raise DeclaracionParseError(
            translated_message="adapters.inbound.declaracion.errors.modelo_conflict",
            context={"modelo": modelo_override, "detected": detected.modelo},
        )
    if año_override and año_override != detected.año:
        raise DeclaracionParseError(
            translated_message="adapters.inbound.declaracion.errors.year_conflict",
            context={"year": año_override, "detected": detected.año},
        )

    if template_revision_override:
        return TemplateRevision(
            modelo=detected.modelo,
            año=detected.año,
            revision=template_revision_override,
            detected_from="explicit_override",
        )
    return detected


def _resolve_period(text: str, *, period_override: str | None) -> str:
    if period_override:
        return period_override.upper()
    match = _PERIOD_RE.search(text)
    if match is None:
        raise DeclaracionParseError(
            translated_message="adapters.inbound.declaracion.errors.period_unresolved",
        )
    period = match.group("period")
    if not isinstance(period, str):
        raise DeclaracionParseError(
            translated_message="adapters.inbound.declaracion.errors.period_unresolved",
        )
    return period.upper()


def _extract_tax_id(text: str) -> str:
    match = _TAX_ID_RE.search(text)
    if match is not None:
        return _validated_tax_id(re.sub(r"\s+", "", match.group("tax_id").strip().rstrip(".")))
    before_match = _TAX_ID_BEFORE_LABEL_RE.search(text)
    if before_match is not None:
        return _validated_tax_id(before_match.group("tax_id"))
    row_match = _DECLARANT_ROW_RE.search(text)
    if row_match is not None:
        return _validated_tax_id(row_match.group("tax_id"))
    raise DeclaracionParseError(
        translated_message="adapters.inbound.declaracion.errors.tax_id_unresolved",
    )


def _validated_tax_id(candidate: str) -> str:
    """Return only a checksum-valid filing identity from a matched PDF label."""
    try:
        return validate_spanish_tax_id(candidate)
    except IdentityError as exc:
        raise DeclaracionParseError(
            translated_message="adapters.inbound.declaracion.errors.tax_id_unresolved",
        ) from exc


def _load_registry_snapshot(
    *,
    template: TemplateRevision,
    period: str,
    registry_root: Path | None,
    source_root: Path | None,
) -> RegistrySnapshot:
    root = registry_root or bundled_path("registry", "aeat")
    authority = ValidatedRegistryAuthority.load(root, source_root=source_root or bundled_path())
    try:
        return authority.snapshot(
            template.modelo,
            filing_year=template.año,
            period=period,
            grade=RegistryAuthorityGrade.APPLICABILITY,
        )
    except RegistrySnapshotError as exc:
        raise DeclaracionParseError(
            translated_message="adapters.inbound.declaracion.errors.registry_snapshot_required",
            context={
                "modelo": template.modelo,
                "year": template.año,
                "period": period,
                "error": str(exc),
            },
        ) from exc


def _validate_snapshot_matches_template(snapshot: RegistrySnapshot, template: TemplateRevision) -> None:
    if snapshot.modelo.id != template.modelo:
        raise DeclaracionParseError(
            translated_message="adapters.inbound.declaracion.errors.snapshot_modelo_conflict",
            context={
                "snapshot_modelo": snapshot.modelo.id,
                "detected": template.modelo,
            },
        )


def _select_extraction_profile(
    snapshot: RegistrySnapshot,
    *,
    extraction_profile_id: str | None,
) -> ExtractionProfileDefinition:
    """Select the registry-owned ``declaracion_pdf`` extraction profile.

    A supplied ``extraction_profile_id`` must match a declaration-PDF profile in
    the snapshot. Otherwise the snapshot must expose exactly one matching
    profile, preserving the generic parser shape: registry data
    selects per-modelo extraction behavior, not Python extractor classes.
    """
    profiles = tuple(
        profile
        for profile in snapshot.extraction_profiles.values()
        if profile.surface == "declaracion_pdf" and "declaration_pdf" in profile.accepted_artefact_kinds
    )
    if extraction_profile_id:
        for profile in profiles:
            if profile.id == extraction_profile_id:
                return profile
        raise DeclaracionParseError(
            translated_message="adapters.inbound.declaracion.errors.profile_unavailable",
            context={
                "profile": extraction_profile_id,
                "modelo": snapshot.modelo.id,
            },
        )
    if len(profiles) != 1:
        available = ", ".join(sorted(profile.id for profile in profiles)) or "none"
        raise DeclaracionParseError(
            translated_message="adapters.inbound.declaracion.errors.profile_count_invalid",
            context={"modelo": snapshot.modelo.id, "available": available},
        )
    return profiles[0]


@dataclass(frozen=True, slots=True)
class _TargetClassification:
    """One target's extraction outcome: a value, or a single failure category.

    Exactly one field is populated. ``value`` carries the extracted casilla on
    success; otherwise one of ``missing`` / ``malformed`` / ``ambiguous`` names
    the failed casilla id.
    """

    value: ExtractedCasilla | None = None
    missing: CasillaId | None = None
    malformed: CasillaId | None = None
    ambiguous: CasillaId | None = None


_STRICT_PRINTED_AMOUNT_RE = re.compile(rf"^{SPANISH_AMOUNT_GROUP}$")
"""A fully-formed AEAT-printed monetary amount, anchored end to end.

``SPANISH_AMOUNT_GROUP`` requires the mandatory ``,NN`` decimal tail that AEAT
prints on every populated money box.
"""


def _is_own_box_number_of_blank_box(raw: str, printed_number: str | None) -> bool:
    """Whether ``raw`` is the target's own box number left by a BLANK box.

    ``named_label`` captures the last token on the line. On a real AEAT form a
    BLANK money box leaves its own printed box number as that last token (e.g.
    ``"...aplicadas en este periodo ......... 78"`` for box 78), and
    :func:`parse_spanish_decimal` is deliberately permissive enough to read that
    ``78`` as ``Decimal("78")`` - fabricating a value the filing never declared.

    The discriminator is deliberately narrow: only a token identical to the
    target's OWN printed box number is refused. A populated money box prints the
    ``,NN`` tail (``"3.000,00"``), and a bare integer that is NOT the box number
    is a genuine value - AEAT prints an explicit bare ``0`` in a zero box
    (compensacion boxes 87 and 110), and count-valued targets such as the
    ``total-perceptores`` of the informativas legitimately print a bare count.
    Keying on the box number keeps all three admissible while refusing the one
    token that can only be a label.
    """
    if printed_number is None:
        return False
    token = raw.strip()
    if _STRICT_PRINTED_AMOUNT_RE.match(token):
        return False
    return token == printed_number.strip()


def _classify_target(
    target: ExtractionTargetDefinition,
    *,
    pages: tuple[str, ...],
    pages_words: tuple[list[_PdfWord], ...] | None,
    numeric_anchors: dict[CasillaId, str],
    printed_box_numbers: dict[CasillaId, str] | None = None,
) -> _TargetClassification:
    """Resolve one target's hits into a value or a failure category.

    Mirrors the per-target arm of :func:`_extract_profile_values`: bbox targets
    without word data are ``missing``; no hits is ``missing``; multiple hits is
    ``ambiguous``; an unparseable amount is ``malformed``; otherwise the captured
    value is returned as an :class:`ExtractedCasilla`.
    """
    casilla_id = target.casilla_id
    printed_number = (printed_box_numbers or {}).get(casilla_id)
    hits = _target_hits(
        target,
        pages=pages,
        pages_words=pages_words,
        numeric_anchors=numeric_anchors,
        printed_number=printed_number,
    )
    if hits is None or not hits:
        return _TargetClassification(missing=casilla_id)
    if len(hits) > 1:
        return _TargetClassification(ambiguous=casilla_id)
    page_number, raw_value = hits[0]
    if target.value_kind != "amount":
        # "text" and "enum" value kinds: store the raw captured token as-is.
        parsed: Decimal | str | None = raw_value
    else:
        # named_label captures the last token on the line, which for a BLANK box
        # on a real AEAT render is the box's own printed number. Such a box is
        # absent, not corrupt, so it is reported missing (coverage decides
        # whether that is tolerable) rather than malformed (which raises hard).
        if target.match_strategy == "named_label" and _is_own_box_number_of_blank_box(raw_value, printed_number):
            return _TargetClassification(missing=casilla_id)
        # Only the `casilla` strategy's regex embeds SPANISH_AMOUNT_GROUP and so
        # guarantees the ``,NN`` tail that makes a printed Spanish amount
        # unambiguous. `bbox_anchored` takes the raw PDF word text and
        # `named_label` takes the line's last word, both unvalidated, so a bare
        # ``1.234`` can reach the permissive parser here and decode as one point
        # two three four -- a filed box read a thousandfold small. Refuse the
        # two-way reading rather than guess; the box is reported malformed, which
        # is what an unreadable printed value is.
        if european_thousands_reading_is_ambiguous(raw_value.strip()):
            return _TargetClassification(malformed=casilla_id)
        parsed = parse_spanish_decimal(raw_value)
        if parsed is None:
            return _TargetClassification(malformed=casilla_id)
    return _TargetClassification(
        value=ExtractedCasilla(
            casilla_id=casilla_id,
            printed_value=parsed,
            source_page=page_number,
            source_bbox=None,
            extraction_confidence=1.0,
        ),
    )


def _target_hits(
    target: ExtractionTargetDefinition,
    *,
    pages: tuple[str, ...],
    pages_words: tuple[list[_PdfWord], ...] | None,
    numeric_anchors: dict[CasillaId, str],
    printed_number: str | None,
) -> list[tuple[int, str]] | None:
    """Find the target's hits with the strategy its definition declares.

    Returns ``None`` when a ``bbox_anchored`` target has no word data to
    resolve against (bytes-mode or a missing file), which the caller treats
    as a missing target rather than a failure.
    """
    if target.match_strategy == "bbox_anchored":
        if pages_words is None:
            return None
        return _find_bbox_casilla_hits(pages_words, target)
    if target.match_strategy == "named_label" and target.value_kind == "amount" and pages_words is not None:
        return _find_named_label_word_hits(pages_words, target, printed_number=printed_number)
    return _find_casilla_hits(pages, target, numeric_anchors=numeric_anchors)


_LINE_Y_TOLERANCE: float = 3.0
"""Maximum vertical distance (points) between words treated as one printed line."""


def _words_by_line(words: list[_PdfWord]) -> list[list[_PdfWord]]:
    """Group one page's words into printed lines, each sorted left to right."""
    lines: list[tuple[float, list[_PdfWord]]] = []
    for word in sorted(words, key=lambda w: (float(w["top"]), float(w["x0"]))):
        top = float(word["top"])
        for line_top, line in lines:
            if abs(line_top - top) <= _LINE_Y_TOLERANCE:
                line.append(word)
                break
        else:
            lines.append((top, [word]))
    return [sorted(line, key=lambda w: float(w["x0"])) for _top, line in lines]


def _find_named_label_word_hits(
    pages_words: tuple[list[_PdfWord], ...],
    target: ExtractionTargetDefinition,
    *,
    printed_number: str | None,
) -> list[tuple[int, str]]:
    """Find a ``named_label`` amount by reading the line's WORDS, not its text.

    The text layer merges glyph runs by horizontal position, so where AEAT prints
    the box number in a smaller font overlapping the amount's own span -- Modelo
    100 does this on every money box -- the two arrive as one token whose digits
    interleave. The correct amount is then not a substring of that token at any
    position, so no rule applied to the text can recover it.

    Word extraction requests the font size, which separates the two runs because
    pdfplumber will not join words of differing size. This reads the line from
    that word list instead, so the amount and the box number stay distinct.

    The value is the line's last word, as on the text path. When that word is the
    target's own printed box number the box is either blank or the layout prints
    the number after the value; the preceding word decides which, and it is taken
    only when it is a well-formed printed amount. Otherwise the box number is
    returned unchanged so the blank-box guard still sees it and reports the target
    absent.
    """
    label = target.label_pattern or re.escape(target.casilla_id)
    pattern = re.compile(rf"^\s*{label}", re.IGNORECASE)

    hits: list[tuple[int, str]] = []
    for page_index, words in enumerate(pages_words, start=1):
        if not words:
            continue
        for line in _words_by_line(words):
            text = " ".join(word["text"] for word in line)
            match = pattern.search(text)
            if match is None:
                continue
            if not text[match.end() :].strip():
                # The label with nothing after it is a section heading, not a
                # populated row. The text path excludes these by requiring a
                # trailing value token; without the same condition a form that
                # prints its heading in capitals matches twice and the target is
                # reported ambiguous. Modelo 100 prints two such headings.
                continue
            hits.append((page_index, _named_label_line_value(line, printed_number=printed_number)))
    return hits


def _named_label_line_value(line: list[_PdfWord], *, printed_number: str | None) -> str:
    """Pick the value word from one matched ``named_label`` line.

    The value is the line's last word, as on the text path. When that word is
    the target's own printed box number the box is either blank or the layout
    prints the number after the value; the preceding word decides which, and
    it is taken only when it is a well-formed printed amount. Otherwise the
    box number is returned unchanged so the blank-box guard still sees it and
    reports the target absent.
    """
    raw = _pdf_word_text(line[-1]).strip()
    if printed_number is None or raw != printed_number.strip() or len(line) < 2:
        return raw
    preceding = _pdf_word_text(line[-2]).strip()
    return preceding if _STRICT_PRINTED_AMOUNT_RE.match(preceding) else raw


def _raise_extraction_failed(
    profile: ExtractionProfileDefinition,
    *,
    missing: list[CasillaId],
    malformed: list[CasillaId],
    ambiguous: list[CasillaId],
    coverage: Decimal,
) -> None:
    """Raise the degraded-extraction error with a human-readable detail summary."""
    details = []
    if missing:
        details.append(f"missing={','.join(missing)}")
    if malformed:
        details.append(f"malformed={','.join(malformed)}")
    if ambiguous:
        details.append(f"ambiguous={','.join(ambiguous)}")
    details.append(f"coverage={coverage}")
    raise DeclaracionParseError(
        translated_message="adapters.inbound.declaracion.errors.extraction_failed",
        context={"profile": profile.id, "details": "; ".join(details)},
        missing=tuple(missing),
        malformed=tuple(malformed),
        ambiguous=tuple(ambiguous),
        coverage=coverage,
    )


def _extract_profile_values(
    pages: tuple[str, ...],
    profile: ExtractionProfileDefinition,
    *,
    revision: ModeloRevision,
    source_pdf_path: Path | None = None,
    pdf_bytes: bytes | None = None,
) -> tuple[ExtractedCasilla, ...]:
    """Extract profile targets into observed casilla values.

    The :class:`ExtractionProfileDefinition` contributes the target list,
    allowed match strategies, and minimum coverage threshold. Bbox extraction
    prefers in-memory ``pdf_bytes`` for privacy, falls back to a real source file
    when only a path is available, and reports malformed or ambiguous targets as
    hard parse failures.
    """
    # Load word-position data lazily, for the two strategies that need it:
    # bbox_anchored resolves entirely in word space, and named_label amount
    # targets read the line's words so a box number printed over the amount stays
    # a separate token. Prefer in-memory bytes so decrypted declaration PDFs never
    # touch disk; fall back to a real source file only when bytes are not
    # supplied. A profile with neither kind of target never pays for the pass.
    pages_words = _load_pages_words(profile, source_pdf_path=source_pdf_path, pdf_bytes=pdf_bytes)
    numeric_anchors = _numeric_casilla_anchors(profile, revision)
    printed_box_numbers = _printed_box_numbers(profile, revision)

    outcomes = _partition_target_outcomes(
        _classify_target(
            target,
            pages=pages,
            pages_words=pages_words,
            numeric_anchors=numeric_anchors,
            printed_box_numbers=printed_box_numbers,
        )
        for target in profile.target_casillas
    )

    coverage = Decimal(len(outcomes.values)) / Decimal(len(profile.target_casillas))
    # Raise when extraction quality is degraded (ambiguous or malformed hits) or when
    # coverage falls below the configured threshold.  Missing casillas are acceptable
    # as long as coverage meets the threshold — partial filings legitimately omit
    # zero or not-applicable casillas (e.g. M130 real-corpus PDFs).
    if outcomes.ambiguous or outcomes.malformed or coverage < profile.min_coverage:
        _raise_extraction_failed(
            profile,
            missing=outcomes.missing,
            malformed=outcomes.malformed,
            ambiguous=outcomes.ambiguous,
            coverage=coverage,
        )
    return tuple(outcomes.values)


def _load_pages_words(
    profile: ExtractionProfileDefinition,
    *,
    source_pdf_path: Path | None,
    pdf_bytes: bytes | None,
) -> tuple[list[_PdfWord], ...] | None:
    """Load word-position data, but only for a profile whose targets need it.

    ``bbox_anchored`` resolves entirely in word space, and ``named_label``
    amount targets read the line's words so a box number printed over the
    amount stays a separate token. Prefers in-memory bytes so decrypted
    declaration PDFs never touch disk, falling back to a real source file
    only when bytes are not supplied. A profile with neither kind of target
    never pays for the pass.
    """
    needs_words = any(
        target.match_strategy == "bbox_anchored"
        or (target.match_strategy == "named_label" and target.value_kind == "amount")
        for target in profile.target_casillas
    )
    if not needs_words:
        return None
    if pdf_bytes is not None:
        return _extract_pages_words_from_bytes(pdf_bytes)
    if source_pdf_path is not None and source_pdf_path.is_file():
        return _extract_pages_words(source_pdf_path)
    return None


@dataclass(frozen=True)
class _ExtractionOutcomes:
    """Every target's classification, sorted into the four report buckets."""

    values: list[ExtractedCasilla]
    missing: list[CasillaId]
    malformed: list[CasillaId]
    ambiguous: list[CasillaId]


def _partition_target_outcomes(classifications: Iterable[_TargetClassification]) -> _ExtractionOutcomes:
    """Sort each target's classification into its report bucket."""
    outcomes = _ExtractionOutcomes(values=[], missing=[], malformed=[], ambiguous=[])
    for outcome in classifications:
        if outcome.value is not None:
            outcomes.values.append(outcome.value)
        elif outcome.malformed is not None:
            outcomes.malformed.append(outcome.malformed)
        elif outcome.ambiguous is not None:
            outcomes.ambiguous.append(outcome.ambiguous)
        elif outcome.missing is not None:
            outcomes.missing.append(outcome.missing)
    return outcomes


def _numeric_casilla_anchors(
    profile: ExtractionProfileDefinition,
    revision: ModeloRevision,
) -> dict[CasillaId, str]:
    """Map canonical target ids to the printed numbers used by ``numeric_casilla``.

    The printed number is ``form_number``, the same field the blank-box guard
    reads. ``number`` is reviewed AEAT record-design metadata and coincides with
    the printed number only when the casilla id is itself numeric, so reading it
    works by accident for numerically-named casillas and yields an id string or a
    fichero-BOE positional range for semantically-named ones. This strategy
    anchors on the printed number at line start, so such an anchor can never
    match and the target silently drops out of every extraction.

    Every ``numeric_casilla`` target in the registry today happens to carry a
    numeric ``number``, so nothing is currently mis-anchored -- but that is the
    same accident that hid the defect in the blank-box guard, and it would end the
    moment a semantically-named casilla is given this strategy.

    Unlike :func:`_printed_box_numbers` this refuses rather than degrading. A
    missing printed number leaves the guard without a safety net, which is
    tolerable; here it means the target cannot be addressed at all, which is a
    registry-integrity error of the same kind as a target naming a casilla that
    does not exist.
    """
    revision_casillas_by_id = casillas_by_id(revision)
    anchors: dict[CasillaId, str] = {}
    for target in profile.target_casillas:
        if target.match_strategy != "numeric_casilla":
            continue
        casilla = revision_casillas_by_id.get(target.casilla_id)
        if casilla is None:
            raise DeclaracionParseError(
                f"extraction profile {profile.id!r} target {target.casilla_id!r} "
                f"is not a canonical casilla.id in revision {revision.id!r}",
            )
        printed = casilla.form_number or None
        if printed is None and casilla.number and casilla.number.strip().isdigit():
            printed = casilla.number
        if printed is None:
            raise DeclaracionParseError(
                f"extraction profile {profile.id!r} target {target.casilla_id!r} anchors on a "
                f"printed box number, but revision {revision.id!r} records none: form_number is "
                f"unset and number is {casilla.number!r}, which is record-design metadata rather "
                f"than a printed box number",
            )
        anchors[target.casilla_id] = printed
    return anchors


def _printed_box_numbers(
    profile: ExtractionProfileDefinition,
    revision: ModeloRevision,
) -> dict[CasillaId, str]:
    """Map ``named_label`` target ids to their printed box number, where one exists.

    Feeds :func:`_is_own_box_number_of_blank_box`, which needs to recognise the
    token a BLANK box leaves behind. Unlike :func:`_numeric_casilla_anchors` this
    is lenient: a target whose printed number the registry does not record simply
    has no box number to compare against, and is left unguarded rather than
    refused.

    The printed number is ``form_number``. ``number`` is reviewed AEAT
    record-design metadata answering a different question, and it coincides with
    the printed number only when the casilla id is itself numeric -- so reading
    it worked by accident for numerically-named casillas and failed silently for
    semantically-named ones, whose ``number`` is an id string or a fichero-BOE
    positional range that no captured token can ever equal. Those targets were
    therefore unguarded, and a blank box returned its own printed number as a
    monetary value.

    ``number`` is still accepted as a fallback, but only when it is a plausible
    printed box number, so the accidental agreement that carried the numerically
    named casillas keeps working without re-admitting the record-design strings
    that caused the defect.

    A target whose printed number is unknown stays UNGUARDED rather than failing
    closed on a bare-integer token. Failing closed was measured against the
    corpus and would refuse genuine values: the informativa perceptor counts
    (``3``, ``2``, ``5``), an explicit zero in a rectificaciones box, and the
    ``ejercicio`` year, none of which are box numbers. Refusing those would trade
    one fabricated value for a different one, so the remaining unguarded targets
    are recorded as an evidence gap to be closed by populating ``form_number``,
    not papered over here.
    """
    revision_casillas_by_id = casillas_by_id(revision)
    numbers: dict[CasillaId, str] = {}
    for target in profile.target_casillas:
        if target.match_strategy != "named_label":
            continue
        casilla = revision_casillas_by_id.get(target.casilla_id)
        if casilla is None:
            continue
        printed = casilla.form_number or None
        if printed is None and casilla.number and casilla.number.strip().isdigit():
            printed = casilla.number
        if printed:
            numbers[target.casilla_id] = printed
    return numbers


def _extract_pages_words(pdf_path: Path) -> tuple[list[_PdfWord], ...]:
    """Extract per-page word-position dicts from ``pdf_path`` using pdfplumber.

    Returns a tuple with one list of word dicts per page in source order.
    Each dict has ``text``, ``x0``, ``x1``, ``top``, ``bottom`` keys from
    pdfplumber's ``Page.extract_words``. Empty pages yield an empty list.
    """
    import pdfplumber

    try:
        with pdfplumber.open(pdf_path) as pdf:
            return tuple(page.extract_words(extra_attrs=["size"]) or [] for page in pdf.pages)
    except Exception as exc:
        _logger.debug(
            "pdfplumber word extraction failed for <input-pdf>: %s",
            type(exc).__name__,
            exc_info=True,
        )
        return ()


def _extract_pages_words_from_bytes(pdf_bytes: bytes) -> tuple[list[_PdfWord], ...]:
    """Extract per-page word-position dicts from in-memory PDF bytes.

    Mirrors :func:`_extract_pages_words` but opens an in-memory
    :class:`~io.BytesIO` stream so decrypted declaration bytes never have to be
    written to a plaintext scratch file to satisfy ``pdfplumber.open``.
    """
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return tuple(page.extract_words(extra_attrs=["size"]) or [] for page in pdf.pages)
    except Exception as exc:
        _logger.debug(
            "pdfplumber word extraction failed for <input-pdf>: %s",
            type(exc).__name__,
            exc_info=True,
        )
        return ()


def _find_bbox_casilla_hits(
    pages_words: tuple[list[_PdfWord], ...],
    target: ExtractionTargetDefinition,
) -> list[tuple[int, str]]:
    """Find the value word for a ``bbox_anchored`` target using word positions.

    Algorithm:
    1. Scan each page's word list for words matching ``bbox_anchor.box_number_pattern``.
    2. For each anchor-word match, locate the value word using ``value_offset``:
       - ``"right_of_number"``: closest word to the right on the same y-row
         (same ``top`` within ``_BBOX_Y_TOLERANCE`` points, x0 greater than
         the anchor word's x1).
    3. If ``column_anchor`` is set, pre-compute the x-range of the column header
       and constrain the anchor-word search to that x-range.

    Returns a list of ``(1-based page number, raw value text)`` tuples.
    Ambiguous matches (multiple anchors on a page) are returned as multiple
    entries so the caller can detect and report them as ``ambiguous``.
    """
    assert target.bbox_anchor is not None  # enforced by model_validator
    anchor_spec: BboxAnchorSpec = target.bbox_anchor
    box_re = re.compile(anchor_spec.box_number_pattern)

    hits: list[tuple[int, str]] = []

    for page_index, words in enumerate(pages_words, start=1):
        if not words:
            continue

        # When column_anchor is set, restrict to words in the column x-range.
        col_x_min: float | None = None
        col_x_max: float | None = None
        if anchor_spec.column_anchor:
            col_x_min, col_x_max = _find_column_x_range(words, anchor_spec.column_anchor)

        anchor_words = [
            w
            for w in words
            if box_re.fullmatch(w["text"])
            and (anchor_spec.anchor_x_min is None or w["x0"] >= anchor_spec.anchor_x_min)
            and (anchor_spec.anchor_x_max is None or w["x0"] <= anchor_spec.anchor_x_max)
            and (col_x_min is None or col_x_max is None or col_x_min <= w["x0"] <= col_x_max)
        ]

        for anchor_word in anchor_words:
            value_word = _resolve_value_word(
                words,
                anchor_word,
                anchor_spec.value_offset,
                value_x_max=anchor_spec.value_x_max,
            )
            if value_word is not None:
                hits.append((page_index, value_word["text"]))

    return hits


_BBOX_Y_TOLERANCE: float = 3.0
"""Maximum vertical distance (points) between anchor and value words on the same row."""

_BBOX_X_GAP_TOLERANCE: float = 150.0
"""Maximum horizontal distance (points) to the right for ``right_of_number`` search."""


def _resolve_value_word(
    words: list[_PdfWord],
    anchor_word: _PdfWord,
    value_offset: str,
    *,
    value_x_max: float | None = None,
) -> _PdfWord | None:
    """Return the value word relative to ``anchor_word`` according to ``value_offset``.

    Args:
        words: All words on the page.
        anchor_word: The located box-number word.
        value_offset: Directional hint — one of ``"right_of_number"``,
            ``"left_of_number"``, or ``"above_number"``.
        value_x_max: When set, restricts ``"right_of_number"`` candidates to
            words whose ``x0`` is at most this value.  Useful in multi-column
            layouts where an empty cell would otherwise match the next column's
            box number.

    Returns:
        The matched value word, or ``None`` if no candidate satisfies the offset
        and proximity constraints.
    """
    anchor_top = anchor_word["top"]
    anchor_x1 = anchor_word["x1"]

    if value_offset == "right_of_number":
        # Find the word on the same y-row to the right of the anchor with the
        # smallest x-gap (closest word), within a reasonable horizontal distance.
        candidates = [
            w
            for w in words
            if abs(w["top"] - anchor_top) <= _BBOX_Y_TOLERANCE
            and w["x0"] > anchor_x1
            and (w["x0"] - anchor_x1) <= _BBOX_X_GAP_TOLERANCE
            and (value_x_max is None or w["x0"] <= value_x_max)
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda w: w["x0"])

    if value_offset == "left_of_number":
        anchor_x0 = anchor_word["x0"]
        candidates = [
            w
            for w in words
            if abs(w["top"] - anchor_top) <= _BBOX_Y_TOLERANCE
            and w["x1"] < anchor_x0
            and (anchor_x0 - w["x1"]) <= _BBOX_X_GAP_TOLERANCE
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda w: w["x1"])

    if value_offset == "above_number":
        anchor_x0 = anchor_word["x0"]
        anchor_x1_val = anchor_word["x1"]
        candidates = [
            w
            for w in words
            if w["bottom"] < anchor_top
            and w["x0"] >= anchor_x0 - _BBOX_Y_TOLERANCE
            and w["x1"] <= anchor_x1_val + _BBOX_Y_TOLERANCE
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda w: w["bottom"])

    return None  # pragma: no cover — exhaustive via Literal type


def _find_column_x_range(
    words: list[_PdfWord],
    column_anchor: str,
) -> tuple[float, float]:
    """Return (x_min, x_max) for the column identified by ``column_anchor`` text.

    Finds all words whose text matches ``column_anchor`` (case-insensitive)
    and returns the bounding x-range of those header words.  When no match
    is found, returns ``(0.0, float("inf"))`` (no constraint).
    """
    matches = [w for w in words if w["text"].lower() == column_anchor.lower()]
    if not matches:
        return (0.0, float("inf"))
    x_min = min(_pdf_word_float(w, "x0") for w in matches)
    x_max = max(_pdf_word_float(w, "x1") for w in matches)
    return (x_min, x_max)


def _find_casilla_hits(
    pages: tuple[str, ...],
    target: ExtractionTargetDefinition,
    *,
    numeric_anchors: dict[CasillaId, str],
) -> list[tuple[int, str]]:
    """Find all regex hits for ``target`` across ``pages``.

    Branches on ``target.match_strategy``:

    - ``"numeric_casilla"``: anchors on the printed casilla number at line start
      followed by a Spanish-formatted amount.  The emitted value remains keyed by
      ``target.casilla_id``.
    - ``"named_label"``: anchors on the printed human-readable label specified
      by ``target.label_pattern`` and captures the last token on the line via
      :data:`TEXT_VALUE_GROUP`.

    Returns a list of ``(1-based page number, captured raw value)`` tuples.
    ``"bbox_anchored"`` targets must use :func:`_find_bbox_casilla_hits` instead.
    """
    if target.match_strategy == "numeric_casilla":
        anchor = numeric_anchors.get(target.casilla_id)
        if anchor is None:
            raise DeclaracionParseError(
                f"numeric extraction target {target.casilla_id!r} has no registry casilla.number anchor",
            )
        pattern = re.compile(
            rf"(?m)^\s*{re.escape(anchor)}\b[^\n]*?\s+{SPANISH_AMOUNT_GROUP}\s*$",
            re.IGNORECASE,
        )
    else:
        # named_label: anchor on the printed label pattern; capture the last token.
        label = target.label_pattern or re.escape(target.casilla_id)
        pattern = re.compile(
            rf"(?m)^\s*{label}[^\n]*?\s+{TEXT_VALUE_GROUP}",
            re.IGNORECASE,
        )

    hits: list[tuple[int, str]] = []
    for page_index, page in enumerate(pages, start=1):
        for match in pattern.finditer(page):
            hits.append((page_index, match.group(1).strip()))
    return hits

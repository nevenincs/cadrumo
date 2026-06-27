"""Public ``parse_declaracion`` entry point for declaración PDFs.

Parsing is registry-grounded: casilla geometry and validation are resolved
against a :class:`RegistrySnapshot`, which the parser loads on demand through
:class:`ValidatedRegistryAuthority` when a caller does not supply one.
The snapshot's :class:`ModeloRevision` owns the extraction profiles and
canonical casilla declarations used during parsing.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any

from ....core import Period
from ....core.logging import get_logger
from ....core.resources import bundled_path
from ....core.time import now
from ....domain.calculations.registry import (
    BboxAnchorSpec,
    CasillaId,
    ExtractionProfileDefinition,
    ExtractionTargetDefinition,
    ModeloRevision,
    RegistrySnapshot,
    RegistrySnapshotError,
    RegistrySnapshotRef,
    ValidatedRegistryAuthority,
    casillas_by_id,
)
from ..pdf import ExtractedCasilla
from ..pdf._label_regex import SPANISH_AMOUNT_GROUP, TEXT_VALUE_GROUP, parse_spanish_decimal
from ..pdf._utils import sha256_file, source_pdf_reference_path
from ._detect import detect_template_revision, detect_template_revision_from_pages
from ._errors import DeclaracionParseError, TemplateNotDetectedError
from ._parsers import extract_pages_text, extract_pages_text_from_bytes
from ._schema import DeclaracionObservation, TemplateRevision

# ADAPTER-INTERNAL-ALIAS-RATIONALE-PDFWORD: pdfplumber's Page.extract_words()
# returns dicts whose full key-set varies by version and page content.  A
# TypedDict would require listing every optional key with total=False and
# would break silently on upstream pdfplumber releases.  Moving to
# aeat.core._types is unwarranted because _PdfWord is consumed exclusively
# within this adapter module.  This alias is correct-by-containment: it
# documents the caller's expectations without over-constraining the library
# boundary.
_PdfWord = dict[str, Any]

_logger = get_logger(__name__)
_INPUT_PDF_SOURCE_LABEL = "<input-pdf>"

_TAX_ID_RE = re.compile(
    r"\bNIF(?:\s+Presentador)?\s*[:\-]\s*(?P<tax_id>(?:[A-Z][0-9]{7}[0-9A-Z]|[0-9]{8}[A-Z]))\b",
    re.IGNORECASE,
)
# 2021-2022 corpus PDFs use an inverted layout where the tax ID appears on the
# line immediately before the "NIF Presentador:" label rather than after it.
_TAX_ID_BEFORE_LABEL_RE = re.compile(
    r"(?P<tax_id>(?:[A-Z][0-9]{7}[0-9A-Z]|[0-9]{8}[A-Z]))\s*\n\s*NIF\s+Presentador\s*:",
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
) -> DeclaracionObservation:
    """Parse an AEAT declaración PDF into a :class:`DeclaracionObservation`.

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
        A strict :class:`DeclaracionObservation` populated with the extracted
        casillas, warnings, and provenance metadata.

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
) -> DeclaracionObservation:
    """Parse declaración PDF bytes without writing them to a plaintext temp file.

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
        A :class:`DeclaracionObservation` populated with the extracted casillas,
        warnings, and provenance metadata.
    """
    pages = extract_pages_text_from_bytes(pdf_bytes, source_label=source_label)
    digest = sha256(pdf_bytes).hexdigest()
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
) -> DeclaracionObservation:
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
    return DeclaracionObservation(
        modelo=template.modelo,
        period=_filing_period_for_observation(template.año, period),
        ejercicio=str(template.año),
        tax_id=tax_id,
        template_revision=template,
        registry_snapshot_ref=snapshot_ref,
        values=values,
        warnings=(),
        source_pdf_path=source_pdf_path,
        source_pdf_sha256=source_pdf_sha256,
        parsed_at=now(),
    )


def _filing_period_for_observation(filing_year: int, registry_selector: str) -> Period:
    """Resolve the parser's registry selector to the stored filing period."""
    normalized = registry_selector.strip().upper()
    if normalized in {"ALTA", "MODIFICACION", "MODIFICACIÓN", "BAJA"}:
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
    return match.group("period").upper()


def _extract_tax_id(text: str) -> str:
    match = _TAX_ID_RE.search(text)
    if match is not None:
        return re.sub(r"\s+", "", match.group("tax_id").strip().rstrip("."))
    before_match = _TAX_ID_BEFORE_LABEL_RE.search(text)
    if before_match is not None:
        return before_match.group("tax_id").upper()
    row_match = _DECLARANT_ROW_RE.search(text)
    if row_match is not None:
        return row_match.group("tax_id").upper()
    raise DeclaracionParseError(
        translated_message="adapters.inbound.declaracion.errors.tax_id_unresolved",
    )


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


def _classify_target(
    target: ExtractionTargetDefinition,
    *,
    pages: tuple[str, ...],
    pages_words: tuple[list[_PdfWord], ...] | None,
    numeric_anchors: dict[CasillaId, str],
) -> _TargetClassification:
    """Resolve one target's hits into a value or a failure category.

    Mirrors the per-target arm of :func:`_extract_profile_values`: bbox targets
    without word data are ``missing``; no hits is ``missing``; multiple hits is
    ``ambiguous``; an unparseable amount is ``malformed``; otherwise the captured
    value is returned as an :class:`ExtractedCasilla`.
    """
    casilla_id = target.casilla_id
    if target.match_strategy == "bbox_anchored":
        if pages_words is None:
            # No word data available (bytes-mode or missing file); treat as missing.
            return _TargetClassification(missing=casilla_id)
        hits = _find_bbox_casilla_hits(pages_words, target)
    else:
        hits = _find_casilla_hits(pages, target, numeric_anchors=numeric_anchors)
    if not hits:
        return _TargetClassification(missing=casilla_id)
    if len(hits) > 1:
        return _TargetClassification(ambiguous=casilla_id)
    page_number, raw_value = hits[0]
    if target.value_kind == "amount":
        parsed: Decimal | str | None = parse_spanish_decimal(raw_value)
        if parsed is None:
            return _TargetClassification(malformed=casilla_id)
    else:
        # "text" and "enum" value kinds: store the raw captured token as-is.
        parsed = raw_value
    return _TargetClassification(
        value=ExtractedCasilla(
            casilla_id=casilla_id,
            printed_value=parsed,
            source_page=page_number,
            source_bbox=None,
            extraction_confidence=1.0,
        ),
    )


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
    # Load word-position data lazily only when bbox_anchored targets exist.
    # Prefer in-memory bytes so decrypted declaration PDFs never touch disk;
    # fall back to a real source file only when bytes are not supplied.
    pages_words: tuple[list[_PdfWord], ...] | None = None
    has_bbox_targets = any(t.match_strategy == "bbox_anchored" for t in profile.target_casillas)
    if has_bbox_targets:
        if pdf_bytes is not None:
            pages_words = _extract_pages_words_from_bytes(pdf_bytes)
        elif source_pdf_path is not None and source_pdf_path.is_file():
            pages_words = _extract_pages_words(source_pdf_path)

    values: list[ExtractedCasilla] = []
    missing: list[CasillaId] = []
    malformed: list[CasillaId] = []
    ambiguous: list[CasillaId] = []
    numeric_anchors = _numeric_casilla_anchors(profile, revision)

    for target in profile.target_casillas:
        outcome = _classify_target(
            target,
            pages=pages,
            pages_words=pages_words,
            numeric_anchors=numeric_anchors,
        )
        if outcome.value is not None:
            values.append(outcome.value)
        elif outcome.malformed is not None:
            malformed.append(outcome.malformed)
        elif outcome.ambiguous is not None:
            ambiguous.append(outcome.ambiguous)
        elif outcome.missing is not None:
            missing.append(outcome.missing)

    coverage = Decimal(len(values)) / Decimal(len(profile.target_casillas))
    # Raise when extraction quality is degraded (ambiguous or malformed hits) or when
    # coverage falls below the configured threshold.  Missing casillas are acceptable
    # as long as coverage meets the threshold — partial filings legitimately omit
    # zero or not-applicable casillas (e.g. M130 real-corpus PDFs).
    if ambiguous or malformed or coverage < profile.min_coverage:
        _raise_extraction_failed(
            profile,
            missing=missing,
            malformed=malformed,
            ambiguous=ambiguous,
            coverage=coverage,
        )
    return tuple(values)


def _numeric_casilla_anchors(
    profile: ExtractionProfileDefinition,
    revision: ModeloRevision,
) -> dict[CasillaId, str]:
    """Map canonical target ids to the printed numbers used by ``numeric_casilla``."""
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
        anchors[target.casilla_id] = casilla.number
    return anchors


def _extract_pages_words(pdf_path: Path) -> tuple[list[_PdfWord], ...]:
    """Extract per-page word-position dicts from ``pdf_path`` using pdfplumber.

    Returns a tuple with one list of word dicts per page in source order.
    Each dict has ``text``, ``x0``, ``x1``, ``top``, ``bottom`` keys from
    pdfplumber's :meth:`Page.extract_words`.  Empty pages yield an empty list.
    """
    import pdfplumber

    try:
        with pdfplumber.open(pdf_path) as pdf:
            return tuple(page.extract_words() or [] for page in pdf.pages)
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
    :class:`io.BytesIO` stream so decrypted declaration bytes never have to be
    written to a plaintext scratch file to satisfy ``pdfplumber.open``.
    """
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return tuple(page.extract_words() or [] for page in pdf.pages)
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
    x_min = min(w["x0"] for w in matches)
    x_max = max(w["x1"] for w in matches)
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

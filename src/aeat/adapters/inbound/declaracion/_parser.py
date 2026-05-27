"""Public ``parse_declaracion`` entry point for declaración PDFs."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from ....core.i18n import tr
from ....core.logging import get_logger
from ....core.paths import PROJECT_ROOT
from ....core.resources import bundled_path
from ....domain.calculations.registry import (
    ExtractionProfileDefinition,
    ExtractionTargetDefinition,
    RegistrySnapshot,
    RegistrySnapshotError,
    ValidatedRegistryAuthority,
)
from ....domain.calculations.registry._schema import RegistrySnapshotRef
from ..pdf import ExtractedCasilla
from ..pdf._label_regex import SPANISH_AMOUNT_GROUP, TEXT_VALUE_GROUP, parse_spanish_decimal
from ..pdf._utils import sha256_file
from ._detect import detect_template_revision, detect_template_revision_from_pages
from ._errors import DeclaracionParseError, TemplateNotDetectedError
from ._parsers import extract_pages_text, extract_pages_text_from_bytes
from ._schema import DeclaracionObservation, TemplateRevision

_logger = get_logger(__name__)

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
        registry_snapshot: Pre-built validated registry snapshot. When
            omitted, the parser loads the committed registry and builds
            one from the detected modelo, tax year, and period.
        registry_root: Optional registry TOML root used when
            ``registry_snapshot`` is omitted.
        source_root: Optional source root used for source integrity
            checks while building a snapshot.

    Returns:
        A strict :class:`DeclaracionObservation` populated with the extracted
        casillas, warnings, and provenance metadata.

    Raises:
        :exc:`aeat.adapters.inbound.declaracion._errors.TemplateNotDetectedError`:
            When auto-detection fails and the caller did not supply both
            ``modelo_override`` and ``año_override``.
        :exc:`aeat.adapters.inbound.declaracion._errors.DeclaracionParseError`:
            For other parse errors (PDF not found, empty text, required
            header field missing, override conflicts with detected
            metadata, malformed casilla values, or missing extraction
            coverage).
    """
    path = Path(pdf_path)
    pages = extract_pages_text(path)
    return _parse_declaracion_pages(
        pages=pages,
        source_path=path.resolve(),
        source_pdf_sha256=sha256_file(path),
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
    """Parse declaración PDF bytes without writing them to a plaintext temp file."""

    pages = extract_pages_text_from_bytes(pdf_bytes, source_label=source_label)
    digest = sha256(pdf_bytes).hexdigest()
    return _parse_declaracion_pages(
        pages=pages,
        source_path=(PROJECT_ROOT / ".secure-source" / f"{digest}.pdf").resolve(),
        source_pdf_sha256=digest,
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
    source_pdf_sha256: str,
    modelo_override: str | None,
    template_revision_override: str | None,
    año_override: int | None,
    period_override: str | None,
    extraction_profile_id: str | None,
    registry_snapshot: RegistrySnapshot | None,
    registry_root: Path | None,
    source_root: Path | None,
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
    values = _extract_profile_values(pages, profile)
    _logger.debug(
        "parse_declaracion: path=%s modelo=%s año=%s period=%s revision=%s profile=%s",
        source_path.name,
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
        period=period,
        ejercicio=str(template.año),
        tax_id=tax_id,
        template_revision=template,
        registry_snapshot_ref=snapshot_ref,
        values=values,
        warnings=(),
        source_pdf_path=source_path,
        source_pdf_sha256=source_pdf_sha256,
        parsed_at=datetime.now(tz=UTC),
    )


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
        modelo_override: Explicit modelo identifier or ``None``.
        template_revision_override: Explicit revision string or ``None``.
        año_override: Explicit four-digit tax year or ``None``.

    Returns:
        The resolved :class:`TemplateRevision`.

    Raises:
        :exc:`aeat.adapters.inbound.declaracion._errors.TemplateNotDetectedError`:
            When detection fails and the caller did not supply both
            modelo and año.
        :exc:`aeat.adapters.inbound.declaracion._errors.DeclaracionParseError`:
            When an override conflicts with the detected metadata.
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
        raise TemplateNotDetectedError(tr("adapters.inbound.declaracion.errors.template_not_detected", path=path))

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
            tr(
                "adapters.inbound.declaracion.errors.modelo_conflict",
                modelo=modelo_override,
                detected=detected.modelo,
            )
        )
    if año_override and año_override != detected.año:
        raise DeclaracionParseError(
            tr("adapters.inbound.declaracion.errors.year_conflict", year=año_override, detected=detected.año)
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
        raise DeclaracionParseError(tr("adapters.inbound.declaracion.errors.period_unresolved"))
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
    raise DeclaracionParseError(tr("adapters.inbound.declaracion.errors.tax_id_unresolved"))


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
            tr(
                "adapters.inbound.declaracion.errors.registry_snapshot_required",
                modelo=template.modelo,
                year=template.año,
                period=period,
                error=exc,
            )
        ) from exc


def _validate_snapshot_matches_template(snapshot: RegistrySnapshot, template: TemplateRevision) -> None:
    if snapshot.modelo.id != template.modelo:
        raise DeclaracionParseError(
            tr(
                "adapters.inbound.declaracion.errors.snapshot_modelo_conflict",
                snapshot_modelo=snapshot.modelo.id,
                detected=template.modelo,
            )
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
            tr(
                "adapters.inbound.declaracion.errors.profile_unavailable",
                profile=extraction_profile_id,
                modelo=snapshot.modelo.id,
            )
        )
    if len(profiles) != 1:
        available = ", ".join(sorted(profile.id for profile in profiles)) or "none"
        raise DeclaracionParseError(
            tr(
                "adapters.inbound.declaracion.errors.profile_count_invalid",
                modelo=snapshot.modelo.id,
                available=available,
            )
        )
    return profiles[0]


def _extract_profile_values(
    pages: tuple[str, ...],
    profile: ExtractionProfileDefinition,
) -> tuple[ExtractedCasilla, ...]:
    values: list[ExtractedCasilla] = []
    missing: list[str] = []
    malformed: list[str] = []
    ambiguous: list[str] = []

    for target in profile.target_casillas:
        casilla_id = target.casilla_id
        hits = _find_casilla_hits(pages, target)
        if not hits:
            missing.append(casilla_id)
            continue
        if len(hits) > 1:
            ambiguous.append(casilla_id)
            continue
        page_number, raw_value = hits[0]
        if target.value_kind == "amount":
            parsed: Decimal | str | None = parse_spanish_decimal(raw_value)
            if parsed is None:
                malformed.append(casilla_id)
                continue
        else:
            # "text" and "enum" value kinds: store the raw captured token as-is.
            parsed = raw_value
        values.append(
            ExtractedCasilla(
                casilla_id=casilla_id,
                printed_value=parsed,
                source_page=page_number,
                source_bbox=None,
                extraction_confidence=1.0,
            )
        )

    coverage = Decimal(len(values)) / Decimal(len(profile.target_casillas))
    if ambiguous or malformed or missing or coverage < profile.min_coverage:
        details = []
        if missing:
            details.append(f"missing={','.join(missing)}")
        if malformed:
            details.append(f"malformed={','.join(malformed)}")
        if ambiguous:
            details.append(f"ambiguous={','.join(ambiguous)}")
        details.append(f"coverage={coverage}")
        raise DeclaracionParseError(
            tr(
                "adapters.inbound.declaracion.errors.extraction_failed",
                profile=profile.id,
                details="; ".join(details),
            ),
            missing=tuple(missing),
            malformed=tuple(malformed),
            ambiguous=tuple(ambiguous),
            coverage=coverage,
        )
    return tuple(values)


def _find_casilla_hits(
    pages: tuple[str, ...],
    target: ExtractionTargetDefinition,
) -> list[tuple[int, str]]:
    """Find all regex hits for ``target`` across ``pages``.

    Branches on ``target.match_strategy``:

    - ``"numeric_casilla"``: anchors on the casilla id printed literally at
      line start followed by a Spanish-formatted amount.  The numeric path is
      unchanged from the pre-named-field implementation.
    - ``"named_label"``: anchors on the printed human-readable label specified
      by ``target.label_pattern`` and captures the last token on the line via
      :data:`TEXT_VALUE_GROUP`.

    Returns a list of ``(1-based page number, captured raw value)`` tuples.
    """

    if target.match_strategy == "numeric_casilla":
        pattern = re.compile(
            rf"(?m)^\s*{re.escape(target.casilla_id)}\b[^\n]*?\s+{SPANISH_AMOUNT_GROUP}\s*$",
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

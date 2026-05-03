"""Public ``parse_declaracion`` entry point for declaración PDFs.

Detection resolves a
:class:`aeat.adapters.inbound.declaracion._schema.TemplateRevision`
from document content and caller overrides. That tuple is a detected
template identity only; it no longer selects a legacy Python extractor
registry entry. Extractor dispatch fails closed until declaration parsing
is backed by validated registry snapshots.
"""

from __future__ import annotations

from pathlib import Path

from ....core.logging import get_logger
from ._detect import detect_template_revision
from ._errors import DeclaracionParseError, TemplateNotDetectedError
from ._extractors import get_extractor
from ._schema import DeclaracionFiling, TemplateRevision

_logger = get_logger(__name__)


def parse_declaracion(
    pdf_path: Path,
    *,
    modelo_override: str | None = None,
    template_revision_override: str | None = None,
    año_override: int | None = None,
) -> DeclaracionFiling:
    """Parse an AEAT declaración PDF into a :class:`DeclaracionFiling`.

    Resolves the
    :class:`aeat.adapters.inbound.declaracion._schema.TemplateRevision`
    triple by combining auto-detection with any caller-supplied
    overrides, then enters the fail-closed extractor dispatch boundary.

    Args:
        pdf_path: Path to the declaración PDF.
        modelo_override: Explicit modelo identifier (skips detection).
        template_revision_override: Explicit revision string (skips detection).
        año_override: Explicit four-digit tax year (skips detection).

    Returns:
        A strict :class:`DeclaracionFiling` populated with the extracted
        casillas, warnings, and provenance metadata.

    Raises:
        :exc:`aeat.adapters.inbound.declaracion._errors.TemplateNotDetectedError`:
            When auto-detection fails and the caller did not supply both
            ``modelo_override`` and ``año_override``.
        :exc:`aeat.adapters.inbound.declaracion._errors.NoExtractorRegisteredError`:
            When extractor dispatch requires validated registry snapshots.
        :exc:`aeat.adapters.inbound.declaracion._errors.DeclaracionParseError`:
            For other parse errors (PDF not found, empty text, required
            header field missing, override conflicts with detected
            metadata).
    """
    path = Path(pdf_path)

    template = _resolve_template(
        path=path,
        modelo_override=modelo_override,
        template_revision_override=template_revision_override,
        año_override=año_override,
    )
    _logger.debug(
        "parse_declaracion: path=%s modelo=%s año=%s revision=%s source=%s",
        path.name,
        template.modelo,
        template.año,
        template.revision,
        template.detected_from,
    )

    extractor = get_extractor(template)
    filing = extractor.extract(path)
    _logger.info(
        "parse_declaracion: parsed %s modelo=%s año=%s",
        path.name,
        template.modelo,
        template.año,
    )
    return filing


def _resolve_template(
    *,
    path: Path,
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

    detected = detect_template_revision(path)
    if detected is None and not (modelo_override and año_override):
        raise TemplateNotDetectedError(
            f"could not auto-detect template for {path}; pass --modelo and --año to override"
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
        raise DeclaracionParseError(f"--modelo {modelo_override!r} conflicts with detected {detected.modelo!r}")
    if año_override and año_override != detected.año:
        raise DeclaracionParseError(f"--año {año_override} conflicts with detected {detected.año}")

    if template_revision_override:
        return TemplateRevision(
            modelo=detected.modelo,
            año=detected.año,
            revision=template_revision_override,
            detected_from="explicit_override",
        )
    return detected

"""Public ``parse_declaracion`` entry point (EPIC #305 cluster D)."""

from __future__ import annotations

from pathlib import Path

from ._detect import detect_template_revision
from ._errors import DeclaracionParseError, TemplateNotDetectedError
from ._extractors import get_extractor
from ._schema import DeclaracionFiling, TemplateRevision


def parse_declaracion(
    pdf_path: Path,
    *,
    modelo_override: str | None = None,
    template_revision_override: str | None = None,
    año_override: int | None = None,
) -> DeclaracionFiling:
    """Parse an AEAT declaración PDF into a :class:`DeclaracionFiling`.

    Args:
        pdf_path: Path to the declaración PDF.
        modelo_override: Explicit modelo identifier (skips detection).
        template_revision_override: Explicit revision string (skips detection).
        año_override: Explicit four-digit tax year (skips detection).

    Returns:
        A strict :class:`DeclaracionFiling`.

    Raises:
        TemplateNotDetectedError: When auto-detection fails and no
            override is supplied.
        NoExtractorRegisteredError: When no extractor is registered for
            the resolved template revision.
        DeclaracionParseError: Base class for other parse errors (PDF
            not found, empty text, required header field missing).
    """
    path = Path(pdf_path)

    template = _resolve_template(
        path=path,
        modelo_override=modelo_override,
        template_revision_override=template_revision_override,
        año_override=año_override,
    )

    extractor = get_extractor(template)
    filing = extractor.extract(path)
    return filing


def _resolve_template(
    *,
    path: Path,
    modelo_override: str | None,
    template_revision_override: str | None,
    año_override: int | None,
) -> TemplateRevision:
    """Resolve to an explicit :class:`TemplateRevision` — override > detect."""
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

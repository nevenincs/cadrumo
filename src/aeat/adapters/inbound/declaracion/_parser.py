"""Public ``parse_declaracion`` entry point for declaración PDFs.

Single-function module that ties detection
(:func:`aeat.adapters.inbound.declaracion._detect.detect_template_revision`)
to extraction (:func:`aeat.adapters.inbound.declaracion._extractors.get_extractor`)
behind one call. Callers may override modelo / año / revision; the
function reconciles overrides against the auto-detected triple and
raises on conflict.
"""

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

    Resolves the
    :class:`aeat.adapters.inbound.declaracion._schema.TemplateRevision`
    triple by combining auto-detection with any caller-supplied
    overrides, then dispatches to the matching extractor obtained from
    :func:`aeat.adapters.inbound.declaracion._extractors.get_extractor`.

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
            When no extractor is registered for the resolved template
            revision.
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

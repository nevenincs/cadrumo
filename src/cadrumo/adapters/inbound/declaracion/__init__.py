"""Public parsing boundary for filed declaration PDFs.

The package exposes :func:`parse_declaracion` for filesystem PDF input and
:func:`parse_declaracion_bytes` for in-memory or decrypted PDF bytes. Both entry
points return :class:`InboundDeclaracionObservation` records interpreted through a
validated :class:`~domain.calculations.registry.RegistrySnapshot`.

Parsing resolves :class:`TemplateRevision` and period, selects one
:class:`~domain.calculations.registry._schema_extraction.ExtractionProfileDefinition` with
``surface == "declaracion_pdf"`` and accepted artefact kind
``"declaration_pdf"``, and extracts filed-declaration casilla values. Without
an explicit profile id, registry profile selection must find exactly one match.

Returned observations stamp a re-resolvable
:class:`~domain.calculations.registry.RegistrySnapshotRef`,
privacy-preserving source reference, and SHA-256. They are observations, not
calculation authority; filing workflow, persistence, tax-law classification,
and CLI presentation live outside inbound parsing.

Template detection resolves identity only; registry validation and profile
choice happen in the parser. This boundary is distinct from
:mod:`~adapters.inbound.justificante`, which parses receipt metadata.

Successful parses currently return ``warnings=()``. :class:`ExtractionWarning`
remains public, while malformed, ambiguous, or low-coverage extraction raises
:exc:`DeclaracionParseError`; missing template identity raises
:exc:`TemplateNotDetectedError`.

Public API::

    from cadrumo.adapters.inbound.declaracion.parser import (
        parse_declaracion,
        parse_declaracion_bytes,
    )
    from cadrumo.adapters.inbound.declaracion.schema import (
        ExtractionWarning,
        InboundDeclaracionObservation,
        TemplateRevision,
    )
    from cadrumo.adapters.inbound.declaracion.errors import (
        DeclaracionParseError,
        TemplateNotDetectedError,
    )

See Also:
    :func:`parse_declaracion`
        Filesystem entry point for declaration-copy PDFs.
    :func:`parse_declaracion_bytes`
        In-memory entry point used by live-read flows that already hold
        decrypted PDF bytes.
    :class:`~domain.calculations.registry._schema_extraction.ExtractionProfileDefinition`
        Registry-owned extraction contract consumed by this parser.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()

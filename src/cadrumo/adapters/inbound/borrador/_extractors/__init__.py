"""Per-año Modelo 100 observed-value extractor registry.

Registers the concrete extractor classes (one per tax year) and exposes
:func:`get_extractor` for the public
:func:`adapters.inbound.borrador.parse_borrador` entry point.

The observed-value extraction logic is year-agnostic across the currently
registered 2021-2025 extractor years: AEAT Renta Web Open borrador PDFs print
casilla rows with the same ``NNNN label amount`` format. A single concrete class
covers those supported years; per-year entries in the registry signal which
years are in scope without requiring distinct class implementations for each.

This registry is an adapter dispatch table, not a registry-authority lookup.
Callers that need target-casilla coverage still provide a
:class:`adapters.inbound.borrador.BorradorExtractionProfile` to
the public parser.

See Also:
    :class:`adapters.inbound.borrador._extractors.modelo_100_summary_v2025.Modelo100ObservedV2025Extractor`
        Current year-stable implementation used by every registered year.
    :class:`adapters.inbound.borrador.BorradorParseMode`
        Caller-selected observed versus registry-profile validation mode.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()

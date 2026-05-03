"""Immutable snapshot creation for registry-backed calculations."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ._schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from ._temporal import select_revision
from ._validate import RegistryValidator


def build_snapshot(
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    *,
    source_root: Path,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: str | None = None,
) -> RegistrySnapshot:
    """Validate ``modelo`` and return the selected immutable snapshot."""

    RegistryValidator(catalogues, source_root=source_root).validate_modelo(modelo)
    revision = select_revision(modelo, filing_year=filing_year, period=period, on=on, revision_id=revision_id)
    legal_ids = set(modelo.legal_refs).union(revision.legal_refs)
    source_ids = set(modelo.source_refs).union(revision.source_refs)
    for casilla in revision.casillas:
        legal_ids.update(casilla.legal_refs)
        source_ids.update(casilla.source_refs)
    for formula in revision.formulas:
        legal_ids.update(formula.legal_refs)
        source_ids.update(formula.source_refs)
    for parameter in revision.parameters:
        legal_ids.update(parameter.legal_refs)
        source_ids.update(parameter.source_refs)
    for binding in revision.bindings:
        legal_ids.update(binding.legal_refs)
        source_ids.update(binding.source_refs)
    for relation in revision.relations:
        legal_ids.update(relation.legal_refs)
        source_ids.update(relation.source_refs)
    for provider in revision.algorithm_providers:
        legal_ids.update(provider.legal_refs)
        source_ids.update(provider.source_refs)
    for algorithm_binding in revision.algorithm_bindings:
        legal_ids.update(algorithm_binding.legal_refs)
        source_ids.update(algorithm_binding.source_refs)
    for layout in revision.export_layouts:
        legal_ids.update(layout.legal_refs)
        source_ids.update(layout.source_refs)
        for record in layout.records:
            for field in record.fields:
                legal_ids.update(field.legal_refs)
                source_ids.update(field.source_refs)
    return RegistrySnapshot(
        modelo=modelo,
        revision=revision,
        legal={ref: catalogues.legal[ref] for ref in sorted(legal_ids)},
        sources={ref: catalogues.sources[ref] for ref in sorted(source_ids)},
    )

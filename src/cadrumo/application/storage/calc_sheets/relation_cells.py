"""Relation values and registry grounding for workbook plans."""

from __future__ import annotations

from ....domain.calculations.registry.relation_prefill_bindings import RelationPrefillProvider
from ....domain.calculations.registry.relations import (
    RegistryFoldRequirement,
    relation_prefill_bindings_for_period,
    relation_requirement_index,
    relation_source_requirements,
)
from ....domain.calculations.registry.schema import BindingDefinition, RegistrySnapshot
from .layout import SheetLayout
from .records import RelationValue, RelationValues, SheetCellAddress, SheetRelationProvenance, SheetValueCell


def relation_value_cells(
    layout: SheetLayout,
    relation_values: RelationValues,
) -> tuple[SheetValueCell, ...]:
    """Mirror caller-supplied cross-revision aggregations to `Tarifas` cells.

    The engine reserves one cell per relation referenced by the
    revision's formulas (see the layout planner's `relation_cells`
    mapping). For each reserved cell we emit:

    - a label cell at `column - 2` carrying the relation id, so the
      operator reading the workbook can identify the aggregation
      without consulting the registry, and
    - the value cell itself at the relation's anchor, populated with
      the caller's pre-resolved scalar when available; a blank cell
      is emitted otherwise so the Sheets formula reads 0 (operators
      who export without supplying relations get a valid workbook
      with a clearly-blank cell to fill in by hand).
    """
    by_relation = relation_values.by_relation()
    cells: list[SheetValueCell] = []
    for relation_id, anchor in layout.relation_cells.items():
        label_address = SheetCellAddress.at(anchor.tab, anchor.row, anchor.column - 2)
        cells.append(
            SheetValueCell(
                address=label_address,
                value=relation_id,
                role="label",
            ),
        )
        supplied = by_relation.get(relation_id)
        cells.append(
            SheetValueCell(
                address=anchor,
                value=supplied.value if supplied is not None else None,
                note=supplied.note if supplied is not None else None,
                role="parameter_value",
            ),
        )
    return tuple(cells)


def relation_values_with_registry_grounding(
    snapshot: RegistrySnapshot,
    layout: SheetLayout,
    relation_values: RelationValues,
) -> RelationValues:
    """Attach registry-owned source identity and grounding to relation scalar rows.

    Takes ``snapshot`` as a :class:`RegistrySnapshot`.
    """
    supplied_by_relation = relation_values.by_relation()
    folds_by_id = {
        binding.id: (binding, provider) for binding, provider in relation_prefill_bindings_for_period(snapshot.revision)
    }
    requirements_by_relation = relation_requirement_index(
        relation_source_requirements(
            snapshot.revision,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
        )
    )
    values = tuple(
        _relation_value_with_registry_grounding(
            relation_id=relation_id,
            provider=folds_by_id[relation_id][1],
            binding=folds_by_id[relation_id][0],
            supplied=supplied_by_relation.get(relation_id),
            requirement=requirements_by_relation.get(relation_id),
        )
        for relation_id in layout.relation_cells
    )
    return RelationValues(values=values)


def _relation_value_with_registry_grounding(
    *,
    relation_id: str,
    provider: RelationPrefillProvider,
    binding: BindingDefinition,
    supplied: RelationValue | None,
    requirement: RegistryFoldRequirement | None,
) -> RelationValue:
    source_modelo = requirement.source_modelo if requirement is not None else provider.source_modelo
    source_periods = requirement.periods if requirement is not None else provider.required_source_periods
    source_casilla_ids = (
        requirement.source_casilla_ids if requirement is not None else provider.declared_source_casilla_ids
    )
    legal_refs = requirement.legal_refs if requirement is not None else tuple(binding.legal_refs)
    source_refs = requirement.source_refs if requirement is not None else tuple(binding.source_refs)
    return RelationValue(
        relation=relation_id,
        value=supplied.value if supplied is not None else None,
        provenance=supplied.provenance if supplied is not None else SheetRelationProvenance.OPERATOR_MANUAL,
        source_modelo=source_modelo,
        source_filing_year=_relation_source_filing_year(requirement, supplied),
        source_periods=source_periods,
        source_casilla_ids=source_casilla_ids,
        dependency_treatment=_relation_dependency_treatment(requirement, supplied),
        legal_refs=legal_refs,
        source_refs=source_refs,
        resolved_at=supplied.resolved_at if supplied is not None else None,
        note=supplied.note if supplied is not None else None,
    )


def _relation_source_filing_year(
    requirement: RegistryFoldRequirement | None,
    supplied: RelationValue | None,
) -> int | None:
    if requirement is not None:
        return requirement.filing_year
    if supplied is not None:
        return supplied.source_filing_year
    return None


def _relation_dependency_treatment(
    requirement: RegistryFoldRequirement | None,
    supplied: RelationValue | None,
) -> str:
    if requirement is not None:
        return requirement.dependency_treatment or ""
    if supplied is not None:
        return supplied.dependency_treatment
    return ""

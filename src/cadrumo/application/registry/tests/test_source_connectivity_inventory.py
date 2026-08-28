"""Corpus gates for the registry side of the source-connectivity census."""

from __future__ import annotations

import pytest

from ....core import RegistryAuthorityGrade
from ....domain.calculations.registry.authority import bundled_authority
from ...registry.source_connectivity import (
    derive_registry_binding_records,
    derive_registry_destination_records,
    derive_registry_formula_records,
    derive_registry_relation_records,
    derive_registry_source_disposition_records,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_every_loaded_revision_has_deterministic_connectivity_records() -> None:
    """Project every validated revision without order drift or omitted declarations."""
    authority = bundled_authority()
    exercised: set[tuple[str, str]] = set()

    for modelo in authority.modelos:
        for revision in modelo.revisions.values():
            filing_year = revision.period_selector.year_from or min(revision.period_selector.years)
            period = min(revision.period_selector.periods)
            snapshot = authority.snapshot(
                modelo.id,
                filing_year=filing_year,
                period=period,
                revision_id=revision.id,
                grade=RegistryAuthorityGrade.APPLICABILITY,
            )
            first = (
                derive_registry_destination_records(snapshot),
                derive_registry_binding_records(snapshot),
                derive_registry_formula_records(snapshot),
                derive_registry_relation_records(snapshot),
                derive_registry_source_disposition_records(snapshot),
            )
            second = (
                derive_registry_destination_records(snapshot),
                derive_registry_binding_records(snapshot),
                derive_registry_formula_records(snapshot),
                derive_registry_relation_records(snapshot),
                derive_registry_source_disposition_records(snapshot),
            )

            assert first == second
            destinations, bindings, formulas, relations, dispositions = first
            assert len(destinations) == len(revision.casillas)
            assert len(bindings) == len(revision.bindings)
            assert len(formulas) == len(revision.formulas)
            assert len(relations) == len(revision.relations)
            assert {row.source_kind for row in dispositions} == {binding.source for binding in revision.bindings}
            assert tuple(row.casilla_id for row in destinations) == tuple(
                sorted(casilla.id for casilla in revision.casillas)
            )
            assert tuple(row.binding_id for row in bindings) == tuple(
                sorted(binding.id for binding in revision.bindings)
            )
            assert tuple(row.relation_id for row in relations) == tuple(
                sorted(relation.id for relation in revision.relations)
            )
            exercised.add((str(modelo.id), str(revision.id)))

    assert exercised == {
        (str(modelo.id), str(revision.id)) for modelo in authority.modelos for revision in modelo.revisions.values()
    }

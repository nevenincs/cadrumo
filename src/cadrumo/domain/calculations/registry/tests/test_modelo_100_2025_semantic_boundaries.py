"""Regression guards for the deferred Modelo 100/2025 semantic rows.

The 2025 declarations for casillas 0150, 0613, and 1481 are measured
cross-revision divergences.  They must not acquire a prior-year producer until
their row-specific legal, input-contract, and independent-value evidence has
been accepted.  These tests exercise the loaded registry graph so an
accidental formula, profile binding, or Modelo 131 relation cannot be added
silently.
"""

from __future__ import annotations

import pytest

from ..schema import ModeloRevision
from ..schema_input_kind import InputKind
from ._modelo_100_registry_support import _loaded_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_FOCUS_ROWS: tuple[tuple[str, str], ...] = (
    ("0150", "formula"),
    ("0613", "formula"),
    ("1481", "relation"),
)


def _casilla(revision: ModeloRevision, casilla_id: str):
    return next(casilla for casilla in revision.casillas if casilla.id == casilla_id)


@pytest.mark.parametrize(("casilla_id", "prior_producer_kind"), _FOCUS_ROWS)
def test_m100_2025_focus_rows_do_not_inherit_prior_revision_producers(
    casilla_id: str,
    prior_producer_kind: str,
) -> None:
    """A prior-year formula or relation is not evidence for the 2025 row."""
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    prior_revision = modelo.revisions["2024"]
    current_revision = modelo.revisions["2025"]

    prior_inventory = prior_revision.producer_inventory()
    current_inventory = current_revision.producer_inventory()
    assert prior_inventory.producer_kind_by_casilla[casilla_id] == prior_producer_kind
    assert current_inventory.producer_kind_by_casilla[casilla_id] == "manual"

    current_casilla = _casilla(current_revision, casilla_id)
    assert current_casilla.input_kind is InputKind.MANUAL
    assert current_casilla.formula is None

    traces = current_inventory.producer_provenance_by_casilla[casilla_id]
    assert len(traces) == 1
    trace = traces[0]
    assert trace.formula is None
    assert trace.binding is None
    assert trace.relation is None


def test_m100_2025_0613_has_no_guarderia_profile_producer() -> None:
    """The 2024 guarderia profile inputs are not silently treated as 2025 facts."""
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    prior_revision = modelo.revisions["2024"]
    current_revision = modelo.revisions["2025"]

    def profile_guarderia_binding_ids(revision: ModeloRevision) -> set[str]:
        return {
            binding.id
            for binding in revision.bindings
            if binding.source.value == "profile" and "guarderia" in binding.id
        }

    prior_ids = profile_guarderia_binding_ids(prior_revision)
    current_ids = profile_guarderia_binding_ids(current_revision)
    assert prior_ids
    assert current_ids == set()


def test_m100_2025_1481_has_no_modelo_131_relation_source() -> None:
    """The only 2025 M131 relation remains the declared payments handoff."""
    modelos_by_id, _catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]

    m131_relations = [relation for relation in revision.relations if relation.source_modelo == "131"]
    assert {(relation.source_casilla_id, relation.target_binding) for relation in m131_relations} == {
        ("15", "renta-2025-modelo-131-pagos-fraccionados"),
    }

    casilla_1481 = _casilla(revision, "1481")
    assert casilla_1481.binding is None

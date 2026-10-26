"""Regression guards for the deferred semantic rows of the newest authored Modelo 100 edition.

That edition's declarations for casillas 0150 and 0613 are measured
cross-revision divergences.  They must not acquire a prior-year producer until
their row-specific legal, input-contract, and independent-value evidence has
been accepted.  These tests exercise the loaded registry graph so an
accidental formula or profile binding cannot be added silently.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind

from ..compiler.producer_inventory import producer_inventory
from ._modelo_100_registry_support import _loaded_registry
from .authored_edition_support import newest_authored_editions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The newest Modelo 100 edition the registry authors; its deferred rows are measured
# against the edition just before it.
_PRIOR_EDITION, _DEFERRED_EDITION = (str(edition) for edition in newest_authored_editions("100", 2))


_FOCUS_ROWS: tuple[tuple[str, str], ...] = (
    ("0150", "formula"),
    ("0613", "formula"),
)


def _casilla(revision: ModeloRevision, casilla_id: str):
    return next(casilla for casilla in revision.casillas if casilla.id == casilla_id)


@pytest.mark.parametrize(("casilla_id", "prior_producer_kind"), _FOCUS_ROWS)
def test_m100_deferred_focus_rows_do_not_inherit_prior_revision_producers(
    casilla_id: str,
    prior_producer_kind: str,
) -> None:
    """A prior-year formula or relation is not evidence for the deferred row."""
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    prior_revision = modelo.revisions[_PRIOR_EDITION]
    current_revision = modelo.revisions[_DEFERRED_EDITION]

    prior_inventory = producer_inventory(prior_revision)
    current_inventory = producer_inventory(current_revision)
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


def test_m100_deferred_0613_has_no_guarderia_profile_producer() -> None:
    """The prior edition's guarderia profile inputs are not silently treated as deferred-edition facts."""
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    prior_revision = modelo.revisions[_PRIOR_EDITION]
    current_revision = modelo.revisions[_DEFERRED_EDITION]

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

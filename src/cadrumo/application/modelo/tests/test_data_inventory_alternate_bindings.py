"""A bound casilla's reviewed alternate bindings stay visible on the checklist.

A bound casilla names one primary binding and may name reviewed equivalents.
The checklist lists the casilla once per binding, in its source's bucket, so an
operator sees every place the value can come from rather than only the first.

No committed casilla names an alternate today, so the case is synthetic: a real
committed revision whose relation prefills are copied with one casilla given a
second relation binding. Everything else is the committed registry.
"""

from __future__ import annotations

import pytest

from ....core.aggregation import BindingSourceKind
from ....domain.calculations.registry.binding_targets import bound_casilla_binding_ids
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.published_authority import published_revision_definitions
from ..data_inventory import _collect_inventory_buckets

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _a_revision_with_two_relation_prefill_casillas() -> tuple[ModeloRevision, int, int]:
    """Return a committed revision and the indices of two relation-prefill casillas in it."""
    for model in published_revision_definitions():
        for revision in model.revisions.values():
            sources = {binding.id: binding.source for binding in revision.bindings}
            relation = [
                index
                for index, casilla in enumerate(revision.casillas)
                if (bound := bound_casilla_binding_ids(casilla))
                and sources[bound[0]] is BindingSourceKind.RELATION_PREFILL
            ]
            if len(relation) >= 2:
                return revision, relation[0], relation[1]
    pytest.fail("no committed revision binds two casillas to relation prefills")


def _with_alternate(revision: ModeloRevision, target: int, donor: int) -> ModeloRevision:
    """Give the target casilla the donor casilla's primary binding as a reviewed alternate."""
    casillas = list(revision.casillas)
    donor_binding = casillas[donor].binding
    assert donor_binding is not None
    casillas[target] = casillas[target].model_copy(update={"alternate_bindings": (donor_binding,)})
    return revision.model_copy(update={"casillas": tuple(casillas)})


def _relation_rows(revision: ModeloRevision) -> set[tuple[str, str | None]]:
    bindings = {binding.id: binding for binding in revision.bindings}
    buckets = _collect_inventory_buckets(revision, bindings)
    return {(entry.casilla_id, entry.binding_id) for entry in buckets.relation_prefill}


def test_an_alternate_relation_binding_is_listed_beside_the_primary() -> None:
    revision, target, donor = _a_revision_with_two_relation_prefill_casillas()
    target_casilla = revision.casillas[target]
    donor_binding = revision.casillas[donor].binding

    rows = _relation_rows(_with_alternate(revision, target, donor))

    assert (target_casilla.id, target_casilla.binding) in rows
    assert (target_casilla.id, donor_binding) in rows


def test_without_an_alternate_the_casilla_is_listed_under_its_primary_only() -> None:
    """The positive control: the alternate row above comes from the alternate, not from the bucket."""
    revision, target, donor = _a_revision_with_two_relation_prefill_casillas()
    target_casilla = revision.casillas[target]
    donor_binding = revision.casillas[donor].binding

    rows = _relation_rows(revision)

    assert (target_casilla.id, target_casilla.binding) in rows
    assert (target_casilla.id, donor_binding) not in rows

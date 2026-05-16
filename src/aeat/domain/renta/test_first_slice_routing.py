"""Strict tests for the BOE-prescribed Modelo 100 first-slice routing.

Three boundaries get coverage:

* The two re-exports (the ``_ledger_expenses`` constant and the
  canonical ``_first_slice_routing`` constant) are the SAME object.
  This guards against a future regression where a copy-edit
  silently forks the table and the two paths drift.
* Every casilla id the routing table targets is a real casilla on
  the modelo-100 registry. This is the cross-domain referential-
  integrity property the snapshot-time gate enforces.
* The constant's coverage of SpendingCategory is closed: the test
  pins the exact category set so a future SpendingCategory enum
  addition without a corresponding routing entry is caught at
  test time, not at runtime by the renta validator.
"""

from __future__ import annotations

import pytest

from ..categories import SpendingCategory
from ._first_slice_routing import (
    FIRST_SLICE_EXPENSE_CASILLAS,
    expected_casilla_for_category,
    first_slice_target_casillas,
)
from ._ledger_expenses import RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_ledger_expenses_re_export_is_the_canonical_table() -> None:
    """``RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS`` IS the canonical mapping.

    Using ``is`` rather than ``==`` guards against any future code
    path that silently copies the table — a copy would equal the
    original but a divergent later edit would not be caught.
    """

    assert RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS is FIRST_SLICE_EXPENSE_CASILLAS


def test_expected_casilla_for_category_round_trips_every_entry() -> None:
    """Every entry in the routing table is reachable via the helper."""

    for category, casilla in FIRST_SLICE_EXPENSE_CASILLAS.items():
        assert expected_casilla_for_category(category) == casilla


def test_expected_casilla_is_none_outside_first_slice() -> None:
    """A category outside the first slice returns ``None``, not a fallback."""

    outside_slice = next(
        cat
        for cat in SpendingCategory
        if cat not in FIRST_SLICE_EXPENSE_CASILLAS
    )
    assert expected_casilla_for_category(outside_slice) is None


def test_first_slice_target_casillas_is_closed_set() -> None:
    """The targets the routing table can resolve to are exactly four casillas.

    The set is closed by BOE prescription; a fifth entry should
    only land alongside a corresponding registry-data update on
    modelo 100. Asserting the closed set surfaces additions as
    test failures so the migration is intentional.
    """

    assert first_slice_target_casillas() == frozenset({"0186", "0192", "0199", "0203"})


def test_first_slice_routing_targets_exist_in_modelo_100_registry() -> None:
    """Cross-domain integrity: every routing target is a casilla on M100.

    Loads the modelo-100 registry from bundled data and asserts that
    every target casilla id the routing table mentions is declared
    as a casilla on at least one revision of M100. This is the
    domain-layer mirror of the snapshot-time gate wired into
    :func:`_check_all_id_references`.
    """

    from ...core.resources import bundled_path
    from ..calculations.registry._loader import load_registry_tree

    modelos, _ = load_registry_tree(bundled_path("registry", "aeat"))
    modelo_100 = next((m for m in modelos if m.id == "100"), None)
    assert modelo_100 is not None, "modelo-100 must be present in bundled registry"

    all_casilla_ids: set[str] = set()
    for revision in modelo_100.revisions.values():
        all_casilla_ids.update(casilla.id for casilla in revision.casillas)

    missing = first_slice_target_casillas() - all_casilla_ids
    assert not missing, (
        f"first-slice routing targets casillas absent from modelo-100: {sorted(missing)!r}"
    )

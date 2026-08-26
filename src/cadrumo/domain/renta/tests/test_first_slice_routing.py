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

from cadrumo.domain.calculations.registry.ledger_bindings import renta_first_slice_binding_target_casillas

from ....core import CasillaId, Modelo
from ...calculations.registry.authority import bundled_authority
from ...categories import SpendingCategory
from .._first_slice_routing import (
    FIRST_SLICE_EXPENSE_CASILLAS,
    expected_casilla_for_category,
    first_slice_target_casillas,
)
from .._ledger_expenses import RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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


def test_expected_casilla_for_category_is_a_direct_lookup_with_no_fallback() -> None:
    """``expected_casilla_for_category`` is ``Mapping.get`` -- no default casilla.

    The routing table is now total (every :class:`SpendingCategory`
    member routes to a real casilla), so this asserts the helper never
    substitutes a fallback casilla for a member it disagrees with: it
    always returns exactly what the table declares, never a coerced
    default. A future enum member added without a routing entry is
    caught by :func:`test_every_spending_category_routes_to_a_first_slice_casilla`
    (``expected_casilla_for_category`` would return ``None`` for it,
    not silently fall back to an arbitrary casilla).
    """

    for category in SpendingCategory:
        assert expected_casilla_for_category(category) == FIRST_SLICE_EXPENSE_CASILLAS[category]


def test_first_slice_target_casillas_is_closed_set() -> None:
    """The targets the routing table can resolve to are exactly these casillas.

    The set is closed by BOE prescription; a new entry should
    only land alongside a corresponding registry-data update on
    modelo 100. Asserting the closed set surfaces additions as
    test failures so the migration is intentional.
    """

    assert first_slice_target_casillas() == frozenset(
        {
            "0183",
            "0186",
            "0191",
            "0192",
            "0193",
            "0194",
            "0195",
            "0199",
            "0200",
            "0202",
            "0203",
            "0206",
            "0208",
            "0217",
        },
    )


def test_every_spending_category_routes_to_a_first_slice_casilla() -> None:
    """No :class:`SpendingCategory` member is silently unrouted.

    Every deducible autónomo expense category resolves to a real
    Modelo 100 estimación-directa casilla. A category left out of
    :data:`FIRST_SLICE_EXPENSE_CASILLAS` would silently drop that
    expense class from the annual filing while the M130 quarterly
    path still accepted it (``no-silent-under-declaration``,
    ``aeat-calculation-aggregation``).
    """

    unrouted = [category for category in SpendingCategory if expected_casilla_for_category(category) is None]
    assert unrouted == []


def test_first_slice_routing_targets_exist_in_modelo_100_registry() -> None:
    """Cross-domain integrity: every routing target is a casilla on M100.

    Loads the modelo-100 registry from bundled data and asserts that
    every target casilla id the routing table mentions is declared
    as a casilla on at least one revision of M100. This is the
    domain-layer mirror of the snapshot-time gate wired into
    :func:`_check_all_id_references`.
    """

    modelo_100 = bundled_authority().modelo("100")

    all_casilla_ids: set[CasillaId] = set()
    for revision in modelo_100.revisions.values():
        all_casilla_ids.update(casilla.id for casilla in revision.casillas)

    missing = first_slice_target_casillas() - all_casilla_ids
    assert not missing, f"first-slice routing targets casillas absent from modelo-100: {sorted(missing)!r}"


def test_first_slice_check_is_registered_with_the_registry_validator() -> None:
    """Importing ``renta`` registers the first-slice cross-domain check.

    The registry validator depends only on the abstract
    ``CrossDomainSnapshotCheck`` Protocol. The concrete renta check is
    injected at ``renta`` package import time. This test confirms the
    registration side effect landed (importing this test module imports
    ``renta``).
    """

    from ...calculations.registry._validate_references import _CROSS_DOMAIN_SNAPSHOT_CHECKS
    from .._first_slice_routing_integrity import check_first_slice_routing

    assert check_first_slice_routing in _CROSS_DOMAIN_SNAPSHOT_CHECKS


def test_registered_check_fires_through_the_snapshot_build_gate() -> None:
    """The registered renta check runs inside ``_check_all_id_references``.

    Drives a divergent casilla set through the registered check against a
    representative revision-scoped binding-target set: a binding target
    absent from the revision must surface as a failure string. This
    proves the Protocol-injected check is wired into the snapshot gate
    rather than dead code.

    The check is scoped to a revision's OWN
    ``ledger_renta_gastos_estimacion_directa_aggregation`` binding targets (never the
    universal :func:`first_slice_target_casillas` codomain) -- see
    :mod:`cadrumo.domain.renta._first_slice_routing_integrity` for why a
    revision that declares no such bindings has a legitimately empty
    required set.
    """

    from .._first_slice_routing_integrity import check_first_slice_routing

    representative_targets = frozenset({"0183", "0195"})
    # A casilla set missing every routing target must report them all.
    failures = check_first_slice_routing("100", frozenset(), representative_targets)
    assert len(failures) == 1
    for target in representative_targets:
        assert target in failures[0]
    # A complete casilla set reports nothing.
    assert check_first_slice_routing("100", representative_targets, representative_targets) == []
    # A revision with no first-slice bindings has an empty required set --
    # reports nothing even with an empty casilla set (the 2020-2022 shape).
    assert check_first_slice_routing("100", frozenset(), frozenset()) == []
    # A non-100 modelo is outside the first slice -- no check.
    assert check_first_slice_routing("303", frozenset(), representative_targets) == []


def test_renta_first_slice_binding_target_casillas_is_revision_scoped() -> None:
    """The per-revision binding-target helper reflects real registry data.

    The 2020-2022 Modelo 100 revisions declare no
    ``ledger_renta_gastos_estimacion_directa_aggregation`` bindings at all -- "Aportaciones a
    mutualidades alternativas" shares the combined ``0186`` Seguridad
    Social casilla on those years rather than the dedicated ``0195`` box
    introduced from 2023 onward. The 2024/2025 revisions declare the full
    14-casilla binding set. This is the property that makes the universal
    :func:`first_slice_target_casillas` codomain unsuitable as a
    per-revision referential-integrity requirement.
    """

    modelo_100 = bundled_authority().modelo("100")

    for year in ("2020", "2021", "2022"):
        revision = modelo_100.revisions[year]
        assert renta_first_slice_binding_target_casillas(revision) == frozenset()

    for year in ("2024", "2025"):
        revision = modelo_100.revisions[year]
        targets = renta_first_slice_binding_target_casillas(revision)
        assert targets == first_slice_target_casillas()
        assert "0195" in targets


def test_modelo_100_snapshots_build_cleanly_across_every_revision() -> None:
    """Every Modelo 100 revision's snapshot passes referential integrity.

    This is the real end-to-end proof for the fix: building a snapshot
    for the 2020-2022 revisions (which declare no first-slice ledger
    bindings) must not raise, even though casilla ``0195`` -- part of
    the universal routing table's codomain -- does not exist on those
    revisions. Building 2023-2025 must also succeed. A regression back
    to checking the universal codomain against every revision's own
    casilla set reproduces the exact defect this test guards against.
    """

    authority = bundled_authority()
    for year in (2020, 2021, 2022, 2023, 2024, 2025):
        snapshot = authority.snapshot(Modelo.M100, filing_year=year, period="0A")
        assert snapshot.revision.id == str(year)

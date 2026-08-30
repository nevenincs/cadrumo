"""Connectivity gate: the committed registry declares no dormant source kind.

The ``RegistryQueryService.source_inventory`` report walks every committed modelo
revision and records which :class:`BindingSourceKind` members the
registry actually declares in its bindings, and where. This gate joins that
registry-side inventory against the live-mesh disposition taxonomy
(``build_binding_source_dispositions`` and the ``DEFERRED`` / ``RESERVED``
partition sets) and refuses the ``aeat-calculation-aggregation`` violation at the
registry-inventory boundary: no committed revision may declare a ``RESERVED``
source kind, because a reserved kind has neither an enrolled resolver nor a
standing deferred advisory, so it would resolve to a silent blank on every
calculation.

The strictly-stronger "against the LIVE enrolled resolver set" join (proving each
declared kind resolves ``ENROLLED`` or ``DEFERRED`` under the actual
``BUCKET_AGGREGATION_OWNED_SOURCES`` derived from live resolver ``owned_sources``,
and that a novel source raises) lives in the application-layer companion
``application/modelo/tests/test_source_mesh_missing_sources.py`` — the live
enrolled set is an application (live-mesh) fact and cannot cross into a domain
test without inverting the layer boundary. This domain gate owns the
registry-inventory integrity half.

See Also:
    :class:`BindingSourceKind`
        Closed source-kind enum whose committed declarations are inventoried.
    :class:`~domain.calculations.registry.RegistryQueryService`
        Domain query service whose ``source_inventory`` report feeds this gate.
    :class:`~domain.calculations.registry.RegistrySourceInventoryReport`
        Typed report contract that records declared source kinds and sites.
    :func:`~application.aggregation.build_binding_source_dispositions`
        Builds the enrolled/deferred/reserved disposition taxonomy.
    :class:`~application.aggregation.BindingSourceDisposition`
        Disposition enum used to reject reserved committed declarations.
    :data:`~application.aggregation.DEFERRED_SOURCE_KINDS`
        Known source kinds with visible advisory deferral.
    :data:`~application.aggregation.RESERVED_SOURCE_KINDS`
        Reserved source kinds this registry gate proves are not declared.
    :mod:`~application.modelo.tests.test_source_mesh_missing_sources`
        Application companion that joins the inventory to the live enrolled set.
"""

from __future__ import annotations

import pytest

from .....application.aggregation import (
    DEFERRED_SOURCE_KINDS,
    RESERVED_SOURCE_KINDS,
    BindingSourceDisposition,
    build_binding_source_dispositions,
)
from .....core.aggregation import BindingSourceKind
from ..authority import bundled_authority
from ..queries import RegistryQueryService
from ..query_reports import RegistrySourceInventoryReport

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _inventory() -> RegistrySourceInventoryReport:
    return RegistryQueryService(bundled_authority()).source_inventory()


def test_source_inventory_is_non_empty_and_well_formed() -> None:
    """The committed registry declares a non-trivial set of source kinds, each with real sites.

    Anti-vacuity floor for the connectivity gates below: a report with no rows
    would make every "no declared reserved kind" assertion trivially true.
    """
    report = _inventory()
    assert report.rows, "source_inventory returned no declared source kinds — the connectivity gate would be vacuous"
    for row in report.rows:
        assert row.sites, f"{row.source_kind.value} declared with no sites"
        assert row.total_binding_count == sum(site.binding_count for site in row.sites)
        assert row.total_binding_count >= len(row.sites)
        # Sites are sorted and unique by (modelo, revision_id).
        keys = [(site.modelo, site.revision_id) for site in row.sites]
        assert keys == sorted(keys)
        assert len(keys) == len(set(keys))


def test_declared_source_kinds_carry_both_enrolled_and_deferred_anchors() -> None:
    """The inventory spans both partitions, so the enrolled/deferred discrimination below is live.

    ``ledger_iva_aggregation`` is an enrolled ledger resolver; ``related_party_operation``
    is an explicitly deferred detail-row kind. Both being declared by the committed
    registry proves the connectivity gate exercises both partitions rather than one.
    """
    declared = _inventory().declared_source_kinds
    assert BindingSourceKind.LEDGER_IVA_AGGREGATION in declared
    assert BindingSourceKind.RELATED_PARTY_OPERATION in declared
    assert BindingSourceKind.RELATED_PARTY_OPERATION in DEFERRED_SOURCE_KINDS


def test_no_committed_revision_declares_a_reserved_source_kind() -> None:
    """Every declared source kind is enrolled or deferred — never reserved (dormant).

    A ``RESERVED`` source kind carries no enrolled resolver and no standing
    deferred advisory, so a committed revision that declared one would blank that
    binding on every calculation with no operator-visible diagnostic — the exact
    ``aeat-calculation-aggregation`` silent-zero this gate refuses. The disposition
    of each declared kind is read from ``build_binding_source_dispositions`` (the
    single closed answer to "where does source X resolve"); a declared kind that
    classifies ``RESERVED`` fails here with its declaring sites enumerated.
    """
    report = _inventory()
    # Enrolled partition, by the disposition-registry parity invariant
    # (test_binding_source_kind_mesh_parity: the three partitions are complete and
    # non-overlapping), is the complement of the deferred and reserved sets.
    enrolled = frozenset(BindingSourceKind) - DEFERRED_SOURCE_KINDS - RESERVED_SOURCE_KINDS
    dispositions = build_binding_source_dispositions(enrolled)

    offenders: list[str] = []
    for row in report.rows:
        disposition = dispositions[row.source_kind]
        if disposition is BindingSourceDisposition.RESERVED:
            sites = ", ".join(f"M{site.modelo}:{site.revision_id}" for site in row.sites)
            offenders.append(f"{row.source_kind.value} (RESERVED, declared by {sites})")

    assert not offenders, (
        "Committed revisions declare RESERVED (dormant, no-resolver, no-advisory) source kinds — "
        "each would silently blank on calculation. Enroll a resolver or explicitly defer it:\n"
        + "\n".join(f"  * {o}" for o in offenders)
    )

    # Every declared kind must therefore classify ENROLLED or DEFERRED.
    for row in report.rows:
        assert dispositions[row.source_kind] in {
            BindingSourceDisposition.ENROLLED,
            BindingSourceDisposition.DEFERRED,
        }


def test_a_reserved_kind_would_be_caught_if_declared() -> None:
    """Anti-tautology: a RESERVED kind classifies RESERVED, so the gate above can fail.

    ``ledger_transaction`` is a real reserved member (taxonomy headroom with no
    binding and no resolver). Proving it classifies ``RESERVED`` confirms the
    "no declared reserved kind" gate is a live discriminator, not a check that
    can only ever pass.
    """
    enrolled = frozenset(BindingSourceKind) - DEFERRED_SOURCE_KINDS - RESERVED_SOURCE_KINDS
    dispositions = build_binding_source_dispositions(enrolled)
    assert RESERVED_SOURCE_KINDS, "expected a non-empty reserved set for this anti-tautology proof"
    for reserved_kind in RESERVED_SOURCE_KINDS:
        assert dispositions[reserved_kind] is BindingSourceDisposition.RESERVED
        # And the registry must not declare it (the gate above would otherwise be red).
        assert reserved_kind not in _inventory().declared_source_kinds

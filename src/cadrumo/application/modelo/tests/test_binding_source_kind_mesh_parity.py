"""Enum↔mesh parity: the application resolver mesh carries only canonical source kinds.

This is the application-layer half of the source-kind taxonomy parity gate. The
domain-layer half (``test_binding_source_kind_taxonomy.py``) binds
:class:`cadrumo.core.BindingSourceKind` to the compiled registry; this half binds the
same enum to the **application resolver mesh** — the owned/deferred source sets and
the novel-source boundary gate that drive live calculation.

It lives in the application layer (not beside the domain gate) because the mesh sets
(``BUCKET_AGGREGATION_OWNED_SOURCES``, ``DEFERRED_SOURCE_KINDS``) are application
symbols, and a domain test importing them would violate the hexagonal direction
(domain → application is forbidden). Together the two halves close the
"neither set contains the other" defect: every mesh source is a
:class:`BindingSourceKind` member, and every member is accounted for as
enrolled, pre-mesh-handled, deferred, or explicitly reserved-undeclared.
"""

from __future__ import annotations

import pytest

from ....core.aggregation import BindingSourceKind
from ...aggregation import (
    DEFERRED_SOURCE_KINDS,
    RESERVED_SOURCE_KINDS,
    BindingSourceDisposition,
)
from .._calculation_source_policy import BUCKET_AGGREGATION_OWNED_SOURCES
from ..calculation_route import (
    CALCULATION_ROUTE_RESOLVER_OWNERSHIP,
    CALCULATION_ROUTE_SOURCE_DISPOSITIONS,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# Enum members that are NOT routed through the bucket-aggregation owned/deferred mesh
# sets, with the reason each is absent. The novel-source gate accepts the owned set ∪
# the deferred set; these members are accounted for elsewhere, so the enum↔mesh
# completeness assertion below exempts exactly this set (and fails if it drifts):
#
#   PURCHASE_INVOICE_EVIDENCE / LEDGER_TRANSACTION — counterpart/invoice-shaped
#     reserved-undeclared sources (no registry binding, no resolver yet); the domain
#     gate's _RESERVED_UNDECLARED_SOURCE_KINDS carve-out tracks them.
#   RELATED_PARTY_OPERATION / REFUND_OPERATION — deferred detail-record
#     families. Their bare-string DEFERRED tokens match the enum member VALUE;
#     the deferred set is asserted to map onto the enum directly below.
# The reserved-undeclared carve-out is now the canonical RESERVED_SOURCE_KINDS in
# the source-mesh module (single declaration); the test consumes it rather than
# re-listing the members.
_MESH_UNROUTED_RESERVED: frozenset[BindingSourceKind] = RESERVED_SOURCE_KINDS


def test_owned_mesh_sources_are_all_binding_source_kind_members() -> None:
    """Every ``BUCKET_AGGREGATION_OWNED_SOURCES`` token is a canonical enum value.

    A typo or a stray bare string in the owned set would silently route (or
    fail to route) a resolver; binding it to the enum makes that a test failure.
    """
    enum_values = {member.value for member in BindingSourceKind}
    stray = sorted(BUCKET_AGGREGATION_OWNED_SOURCES - enum_values)
    assert not stray, f"Owned mesh source(s) absent from BindingSourceKind: {stray}"


def test_deferred_mesh_sources_are_all_binding_source_kind_members() -> None:
    """Every ``DEFERRED_SOURCE_KINDS`` token is a canonical enum value."""
    enum_values = {member.value for member in BindingSourceKind}
    stray = sorted(DEFERRED_SOURCE_KINDS - enum_values)
    assert not stray, f"Deferred mesh source(s) absent from BindingSourceKind: {stray}"


def test_owned_and_deferred_mesh_sets_are_disjoint() -> None:
    """A source kind is either routed by a resolver or deferred, never both."""
    overlap = sorted(BUCKET_AGGREGATION_OWNED_SOURCES & DEFERRED_SOURCE_KINDS)
    assert not overlap, f"Source kind(s) both owned and deferred (ambiguous routing): {overlap}"


def test_every_enum_member_is_routed_deferred_or_reserved() -> None:
    """Close the union: no enum member is silently absent from the mesh accounting.

    Every :class:`BindingSourceKind` member must be either routed by an enrolled /
    pre-mesh resolver (``BUCKET_AGGREGATION_OWNED_SOURCES``), explicitly deferred
    (``DEFERRED_SOURCE_KINDS``), or one of the documented reserved-undeclared
    counterpart/invoice sources. A member that drifts out of all three is an
    unaccounted source kind — exactly the "neither set contains the other" gap.
    """
    accounted = (
        BUCKET_AGGREGATION_OWNED_SOURCES | DEFERRED_SOURCE_KINDS | {member.value for member in _MESH_UNROUTED_RESERVED}
    )
    unaccounted = sorted(member.value for member in BindingSourceKind if member.value not in accounted)
    assert not unaccounted, (
        "BindingSourceKind member(s) not routed, deferred, or reserved in the mesh "
        f"(unaccounted source kind): {unaccounted}"
    )


def test_borrador_and_iva_wallet_decision_are_routed_owned_sources() -> None:
    """The two mesh-only members are first-class owned sources, not bare strings.

    They carry no registry binding (the domain gate exempts them via
    ``_MESH_ONLY_SOURCE_KINDS``), so this is the gate that proves they ARE accounted
    for on the mesh half.
    """
    assert BindingSourceKind.BORRADOR.value in BUCKET_AGGREGATION_OWNED_SOURCES
    assert BindingSourceKind.IVA_WALLET_DECISION.value in BUCKET_AGGREGATION_OWNED_SOURCES


def test_inventory_has_one_mesh_owner_and_is_no_longer_deferred() -> None:
    """Inventory is enrolled exactly once without claiming runtime composition."""
    owners = tuple(
        row for row in CALCULATION_ROUTE_RESOLVER_OWNERSHIP if BindingSourceKind.INVENTORY in row.owned_sources
    )

    assert len(owners) == 1
    assert owners[0].stage == "mesh"
    assert owners[0].resolver_id == "inventory"
    assert BindingSourceKind.INVENTORY not in DEFERRED_SOURCE_KINDS
    assert CALCULATION_ROUTE_SOURCE_DISPOSITIONS[BindingSourceKind.INVENTORY] is BindingSourceDisposition.ENROLLED


def test_reserved_mesh_members_are_not_routed_or_deferred() -> None:
    """Anti-tautology: the reserved carve-out is genuinely absent from the mesh.

    If a reserved member silently appeared in the owned or deferred set, the
    completeness assertion above would pass vacuously; this pins the carve-out to
    its real (unrouted) state so it cannot be widened to mask a routing change.
    """
    routed_or_deferred = BUCKET_AGGREGATION_OWNED_SOURCES | DEFERRED_SOURCE_KINDS
    leaked = sorted(member.value for member in _MESH_UNROUTED_RESERVED if member.value in routed_or_deferred)
    assert not leaked, f"Reserved-undeclared member(s) unexpectedly routed/deferred on the mesh: {leaked}"


# ---------------------------------------------------------------------------
# the ONE disposition registry parity gate.
#
# The canonical route disposition registry is the single mapping
# answering "where does source X resolve" for every BindingSourceKind member,
# built from the LIVE enrolled set (no hard-coded dispositions). These assertions
# bind it to the enum and to the owned / deferred / reserved sets, making
# aeat-calculation-aggregation enforceable across the union.


def test_disposition_registry_covers_every_enum_member() -> None:
    """Every BindingSourceKind member has exactly one declared disposition.

    A member missing from the registry is an unaccounted source kind; the registry
    builder raises on a member in zero or two states, so this pins full coverage.
    """
    assert set(CALCULATION_ROUTE_SOURCE_DISPOSITIONS) == set(BindingSourceKind)


def test_disposition_enrolled_partition_equals_owned_mesh_set() -> None:
    """The ENROLLED disposition partition equals the owned mesh set EXACTLY.

    The disposition registry's enrolled members must be precisely the live
    enrolled resolver / pre-mesh / manual owned_sources. A
    drift between the registry and the owned set (a newly-enrolled source not
    reflected, or an owned source not enrolled) fails here.
    """
    enrolled = frozenset(
        source
        for source, disposition in CALCULATION_ROUTE_SOURCE_DISPOSITIONS.items()
        if disposition is BindingSourceDisposition.ENROLLED
    )
    assert enrolled == BUCKET_AGGREGATION_OWNED_SOURCES


def test_disposition_deferred_partition_equals_deferred_set() -> None:
    """The DEFERRED disposition partition equals DEFERRED_SOURCE_KINDS exactly."""
    deferred = frozenset(
        source
        for source, disposition in CALCULATION_ROUTE_SOURCE_DISPOSITIONS.items()
        if disposition is BindingSourceDisposition.DEFERRED
    )
    assert deferred == DEFERRED_SOURCE_KINDS


def test_disposition_reserved_partition_equals_reserved_set() -> None:
    """The RESERVED disposition partition equals RESERVED_SOURCE_KINDS exactly."""
    reserved = frozenset(
        source
        for source, disposition in CALCULATION_ROUTE_SOURCE_DISPOSITIONS.items()
        if disposition is BindingSourceDisposition.RESERVED
    )
    assert reserved == RESERVED_SOURCE_KINDS


def test_disposition_partitions_are_a_total_disjoint_cover() -> None:
    """The three dispositions partition the enum: total, disjoint, no member double-counted.

    This is the structural guarantee that replaces the four scattered enrollment
    structures with one mapping: every member is enrolled, deferred, or reserved,
    and never two at once.
    """
    enrolled = {
        source
        for source, disposition in CALCULATION_ROUTE_SOURCE_DISPOSITIONS.items()
        if disposition is BindingSourceDisposition.ENROLLED
    }
    deferred = {
        source
        for source, disposition in CALCULATION_ROUTE_SOURCE_DISPOSITIONS.items()
        if disposition is BindingSourceDisposition.DEFERRED
    }
    reserved = {
        source
        for source, disposition in CALCULATION_ROUTE_SOURCE_DISPOSITIONS.items()
        if disposition is BindingSourceDisposition.RESERVED
    }
    assert enrolled.isdisjoint(deferred)
    assert enrolled.isdisjoint(reserved)
    assert deferred.isdisjoint(reserved)
    assert enrolled | deferred | reserved == set(BindingSourceKind)

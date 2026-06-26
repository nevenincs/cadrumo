"""Enum↔mesh parity: the application resolver mesh carries only canonical source kinds.

This is the application-layer half of the source-kind taxonomy parity gate. The
domain-layer half (``test_binding_source_kind_taxonomy.py``) binds
:class:`aeat.core.BindingSourceKind` to the compiled registry; this half binds the
same enum to the **application resolver mesh** — the owned/deferred source sets and
the novel-source boundary gate that drive live calculation.

It lives in the application layer (not beside the domain gate) because the mesh sets
(``_BUCKET_AGGREGATION_OWNED_SOURCES``, ``DEFERRED_SOURCE_KINDS``) are application
symbols, and a domain test importing them would violate the hexagonal direction
(domain → application is forbidden). Together the two halves close the
"neither set contains the other" defect the phase-2.1 ADR
(``2026-06-26-binding-source-kind-taxonomy-unification-adr``) eliminates: every mesh
source is a :class:`BindingSourceKind` member, and every member is accounted for as
enrolled, pre-mesh-handled, deferred, or explicitly reserved-undeclared.
"""

from __future__ import annotations

import pytest

from ....core import BindingSourceKind
from ...aggregation import DEFERRED_SOURCE_KINDS
from .._calculation_actions import _BUCKET_AGGREGATION_OWNED_SOURCES

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# Enum members that are NOT routed through the bucket-aggregation owned/deferred mesh
# sets, with the reason each is absent. The novel-source gate accepts the owned set ∪
# the deferred set; these members are accounted for elsewhere, so the enum↔mesh
# completeness assertion below exempts exactly this set (and fails if it drifts):
#
#   PURCHASE_INVOICE_EVIDENCE / LEDGER_TRANSACTION — counterpart/invoice-shaped
#     reserved-undeclared sources (no registry binding, no resolver yet); the domain
#     gate's _RESERVED_UNDECLARED_SOURCE_KINDS carve-out tracks them.
#   WITHHOLDING / FOREIGN_ASSET / RELATED_PARTY_OPERATION / ATRIBUCION_MEMBER /
#     REFUND_OPERATION — detail-record families. Their bare-string DEFERRED tokens
#     differ from the enum member VALUE only for the three `_operation` / `_member`
#     suffixed members (see ROW_SET_GROUPING_FOR_BINDING_SOURCE); the deferred set is
#     asserted to map onto the enum directly below.
_MESH_UNROUTED_RESERVED: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
        BindingSourceKind.LEDGER_TRANSACTION,
    },
)


def test_owned_mesh_sources_are_all_binding_source_kind_members() -> None:
    """Every ``_BUCKET_AGGREGATION_OWNED_SOURCES`` token is a canonical enum value.

    A typo or a stray bare string in the owned set would silently route (or
    fail to route) a resolver; binding it to the enum makes that a test failure.
    """
    enum_values = {member.value for member in BindingSourceKind}
    stray = sorted(_BUCKET_AGGREGATION_OWNED_SOURCES - enum_values)
    assert not stray, f"Owned mesh source(s) absent from BindingSourceKind: {stray}"


def test_deferred_mesh_sources_are_all_binding_source_kind_members() -> None:
    """Every ``DEFERRED_SOURCE_KINDS`` token is a canonical enum value."""
    enum_values = {member.value for member in BindingSourceKind}
    stray = sorted(DEFERRED_SOURCE_KINDS - enum_values)
    assert not stray, f"Deferred mesh source(s) absent from BindingSourceKind: {stray}"


def test_owned_and_deferred_mesh_sets_are_disjoint() -> None:
    """A source kind is either routed by a resolver or deferred, never both."""
    overlap = sorted(_BUCKET_AGGREGATION_OWNED_SOURCES & DEFERRED_SOURCE_KINDS)
    assert not overlap, f"Source kind(s) both owned and deferred (ambiguous routing): {overlap}"


def test_every_enum_member_is_routed_deferred_or_reserved() -> None:
    """Close the union: no enum member is silently absent from the mesh accounting.

    Every :class:`BindingSourceKind` member must be either routed by an enrolled /
    pre-mesh resolver (``_BUCKET_AGGREGATION_OWNED_SOURCES``), explicitly deferred
    (``DEFERRED_SOURCE_KINDS``), or one of the documented reserved-undeclared
    counterpart/invoice sources. A member that drifts out of all three is an
    unaccounted source kind — exactly the "neither set contains the other" gap the
    phase-2.1 ADR eliminates.
    """
    accounted = (
        _BUCKET_AGGREGATION_OWNED_SOURCES | DEFERRED_SOURCE_KINDS | {member.value for member in _MESH_UNROUTED_RESERVED}
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
    for on the mesh half — closing the union the ADR opened.
    """
    assert BindingSourceKind.BORRADOR.value in _BUCKET_AGGREGATION_OWNED_SOURCES
    assert BindingSourceKind.IVA_WALLET_DECISION.value in _BUCKET_AGGREGATION_OWNED_SOURCES


def test_reserved_mesh_members_are_not_routed_or_deferred() -> None:
    """Anti-tautology: the reserved carve-out is genuinely absent from the mesh.

    If a reserved member silently appeared in the owned or deferred set, the
    completeness assertion above would pass vacuously; this pins the carve-out to
    its real (unrouted) state so it cannot be widened to mask a routing change.
    """
    routed_or_deferred = _BUCKET_AGGREGATION_OWNED_SOURCES | DEFERRED_SOURCE_KINDS
    leaked = sorted(member.value for member in _MESH_UNROUTED_RESERVED if member.value in routed_or_deferred)
    assert not leaked, f"Reserved-undeclared member(s) unexpectedly routed/deferred on the mesh: {leaked}"

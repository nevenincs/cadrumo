"""Coverage check: every row-producer grouping in the registry has an assembler.

Walks every revision's row-producer bindings and groups them by
``selector.grouping``. Every distinct grouping value must be one of:

  * a key in the dispatcher's ``_GROUPING_DISPATCH`` table (the
    application layer can ingest it), or
  * explicitly listed in ``_INVOICE_GROUPINGS`` (those route through
    the modelo 349 / invoice + counterpart aggregation paths
    handled outside ``_row_set_assembly``).

Any grouping that satisfies neither is a registry binding whose
operator-typed detail rows have no path back into typed
observations. Adding it here without an assembler is dead weight;
the test fails loudly so the gap is fixed at declaration time
rather than at the operator's first ``--assemble-observations``
invocation.
"""

from __future__ import annotations

import pytest

from ....core.aggregation import BindingSourceKind
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.binding_selector_utils import selector_as_dict
from ...aggregation import BindingSourceDisposition, InventorySourceResolver
from ...modelo.calculation_route import CALCULATION_ROUTE_RESOLVER_OWNERSHIP, CALCULATION_ROUTE_SOURCE_DISPOSITIONS
from ..row_set_assembly import _GROUPING_DISPATCH

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# Groupings handled by the modelo 349 / invoice + counterpart aggregation
# resolvers in ``cadrumo.domain.calculations.registry`` rather than
# by the ``_row_set_assembly`` dispatcher. Listed explicitly so a new
# grouping value cannot sneak into the registry without surfacing here.
_INVOICE_GROUPINGS: frozenset[str] = frozenset({"contraparte_clave", "operator_clave", "operator_clave_period"})

# Groupings whose row values are materialised by a source resolver rather than
# by ``_GROUPING_DISPATCH`` or invoice-row materialisation.  This is a mapping,
# not an unqualified allowlist: each exception names the binding source whose
# enrolment the route proof below must establish.
_MESH_RESOLVED_GROUPINGS: dict[str, BindingSourceKind] = {
    "per_inventory_activity": BindingSourceKind.INVENTORY,
}


def _all_row_producer_groupings() -> set[str]:
    groupings: set[str] = set()
    for modelo in bundled_authority().modelos:
        for revision in modelo.revisions.values():
            for binding in revision.bindings:
                if binding.aggregation is None or binding.aggregation.op != "rows":
                    continue
                grouping = selector_as_dict(binding).get("grouping")
                if isinstance(grouping, str) and grouping:
                    groupings.add(grouping)
    return groupings


def test_every_registry_grouping_has_an_assembler_or_a_confirmed_owner() -> None:
    """A row-producer binding's grouping must be ingestable somewhere."""

    declared = _all_row_producer_groupings()
    handled = set(_GROUPING_DISPATCH) | _INVOICE_GROUPINGS | set(_MESH_RESOLVED_GROUPINGS)
    unhandled = sorted(declared - handled)

    assert not unhandled, (
        f"Row-producer bindings declare grouping values with no application-layer "
        f"ingestor: {unhandled}. Either add the grouping to the "
        f"`_row_set_assembly._GROUPING_DISPATCH` map (with a matching assembler) "
        f"or classify it in `_INVOICE_GROUPINGS` or `_MESH_RESOLVED_GROUPINGS` "
        f"only after its real owner is confirmed."
    )


def test_dispatch_table_contains_at_least_the_five_known_detail_record_groupings() -> None:
    """Sanity: the assembler dispatch table covers the five detail-record modelos.

    Pins the closed enum so a refactor that accidentally removes one of
    the five known groupings fails here, rather than at the operator's
    first invocation.
    """

    expected = {
        "per_perceptor",
        "per_perceptor_clave",
        "per_related_party_operation",
        "per_foreign_asset",
        "per_atribucion_member",
        "per_refund_operation",
    }
    missing = expected - set(_GROUPING_DISPATCH)
    assert not missing, f"`_row_set_assembly._GROUPING_DISPATCH` is missing canonical groupings: {sorted(missing)}"


def test_no_invoice_grouping_leaks_into_the_assembly_dispatch() -> None:
    """Invoice / counterpart groupings stay out of the assembler dispatch.

    Modelo 349 uses ``operator_clave`` / ``operator_clave_period`` and Modelo
    347 uses ``contraparte_clave``.  They are resolved by the invoice +
    counterpart machinery in the domain layer; routing them through
    ``_row_set_assembly`` would double-process the same data.
    """

    overlap = _INVOICE_GROUPINGS & set(_GROUPING_DISPATCH)
    assert not overlap, f"Invoice groupings must not appear in the assembler dispatch table; overlap: {sorted(overlap)}"


def test_mesh_resolved_groupings_have_a_real_enrolled_route_owner() -> None:
    """A resolver class is insufficient: the canonical calculation route must own it.

    ``InventorySourceResolver`` can exist without participating in a calculation.
    The classification is therefore tied to its exact source kind, one canonical
    mesh-stage owner, and the route's independently derived ``ENROLLED``
    disposition.  Removing the resolver from the route, assigning another owner,
    or merely leaving inventory deferred all make this gate fail.
    """

    assert _MESH_RESOLVED_GROUPINGS == {"per_inventory_activity": BindingSourceKind.INVENTORY}
    for grouping, source_kind in _MESH_RESOLVED_GROUPINGS.items():
        owners = tuple(owner for owner in CALCULATION_ROUTE_RESOLVER_OWNERSHIP if source_kind in owner.owned_sources)

        assert len(owners) == 1, f"{grouping!r} has no unique calculation-route owner for {source_kind.value!r}"
        owner = owners[0]
        assert owner.stage == "mesh", f"{grouping!r} must resolve in the calculation mesh"
        assert owner.resolver_type is InventorySourceResolver, f"{grouping!r} must use InventorySourceResolver"
        assert owner.resolver_id == InventorySourceResolver.resolver_id
        assert source_kind in InventorySourceResolver.owned_sources
        assert CALCULATION_ROUTE_SOURCE_DISPOSITIONS[source_kind] is BindingSourceDisposition.ENROLLED

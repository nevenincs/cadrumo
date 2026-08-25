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

from ....core.resources import resources
from cadrumo.domain.calculations.registry.binding_selector_utils import selector_as_dict
from .._row_set_assembly import _GROUPING_DISPATCH

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# Groupings handled by the modelo 349 / invoice + counterpart aggregation
# resolvers in ``cadrumo.domain.calculations.registry`` rather than
# by the ``_row_set_assembly`` dispatcher. Listed explicitly so a new
# grouping value cannot sneak into the registry without surfacing here.
_INVOICE_GROUPINGS: frozenset[str] = frozenset({"operator_clave", "operator_clave_period"})


def _all_row_producer_groupings() -> set[str]:
    groupings: set[str] = set()
    for modelo in resources().modelos.all():
        for revision in modelo.revisions.values():
            for binding in revision.bindings:
                if binding.aggregation is None or binding.aggregation.op != "rows":
                    continue
                grouping = selector_as_dict(binding).get("grouping")
                if isinstance(grouping, str) and grouping:
                    groupings.add(grouping)
    return groupings


def test_every_registry_grouping_has_an_assembler_or_is_invoice_handled() -> None:
    """A row-producer binding's grouping must be ingestable somewhere."""

    declared = _all_row_producer_groupings()
    handled = set(_GROUPING_DISPATCH) | _INVOICE_GROUPINGS
    unhandled = sorted(declared - handled)

    assert not unhandled, (
        f"Row-producer bindings declare grouping values with no application-layer "
        f"ingestor: {unhandled}. Either add the grouping to the "
        f"`_row_set_assembly._GROUPING_DISPATCH` map (with a matching assembler) "
        f"or extend `_INVOICE_GROUPINGS` if the modelo routes through the "
        f"invoice/counterpart resolver path."
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

    Modelo 349 uses ``operator_clave`` / ``operator_clave_period`` bindings.
    Those are resolved by the invoice + counterpart machinery in the
    domain layer; routing them through ``_row_set_assembly`` would
    double-process the same data.
    """

    overlap = _INVOICE_GROUPINGS & set(_GROUPING_DISPATCH)
    assert not overlap, f"Invoice groupings must not appear in the assembler dispatch table; overlap: {sorted(overlap)}"

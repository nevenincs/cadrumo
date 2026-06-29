"""Deferred detalle source-kind advisory tests."""

from __future__ import annotations

import pytest

from ._dormant_resolver_live_support import _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Deferred detalle kinds — related_party_operation (M232) + refund_operation (M360)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("modelo", "revision_id", "deferred_kind"),
    [
        ("232", "2018-y-siguientes", "related_party_operation"),
        ("360", "2010-y-siguientes", "refund_operation"),
    ],
)
def test_deferred_detalle_kinds_emit_unhandled_advisory_not_silent_blank(
    modelo: str,
    revision_id: str,
    deferred_kind: str,
) -> None:
    """The remaining two deferred detalle kinds surface the unhandled-source advisory.

    related_party_operation (M232 operaciones vinculadas) and refund_operation
    (M360 IVA refund operations) are Sheets-pull-only row-producer source kinds
    with no live resolver; both must emit an ``unhandled_binding_source`` advisory
    rather than a silent blank, and must NOT sit on the manual_sources allowlist.

    Asserted via the ``collect_unhandled_source_diagnostics`` boundary (mirroring
    the source-boundary tests): these revisions carry row-producer relation
    operands and the full calculate path is orthogonal to the advisory contract
    under test. With atribucion_member / foreign_asset pinned in
    test_source_boundary_and_enrollment, this covers the remaining deferred
    DEFERRED_SOURCE_KINDS. Withholding is now enrolled separately.
    """
    from ...aggregation import DEFERRED_SOURCE_KINDS, collect_unhandled_source_diagnostics

    revision = _revision(modelo, revision_id)
    assert any(str(b.source) == deferred_kind for b in revision.bindings), (
        f"M{modelo} {revision_id} must declare {deferred_kind} bindings for this test to be non-vacuous"
    )
    handled = frozenset({"relation_prefill", "profile", "borrador", "iva_wallet_decision"})
    unhandled = collect_unhandled_source_diagnostics(
        revision,
        handled_sources=handled,
        manual_sources=frozenset({"manual_input"}),
    )
    advisories = [d for d in unhandled if d.source_kind == deferred_kind and d.reason == "unhandled_binding_source"]
    assert advisories, (
        f"expected 'unhandled_binding_source' advisory for deferred kind {deferred_kind!r} on M{modelo}; "
        f"got none. unhandled={unhandled}"
    )
    assert all(d.binding_id for d in advisories)
    assert deferred_kind not in frozenset({"manual_input"})
    assert deferred_kind in DEFERRED_SOURCE_KINDS

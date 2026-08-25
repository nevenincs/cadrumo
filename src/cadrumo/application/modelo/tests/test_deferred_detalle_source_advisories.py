"""Deferred detalle source-kind advisory tests."""

from __future__ import annotations

import pytest

from ._dormant_resolver_live_support import _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Deferred detalle kinds — related_party_operation (M232), refund_operation
# (M360), donativo_donor (M182)
# ---------------------------------------------------------------------------


#: One (modelo, revision, source kind) advisory case per deferred kind. Bound to
#: ``DEFERRED_SOURCE_KINDS`` by ``test_every_deferred_kind_has_an_advisory_case``.
_DEFERRED_ADVISORY_CASES = [
    ("232", "2018-y-siguientes", "related_party_operation"),
    ("360", "2010-y-siguientes", "refund_operation"),
    ("182", "2025", "donativo_donor"),
]


@pytest.mark.parametrize(("modelo", "revision_id", "deferred_kind"), _DEFERRED_ADVISORY_CASES)
def test_deferred_detalle_kinds_emit_unhandled_advisory_not_silent_blank(
    modelo: str,
    revision_id: str,
    deferred_kind: str,
) -> None:
    """Every deferred detalle kind surfaces the unhandled-source advisory.

    related_party_operation (M232 operaciones vinculadas), refund_operation
    (M360 IVA refund operations), and donativo_donor (M182 donativos) are
    Sheets-pull-only row-producer source kinds with no live resolver. Each must
    emit an ``unhandled_binding_source`` advisory rather than a silent blank, and
    none may sit on the manual_sources allowlist — the allowlist would suppress
    the advisory. This parametrisation covers the whole of
    ``DEFERRED_SOURCE_KINDS``; the completeness assertion below fails if a kind
    is added to the set without an advisory case here.

    Asserted via the ``collect_unhandled_source_diagnostics`` boundary (mirroring
    the source-boundary tests): these revisions carry row-producer relation
    operands and the full calculate path is orthogonal to the advisory contract
    under test. Withholding, foreign_asset, and atribucion_member are enrolled
    or pinned separately.
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


def test_every_deferred_kind_has_an_advisory_case() -> None:
    """The advisory parametrisation covers every member of ``DEFERRED_SOURCE_KINDS``.

    Without this, a source kind could be added to the deferred set and ship with
    no proof that it emits a standing advisory instead of a silent blank.
    """
    from ...aggregation import DEFERRED_SOURCE_KINDS

    covered = {deferred_kind for _modelo, _revision_id, deferred_kind in _DEFERRED_ADVISORY_CASES}
    declared = {kind.value for kind in DEFERRED_SOURCE_KINDS}
    assert covered == declared, (
        f"deferred kinds without an advisory case: {sorted(declared - covered)}; "
        f"advisory cases for non-deferred kinds: {sorted(covered - declared)}"
    )

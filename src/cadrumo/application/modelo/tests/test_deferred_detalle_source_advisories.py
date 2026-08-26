"""Deferred detalle source-kind advisory tests."""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ._dormant_resolver_live_support import _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Deferred detalle kinds — related_party_operation (M232), refund_operation
# (M360), donativo_donor (M182), gasto193_contributor (M193)
# ---------------------------------------------------------------------------


#: One (modelo, revision, source kind) advisory case per registry-declared
#: deferred kind. Bound to the live registry by
#: ``test_every_registry_declared_deferred_kind_has_an_advisory_case``.
_DEFERRED_ADVISORY_CASES = [
    ("232", "2018-y-siguientes", "related_party_operation"),
    ("360", "2010-y-siguientes", "refund_operation"),
    ("182", "2025", "donativo_donor"),
    ("193", "2025-y-siguientes", "gasto193_contributor"),
]


@pytest.mark.parametrize(("modelo", "revision_id", "deferred_kind"), _DEFERRED_ADVISORY_CASES)
def test_deferred_detalle_kinds_emit_unhandled_advisory_not_silent_blank(
    modelo: str,
    revision_id: str,
    deferred_kind: str,
) -> None:
    """Every deferred detalle kind surfaces the unhandled-source advisory.

    related_party_operation (M232 operaciones vinculadas), refund_operation
    (M360 IVA refund operations), donativo_donor (M182 donativos), and
    gasto193_contributor (M193 contributor expenses) are Sheets-pull-only
    row-producer source kinds with no live resolver. Each must emit an
    ``unhandled_binding_source`` advisory rather than a silent blank, and none
    may sit on the manual_sources allowlist — the allowlist would suppress the
    advisory. The completeness assertion below binds this parametrisation to
    every deferred source kind actually declared by a live registry revision.

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


def test_every_registry_declared_deferred_kind_has_an_advisory_case() -> None:
    """The advisory parametrisation covers each registry-declared deferred kind.

    A deferred kind without a registry binding has no live calculate boundary at
    which to emit an advisory. Once it is declared by a revision, it must gain an
    explicit real-revision case here rather than silently joining the mesh.
    """
    from ...aggregation import DEFERRED_SOURCE_KINDS

    covered = {deferred_kind for _modelo, _revision_id, deferred_kind in _DEFERRED_ADVISORY_CASES}
    declared = {
        binding.source.value
        for modelo in bundled_authority().modelos
        for revision in modelo.revisions.values()
        for binding in revision.bindings
        if binding.source in DEFERRED_SOURCE_KINDS
    }
    assert covered == declared, (
        f"registry-declared deferred kinds without an advisory case: {sorted(declared - covered)}; "
        f"advisory cases for non-deferred kinds: {sorted(covered - declared)}"
    )

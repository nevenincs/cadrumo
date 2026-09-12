"""A source-backed binding with no live resolver cannot silently calculate zero.

This live zero-target gate compares committed registry source declarations with
the source kinds derived from executable calculation-route ownership. Every
unrouted declaration is named and fails; no development disposition can turn it
into an accepted advisory. A synthetic unknown source separately proves the
runtime guard bites rather than calculating a silent zero.

See Also:
    :class:`BindingSourceKind`
        Closed source-kind enum whose committed members are audited here.
    :class:`~domain.calculations.registry.RegistryQueryService`
        Domain query service that supplies the source-inventory report.
    :class:`~domain.calculations.registry.BindingDefinition`
        Binding schema mutated in the novel-source anti-tautology check.
    :func:`~application.modelo.assert_no_novel_source_kinds`
        Live calculate-path guard proved by the synthetic source case.
    :exc:`~application.modelo.ModeloAggregationBindingError`
        Loud failure raised for novel source kinds instead of silent zero.
    :mod:`~domain.calculations.registry.tests.test_source_enrollment`
        Domain companion that verifies committed registry inventory.
"""

from __future__ import annotations

import pytest

from ....core.aggregation import ROW_SET_GROUPING_FOR_BINDING_SOURCE, BindingAggregationOp, BindingSourceKind
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import BindingDefinition
from ...aggregation.source_resolution_operations import collect_unhandled_source_diagnostics
from ..action_errors import ModeloAggregationBindingError
from ..calculation_actions import assert_no_novel_source_kinds
from ..calculation_route import CALCULATION_ROUTE_ENROLLED_SOURCES

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _declared_source_kinds() -> frozenset[BindingSourceKind]:
    return frozenset(
        binding.source
        for modelo in bundled_authority().modelos
        for revision in modelo.revisions.values()
        for binding in revision.bindings
        if getattr(binding.aggregation, "op", None) is not BindingAggregationOp.ROWS
    )


def test_declared_source_kinds_are_non_empty() -> None:
    """Anti-vacuity floor: the committed registry declares source kinds to test against."""
    assert _declared_source_kinds(), "no declared source kinds — the connectivity assertions would be vacuous"


def test_every_declared_source_kind_has_executable_route_ownership() -> None:
    """Name every current declaration whose source has no production owner."""
    declared = _declared_source_kinds()
    uncovered = sorted(kind.value for kind in declared - CALCULATION_ROUTE_ENROLLED_SOURCES)
    assert not uncovered, "registry binding sources without executable calculation-route ownership:\n" + "\n".join(
        f"  + {kind}" for kind in uncovered
    )


def test_novel_source_binding_raises_not_silent_zero() -> None:
    """A binding whose source is unknown to the live mesh raises rather than blanking.

    ``model_construct`` bypasses the ``BindingSourceKind`` field validation so a
    source token absent from the enrolled and deferred sets can be injected —
    exactly the TOML-authoring mistake the gate must convert from a silent zero
    into a loud ``ModeloAggregationBindingError`` at calculate time.
    """
    # Resolved from (modelo, filing year, period) rather than indexed by a
    # literal revision id: AEAT re-cuts revision layouts, and this modelo's
    # a broad M303 revision was decomposed into four narrower revisions.
    revision = bundled_authority().snapshot("303", filing_year=2025, period="1T").revision
    synthetic = BindingDefinition.model_construct(
        id="synthetic-missing-source-binding",
        provider={"kind": "synthetic_unrouted_source_qqq"},
        value={"data_type": "money", "channel": "decimal"},
    )
    patched = revision.model_copy(update={"bindings": (*revision.bindings, synthetic)})

    with pytest.raises(ModeloAggregationBindingError) as exc_info:
        assert_no_novel_source_kinds(patched)

    context = exc_info.value.context
    assert context is not None
    novel_kinds = context["novel_source_kinds"]
    assert isinstance(novel_kinds, list)
    assert "synthetic_unrouted_source_qqq" in novel_kinds


def test_row_producing_binding_uses_its_detail_row_channel() -> None:
    """An unknown row source does not need a scalar source-mesh resolver."""
    revision = bundled_authority().snapshot("232", filing_year=2025, period="0A").revision
    row_binding = next(
        binding
        for binding in revision.bindings
        if getattr(binding.aggregation, "op", None) is BindingAggregationOp.ROWS
    )
    synthetic = row_binding.model_copy(update={"source": "synthetic_row_source_qqq"})
    patched = revision.model_copy(update={"bindings": (*revision.bindings, synthetic)})

    assert_no_novel_source_kinds(patched)


def _deferred_binding() -> BindingDefinition:
    grouping = ROW_SET_GROUPING_FOR_BINDING_SOURCE[BindingSourceKind.RELATED_PARTY_OPERATION]
    return BindingDefinition.model_validate(
        {
            "id": "synthetic-deferred-related-party-rows",
            "provider": {"kind": "related_party_operation", "fact": "row_field", "row_field": "counterparty_tax_id"},
            "value": {"data_type": "money", "channel": "row_set", "row_grouping": grouping},
            "aggregation": {"op": "rows"},
            "legal_refs": ("ley-27-2014:art-18",),
            "source_refs": ("aeat-manual",),
        },
    )


def test_deferred_source_binding_is_not_novel_and_is_not_exempted_by_row_shape() -> None:
    """A kind registered ``deferred`` passes the novel gate on its registration, not on a ROWS exemption."""
    revision = bundled_authority().snapshot("303", filing_year=2025, period="1T").revision
    patched = revision.model_copy(update={"bindings": (*revision.bindings, _deferred_binding())})

    assert_no_novel_source_kinds(patched)

    scalar_novel = BindingDefinition.model_construct(
        id="synthetic-scalar-novel",
        provider=_deferred_binding().provider.model_copy(update={"kind": "synthetic_unrouted_source_qqq"}),
    )
    with pytest.raises(ModeloAggregationBindingError):
        assert_no_novel_source_kinds(revision.model_copy(update={"bindings": (*revision.bindings, scalar_novel)}))


def test_deferred_source_binding_surfaces_as_deferred_diagnostic() -> None:
    revision = bundled_authority().snapshot("303", filing_year=2025, period="1T").revision
    patched = revision.model_copy(update={"bindings": (_deferred_binding(),)})

    diagnostics = collect_unhandled_source_diagnostics(patched, handled_sources=frozenset())

    assert [d.reason for d in diagnostics] == ["deferred_binding_source"]
    assert diagnostics[0].binding_id == "synthetic-deferred-related-party-rows"
    assert diagnostics[0].source_kind == "related_party_operation"

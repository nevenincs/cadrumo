"""Tests for the audit joining declared terminal origins to resolved provenance.

Every case builds a real :class:`ModeloRevision`, a real
:class:`CalculationSourceResolution`, and real
:class:`CalculationSourceProvenance` rows: the whole point of the audit is that
it reads what a resolver actually produced, so substituting a double for either
half would leave the join untested. The conforming case is carried beside the
violations because an audit that fires on everything reports nothing.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.aggregation import (
    BindingAggregation,
    BindingAggregationOp,
    BindingSourceKind,
    CalculationSourceLineageRole,
)
from ....domain.calculations.registry.binding_terminal_origin import (
    TerminalOriginClass,
    TerminalOriginExpectation,
)
from ....domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_references import PeriodSelector
from ....domain.iva.flow import IvaFlowDirection
from ....domain.iva.schema import IvaCashAccountingTreatment, IvaCategory, IvaLedgerObservationRole, IvaRateKind
from ..source_mesh import CalculationSourceProvenance, CalculationSourceResolution
from ..terminal_origin_audit import collect_terminal_origin_diagnostics

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LEGAL_REFS = ("ley-37-1992:art-1",)
_SOURCE_REFS = ("aeat-modelo-303-diseno-registro",)
_PROFILE_BINDING_ID = "test-profile-binding"
_LEDGER_BINDING_ID = "test-ledger-binding"


def _profile_binding(terminal_origins: tuple[TerminalOriginExpectation, ...] = ()) -> BindingDefinition:
    return BindingDefinition(
        id=_PROFILE_BINDING_ID,
        provider={"kind": "profile", "profile_key": "declarante.nif"},
        value={"data_type": "money", "channel": "decimal"},
        aggregation=BindingAggregation(op=BindingAggregationOp.COPY),
        terminal_origins=terminal_origins,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


def _ledger_binding() -> BindingDefinition:
    return BindingDefinition(
        id=_LEDGER_BINDING_ID,
        provider={
            "kind": "ledger_iva_aggregation",
            "categories": (IvaCategory.DOMESTIC_GENERAL,),
            "rate_kinds": (IvaRateKind.GENERAL,),
            "flow_direction": IvaFlowDirection.REPERCUTIDO,
            "observation_roles": (IvaLedgerObservationRole.SETTLEMENT,),
            "cash_accounting_treatments": (IvaCashAccountingTreatment.NONE,),
            "fact": "iva_amount_sum",
        },
        value={"data_type": "money", "channel": "decimal"},
        aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


def _revision(*bindings: BindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id="terminal-origin-audit-test",
        localization_key="test.schema.revision.terminal-origin-audit-test.label",
        valid_from=date(2025, 1, 1),
        period_selector=PeriodSelector(years=(2025,), periods=("1T",)),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
        bindings=bindings,
    )


def _profile_provenance(
    *,
    source_ref: str,
    terminal_origin: TerminalOriginClass | None,
    fingerprint: str | None = "sha256:abc",
) -> CalculationSourceProvenance:
    return CalculationSourceProvenance(
        resolver_id="profile",
        resolved_binding_source=BindingSourceKind.PROFILE,
        contributor_source_kind=BindingSourceKind.PROFILE.value,
        contributor_binding_source=BindingSourceKind.PROFILE,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref=source_ref,
        parent_source_ref=None,
        fingerprint=fingerprint,
        terminal_origin=terminal_origin,
    )


def _profile_resolution(*provenance: CalculationSourceProvenance) -> CalculationSourceResolution:
    return CalculationSourceResolution(
        resolver_id="profile",
        owned_sources=(BindingSourceKind.PROFILE,),
        binding_values={_PROFILE_BINDING_ID: Decimal("100.00")},
        provenance=provenance,
    )


def test_a_conforming_resolution_earns_no_diagnostic() -> None:
    """One fingerprinted profile-field node satisfies the profile family's default."""
    resolution = _profile_resolution(
        _profile_provenance(source_ref="profile:b:1", terminal_origin=TerminalOriginClass.PROFILE_FIELD),
    )

    assert collect_terminal_origin_diagnostics(_revision(_profile_binding()), resolution) == ()


def test_an_origin_class_the_declaration_does_not_admit_is_reported() -> None:
    """A profile binding resolved from a derived calculation is a route nobody declared."""
    resolution = _profile_resolution(
        _profile_provenance(source_ref="profile:b:1", terminal_origin=TerminalOriginClass.DERIVED_CALCULATION),
    )

    diagnostics = collect_terminal_origin_diagnostics(_revision(_profile_binding()), resolution)

    reasons = {diagnostic.reason for diagnostic in diagnostics}
    assert reasons == {"terminal_origin_mismatch"}
    assert any("derived_calculation" in diagnostic.message for diagnostic in diagnostics)
    assert all(diagnostic.binding_id == _PROFILE_BINDING_ID for diagnostic in diagnostics)
    assert all(diagnostic.binding_source is BindingSourceKind.PROFILE for diagnostic in diagnostics)


def test_a_value_resolved_with_no_terminal_origin_at_all_is_reported() -> None:
    """A value arriving with no declared origin is the gap a complete total hides best."""
    resolution = _profile_resolution(_profile_provenance(source_ref="profile:b:1", terminal_origin=None))

    diagnostics = collect_terminal_origin_diagnostics(_revision(_profile_binding()), resolution)

    assert [diagnostic.reason for diagnostic in diagnostics] == ["terminal_origin_mismatch"]
    assert "no 'profile_field' terminal origin" in diagnostics[0].message


def test_a_value_resolved_with_no_provenance_at_all_is_reported() -> None:
    """Cardinality has teeth in the zero direction: emptiness is never silently legitimate."""
    resolution = _profile_resolution()

    diagnostics = collect_terminal_origin_diagnostics(_revision(_profile_binding()), resolution)

    assert [diagnostic.reason for diagnostic in diagnostics] == ["terminal_origin_mismatch"]


def test_more_than_one_terminal_node_violates_an_exactly_one_expectation() -> None:
    """An authored ``exactly_one`` refuses a second node for the same value."""
    authored = (
        TerminalOriginExpectation(
            source_class=TerminalOriginClass.PROFILE_FIELD,
            role="primary",
            cardinality="exactly_one",
            fingerprint="optional",
        ),
    )
    resolution = _profile_resolution(
        _profile_provenance(source_ref="profile:b:1", terminal_origin=TerminalOriginClass.PROFILE_FIELD),
        _profile_provenance(source_ref="profile:b:2", terminal_origin=TerminalOriginClass.PROFILE_FIELD),
    )

    diagnostics = collect_terminal_origin_diagnostics(_revision(_profile_binding(authored)), resolution)

    assert [diagnostic.reason for diagnostic in diagnostics] == ["terminal_origin_mismatch"]
    assert "exactly one" in diagnostics[0].message


def test_several_terminal_nodes_satisfy_an_at_least_one_expectation() -> None:
    """A fold rests on as many nodes as the taxpayer has facts, which is not a defect."""
    resolution = _profile_resolution(
        _profile_provenance(source_ref="profile:b:1", terminal_origin=TerminalOriginClass.PROFILE_FIELD),
        _profile_provenance(source_ref="profile:b:2", terminal_origin=TerminalOriginClass.PROFILE_FIELD),
    )

    assert collect_terminal_origin_diagnostics(_revision(_profile_binding()), resolution) == ()


def test_a_missing_evidence_fingerprint_is_reported_where_the_declaration_requires_one() -> None:
    """A profile field is one persisted record; resolving it unhashed loses the evidence."""
    resolution = _profile_resolution(
        _profile_provenance(
            source_ref="profile:b:1",
            terminal_origin=TerminalOriginClass.PROFILE_FIELD,
            fingerprint=None,
        ),
    )

    diagnostics = collect_terminal_origin_diagnostics(_revision(_profile_binding()), resolution)

    assert [diagnostic.reason for diagnostic in diagnostics] == ["terminal_origin_mismatch"]
    assert "no evidence fingerprint" in diagnostics[0].message


def test_a_binding_the_resolution_produced_no_value_for_is_not_audited() -> None:
    """The audit speaks about values that arrived, never about values nobody resolved."""
    resolution = _profile_resolution(
        _profile_provenance(source_ref="profile:b:1", terminal_origin=TerminalOriginClass.PROFILE_FIELD),
    )

    diagnostics = collect_terminal_origin_diagnostics(
        _revision(_profile_binding(), _ledger_binding()),
        resolution,
    )

    assert diagnostics == ()

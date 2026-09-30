"""The registered modelo query wire shape preserves every canonical read axis."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.ledger.preflight import LedgerPreflightIssue, LedgerPreflightIssueReason
from cadrumo.application.modelo.data_inventory import DataInventoryCasilla, DataInventoryChecklist
from cadrumo.application.modelo.query_read_operation import (
    ModeloBindingsListRequest,
    ModeloQueryReadPorts,
    ModeloReadinessOperationRequest,
    ModeloReadinessProjection,
    ModeloRequiresProjection,
    _requested_scope,
    build_modelo_bindings_list_definition,
    build_modelo_bindings_list_registration,
    build_modelo_bindings_resolve_definition,
    build_modelo_bindings_resolve_registration,
    build_modelo_readiness_definition,
    build_modelo_readiness_registration,
    build_modelo_requires_definition,
    build_modelo_requires_registration,
)
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.state_projection import (
    ProjectionModeloBindingRequirement,
    ProjectionModeloReadiness,
)
from cadrumo.application.user_profile.commands import ProfilePreflightRequirement
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.period import Period
from cadrumo.entrypoints.cli.runtime_modelo_query_read import (
    to_data_inventory_checklist,
    to_modelo_readiness_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_public_query_schemas_compile_as_closed_registered_contracts() -> None:
    """The complete registry accepts every closed query and settlement shape."""
    builders = (
        (build_modelo_bindings_list_definition, build_modelo_bindings_list_registration),
        (build_modelo_bindings_resolve_definition, build_modelo_bindings_resolve_registration),
        (build_modelo_requires_definition, build_modelo_requires_registration),
    )
    definitions = []
    registrations = []
    for define, register in builders:
        definition = define()
        registration = register(definition)
        contract = registration.contract
        assert contract.definition_id == definition.definition_id
        assert contract.result_schema is not None
        definitions.append(definition)
        registrations.append(registration)

    def unavailable_read_ports(*, bucket_id: str) -> ModeloQueryReadPorts:
        raise AssertionError(f"read ports must not be opened by schema enrollment for {bucket_id}")

    readiness = build_modelo_readiness_definition(unavailable_read_ports)
    definitions.append(readiness)
    registrations.append(build_modelo_readiness_registration(readiness))
    registry = OperationRegistry(
        definitions=tuple(sorted(definitions, key=lambda item: item.definition_id)),
        public_registrations=tuple(sorted(registrations, key=lambda item: item.contract.definition_id)),
    )
    assert {item.definition_id for item in registry.definitions} == {
        "modelo.bindings.list",
        "modelo.bindings.resolve",
        "modelo.requires",
        "modelo.readiness",
    }


def test_scope_requires_all_periods_when_a_read_is_not_exact() -> None:
    """A missing-binding or periodless readiness query cannot borrow one period."""
    profile_id = uuid4()
    annual = Period.from_year_and_code(2026, "0A")
    assert _requested_scope(ModeloBindingsListRequest(profile_id=profile_id)) == (frozenset(), True, False)
    assert _requested_scope(ModeloBindingsListRequest(profile_id=profile_id, missing=True)) == (
        frozenset(),
        True,
        True,
    )
    assert _requested_scope(
        ModeloBindingsListRequest(profile_id=profile_id, year=2026, period_code="0A", missing=True)
    ) == (
        frozenset({annual}),
        False,
        False,
    )
    assert _requested_scope(ModeloReadinessOperationRequest(profile_id=profile_id, modelo="303", filing_year=2026)) == (
        frozenset(),
        True,
        True,
    )
    assert _requested_scope(
        ModeloReadinessOperationRequest(
            profile_id=profile_id,
            modelo="303",
            filing_year=2026,
            period=PublicPeriod.from_period(annual),
        )
    ) == (frozenset({annual}), False, False)


def test_unscoped_temporal_binding_selection_refuses_before_submission() -> None:
    """An as-of date needs a year so the authority cannot silently list nothing."""
    with pytest.raises(ValidationError):
        ModeloBindingsListRequest(profile_id=uuid4(), as_of=date(2026, 1, 1))


def test_readiness_wire_round_trip_preserves_gaps_and_absent_ledger_verdict() -> None:
    """The existing CLI renderer receives the same checked and unchecked axes."""
    profile_id = uuid4()
    report = ProjectionModeloReadiness(
        profile_id=str(profile_id),
        modelo="303",
        revision_id="303-2026",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        missing=(
            ProfilePreflightRequirement(
                selector="identity.tax_id",
                section_key="identity",
                field_key="tax_id",
                label="Tax ID",
                legal_refs=("article-1",),
                modelos=("303",),
            ),
        ),
        profile_ready=False,
        per_operation_requirements_assessed=False,
        profile_refusal="setup incomplete",
        registry_ready=True,
        binding_ready=False,
        missing_bindings=(
            ProjectionModeloBindingRequirement(
                binding_id="input-iva",
                source=BindingSourceKind.PROFILE,
                input_channel="decimal",
            ),
        ),
        ledger_preflight_required=True,
        ledger_ready=None,
        ledger_checked_transaction_count=0,
        ledger_issues=(
            LedgerPreflightIssue(
                transaction_id="__period__",
                reason=LedgerPreflightIssueReason.UNSUPPORTED_PERIOD,
                detail="Period unavailable",
            ),
        ),
        ready=False,
    )
    public = ModeloReadinessProjection.from_report(profile_id, report, language=OutputLanguage.HU)
    parsed = ModeloReadinessProjection.model_validate_json(public.model_dump_json())
    assert parsed.per_operation_requirements_assessed is False
    assert parsed.ledger_ready is None
    assert parsed.language is OutputLanguage.HU
    assert to_modelo_readiness_report(parsed) == report


def test_inventory_wire_round_trip_keeps_every_bucket_and_provenance() -> None:
    """A checklist renderer sees all nine sections and unresolved profile facts."""
    row = DataInventoryCasilla(
        casilla_id="casilla-1",
        number="1",
        label="Amount",
        legal_refs=("article-1",),
        source_refs=("source-1",),
        binding_id="binding-1",
        binding_source="profile",
    )
    report = DataInventoryChecklist(
        modelo="303",
        revision_id="303-2026",
        filing_year=2026,
        period="1T",
        required_manual=(row,),
        optional_manual=(),
        detail_row_fields=(),
        ledger_derivable=(),
        profile_derivable=(row,),
        previous_filing=(),
        relation_prefill=(),
        live_observation=(),
        unbucketed_sources=(row,),
        unresolved_profile_bindings=("binding-1",),
        unresolved_profile_keys=("identity.tax_id",),
        profile_checked=True,
    )
    public = ModeloRequiresProjection.from_checklist(uuid4(), report, language=OutputLanguage.CA)
    parsed = ModeloRequiresProjection.model_validate_json(public.model_dump_json())
    assert parsed.language is OutputLanguage.CA
    assert to_data_inventory_checklist(parsed) == report

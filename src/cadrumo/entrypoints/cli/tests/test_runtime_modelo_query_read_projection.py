"""The registered modelo query wire shape preserves every canonical read axis."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
import typer
from pydantic import BaseModel, ValidationError
from typer.main import get_command

from cadrumo.application.ledger.preflight import LedgerPreflightIssue, LedgerPreflightIssueReason
from cadrumo.application.modelo.data_inventory import DataInventoryCasilla, DataInventoryChecklist
from cadrumo.application.modelo.query_read_operation import (
    ModeloBindingsListProjection,
    ModeloBindingsListRequest,
    ModeloBindingsResolveProjection,
    ModeloBindingsResolveRequest,
    ModeloQueryReadPorts,
    ModeloReadinessOperationRequest,
    ModeloReadinessProjection,
    ModeloRequiresProjection,
    ModeloRequiresRequest,
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
from cadrumo.application.runtime.contracts import RuntimeRefusalCode
from cadrumo.application.state_projection import (
    ProjectionModeloBindingRequirement,
    ProjectionModeloReadiness,
)
from cadrumo.application.user_profile.commands import ProfilePreflightRequirement
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.core.period import Period
from cadrumo.entrypoints.cli import runtime_modelo_query_read as bridge
from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError
from cadrumo.entrypoints.cli.registered_operation_contracts import RegisteredOperationCompletion
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
    public = ModeloReadinessProjection.from_report(
        profile_id, report, language=OutputLanguage.HU, authority_generation="a" * 64
    )
    parsed = ModeloReadinessProjection.model_validate_json(public.model_dump_json())
    assert parsed.per_operation_requirements_assessed is False
    assert parsed.ledger_ready is None
    assert parsed.language is OutputLanguage.HU
    assert parsed.authority_generation == "a" * 64
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
    public = ModeloRequiresProjection.from_checklist(
        uuid4(), report, language=OutputLanguage.CA, authority_generation="a" * 64
    )
    parsed = ModeloRequiresProjection.model_validate_json(public.model_dump_json())
    assert parsed.language is OutputLanguage.CA
    assert parsed.authority_generation == "a" * 64
    assert to_data_inventory_checklist(parsed) == report


def _requires_projection(request: ModeloRequiresRequest) -> ModeloRequiresProjection:
    report = DataInventoryChecklist(
        modelo=request.modelo,
        revision_id="303-2026",
        filing_year=request.period.filing_year,
        period=request.period.code,
        required_manual=(),
        optional_manual=(),
        detail_row_fields=(),
        ledger_derivable=(),
        profile_derivable=(),
        previous_filing=(),
        relation_prefill=(),
        live_observation=(),
        unbucketed_sources=(),
        unresolved_profile_bindings=(),
        unresolved_profile_keys=(),
        profile_checked=True,
    )
    return ModeloRequiresProjection.from_checklist(
        request.profile_id, report, language=request.language, authority_generation="a" * 64
    )


def _requires_request() -> ModeloRequiresRequest:
    return ModeloRequiresRequest(
        profile_id=uuid4(),
        modelo="303",
        period=PublicPeriod.from_period(Period.from_year_and_code(2026, "1T")),
        language=OutputLanguage.CA,
    )


_QueryRequest = (
    ModeloBindingsListRequest | ModeloBindingsResolveRequest | ModeloRequiresRequest | ModeloReadinessOperationRequest
)


def _query_case(route: str) -> tuple[_QueryRequest, BaseModel]:
    request = _requires_request()
    if route == "requires":
        return request, _requires_projection(request)
    if route == "bindings_list":
        listing = ModeloBindingsListRequest(profile_id=request.profile_id, modelo="303", year=2026, period_code="1T")
        return listing, ModeloBindingsListProjection(
            profile_id=listing.profile_id,
            authority_generation="a" * 64,
            modelo_filter=listing.modelo,
            year_filter=listing.year,
            period_filter=listing.period_code,
            missing_filter=False,
            catalogue_only=False,
            known_modelos=("303",),
            binding_count=0,
            bindings=(),
        )
    if route == "bindings_resolve":
        resolving = ModeloBindingsResolveRequest(profile_id=request.profile_id, modelo="303", period=request.period)
        return resolving, ModeloBindingsResolveProjection(
            profile_id=resolving.profile_id,
            authority_generation="a" * 64,
            modelo="303",
            revision="303-2026",
            filing_year=2026,
            period="1T",
            override_count=0,
            binding_count=0,
            bindings=(),
        )
    assert route == "readiness"
    readiness = ModeloReadinessOperationRequest(
        profile_id=request.profile_id,
        modelo="303",
        filing_year=2026,
        period=request.period,
        revision_id="303-2026",
        language=request.language,
    )
    report = ProjectionModeloReadiness(
        profile_id=str(request.profile_id),
        modelo="303",
        revision_id="303-2026",
        filing_year=2026,
        period=request.period.to_period(),
        profile_ready=True,
        per_operation_requirements_assessed=True,
        ready=True,
    )
    return readiness, ModeloReadinessProjection.from_report(
        request.profile_id, report, language=request.language, authority_generation="a" * 64
    )


def _read_query(ctx: typer.Context, request: _QueryRequest) -> BaseModel:
    if isinstance(request, ModeloBindingsListRequest):
        return bridge.read_modelo_bindings_list(ctx, request, expected_authority_generation="a" * 64)
    if isinstance(request, ModeloBindingsResolveRequest):
        return bridge.read_modelo_bindings_resolve(ctx, request, expected_authority_generation="a" * 64)
    if isinstance(request, ModeloReadinessOperationRequest):
        return bridge.read_modelo_readiness(ctx, request, expected_authority_generation="a" * 64)
    return bridge.read_modelo_requires(ctx, request, expected_authority_generation="a" * 64)


@pytest.mark.parametrize("route", ["bindings_list", "bindings_resolve", "requires", "readiness"])
@pytest.mark.parametrize("matching_generation", [True, False])
def test_query_release_correlates_logical_authority_generation(
    monkeypatch: pytest.MonkeyPatch, route: str, matching_generation: bool
) -> None:
    """A successful read from another logical pin remains a correlated refusal."""
    request, projection = _query_case(route)
    if not matching_generation:
        projection = type(projection).model_validate(
            projection.model_dump(mode="python") | {"authority_generation": "b" * 64}
        )
    monkeypatch.setattr(bridge, "active_bucket_id_or_refuse", lambda: str(request.profile_id))
    monkeypatch.setattr(
        bridge,
        "require_profile_client",
        lambda *_args, **_kwargs: SimpleNamespace(profile_id=request.profile_id),
    )
    submitted: list[BaseModel] = []

    def submit(_client: object, operand: BaseModel, **_kwargs: object) -> RegisteredOperationCompletion[BaseModel]:
        submitted.append(operand)
        return RegisteredOperationCompletion(
            operation_id="c" * 64,
            projection=projection,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    app = typer.Typer()
    app.command("query")(lambda: None)
    ctx = typer.Context(get_command(app))
    if matching_generation:
        result = _read_query(ctx, request)
        assert result is projection
    else:
        with pytest.raises(CliRefusedBoundaryError) as caught:
            _read_query(ctx, request)
        assert caught.value.context is not None
        assert caught.value.context["operation_id"] == "c" * 64
        assert caught.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
        assert caught.value.context["effect"] == OperationEffect.NONE.value
        assert caught.value.context["terminal_condition"] == OperationTerminalCondition.SUCCEEDED.value
    assert submitted == [request]


@pytest.mark.parametrize("route", ["bindings_list", "bindings_resolve", "requires", "readiness"])
@pytest.mark.parametrize("generation", [None, "not-a-digest"])
def test_query_wire_refuses_missing_or_malformed_authority_generation(route: str, generation: str | None) -> None:
    """The logical pin is required even when every inventory field is valid."""
    _request, projection = _query_case(route)
    document = projection.model_dump(mode="json")
    if generation is None:
        del document["authority_generation"]
    else:
        document["authority_generation"] = generation
    with pytest.raises(ValidationError, match="authority_generation"):
        type(projection).model_validate_json(json.dumps(document))

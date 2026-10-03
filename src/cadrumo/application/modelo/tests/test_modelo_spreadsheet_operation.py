"""Focused spreadsheet worker custody and effect tests; no provider acceptance claim."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn, cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.config import override_settings
from ....core.hashing import canonical_json_bytes, sha256_hex
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.time.clock import now
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.detail_record_bindings import (
    AtributionMemberObservation,
    Modelo720RowObservation,
)
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.gasto193_bindings import Gasto193Observation
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.calculations.registry.relations import relation_source_requirements
from ....domain.calculations.registry.withholding296_bindings import Withholding296Observation
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.capabilities import OperationRequestStoragePolicy
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.operation_definition import OperationDefinition
from ...operations.owner import OperationExecutorContext
from ...operations.public_period import PublicPeriod
from ...operations.refusal_evidence import OperationRefusalEvidence
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...storage.calc_sheets.engine import build_export_plan, collect_row_sets
from ...storage.calc_sheets.parity_harness import OperatorInputScenario
from ...storage.calc_sheets.row_set_assembly import assemble_row_sets_for_snapshot
from ...user_profile.access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessDenialCode,
    AccessDenied,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..export_sink import LocalFileExportReceipt, LocalFileExportSink, ModeloExportOutputPathError
from ..modelo_spreadsheet_observations import (
    CanonicalSpreadsheetAssembledObservation,
    project_modelo_spreadsheet_observation,
)
from ..modelo_spreadsheet_operation import (
    build_modelo_spreadsheet_definitions,
)
from ..modelo_spreadsheet_operation_contracts import (
    MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE,
    MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID,
    ModeloSpreadsheetCalculateOutcome,
    ModeloSpreadsheetCalculateRequest,
    ModeloSpreadsheetExecutionResult,
    ModeloSpreadsheetExportOutcome,
    ModeloSpreadsheetExportRequest,
    ModeloSpreadsheetOperationPorts,
    ModeloSpreadsheetOperationPortsFactory,
    ModeloSpreadsheetPullOutcome,
    ModeloSpreadsheetPullRequest,
    ModeloSpreadsheetVerifyRequest,
    SpreadsheetMutationHandoff,
    SpreadsheetOutputPathRefusal,
    SpreadsheetProviderAdmission,
    SpreadsheetRowIngressRefusal,
    SpreadsheetSnapshotMismatchRefusal,
    SpreadsheetVerifyAcknowledgement,
)
from ..modelo_spreadsheet_operation_projections import (
    SpreadsheetCalculateFacts,
    SpreadsheetComputedCasilla,
    SpreadsheetRowSet,
    SpreadsheetRowSetCell,
    SpreadsheetVerifyFacts,
)
from ..modelo_spreadsheet_operation_scenario import decode_modelo_spreadsheet_scenario
from ..modelo_spreadsheet_registration import (
    build_modelo_spreadsheet_registration,
)
from .m036_operation_support import PROFILE_ID as POLICY_PROFILE_ID
from .m036_operation_support import policy_decision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_PERIOD = PublicPeriod(filing_year=2026, code="1T")


class _Scope:
    def __init__(self, *, refuse: bool = False) -> None:
        self.held = False
        self.admissions = 0
        self.refuse = refuse

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        if self.refuse:
            raise ProfileAccessRefusedError(AccessDenialCode.SESSION_INACTIVE)
        assert not self.held
        self.admissions += 1
        self.held = True
        try:
            yield
        finally:
            self.held = False


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def phase(self, _phase: str) -> None:
        pass

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Operands:
    def __init__(self) -> None:
        self.rows: list[BaseModel] = []

    async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        self.rows.append(operand)
        return "f" * 64


def _request(definition_id: str, payload: BaseModel) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition_id, subject_ref=profile_operation_subject(str(_PROFILE)), payload=payload
    )


def _context(
    request: OperationRequest[BaseModel],
    operation: PinnedAuthorityOperation,
    scope: _Scope,
    events: _Events,
    operands: _Operands,
) -> OperationExecutorContext:
    return cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=OperationIdentity(
                    operation_id="a" * 64, definition_id=request.definition_id, subject_ref=request.subject_ref
                ),
                authority_operation=operation,
                cancellation=scope,
                events=events,
                operands=operands,
            ),
        ),
    )


def _unavailable(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("unused spreadsheet service must not be invoked")


def _ports(operation: PinnedAuthorityOperation) -> ModeloSpreadsheetOperationPorts:
    return ModeloSpreadsheetOperationPorts(
        profile_id=_PROFILE,
        operation=operation,
        materialize=lambda _plan: b"canonical-workbook-materializer-output",
        plan_builder=build_export_plan,
        pull=_unavailable,
        calculate=_unavailable,
        verify=_unavailable,
    )


def _factory(ports: ModeloSpreadsheetOperationPorts) -> ModeloSpreadsheetOperationPortsFactory:
    def factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> ModeloSpreadsheetOperationPorts:
        assert profile_id == _PROFILE and operation is ports.operation
        return ports

    return factory


def _definition(factory: ModeloSpreadsheetOperationPortsFactory, definition_id: str) -> OperationDefinition:
    return next(row for row in build_modelo_spreadsheet_definitions(factory) if row.definition_id == definition_id)


def test_every_public_spreadsheet_schema_compiles_with_secure_requests() -> None:
    """Exercise the actual registry's closed-schema validation for all four leaves."""
    definitions = build_modelo_spreadsheet_definitions(_unavailable)
    registrations = tuple(build_modelo_spreadsheet_registration(row) for row in definitions)
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
    assert {row.definition_id for row in definitions} == {
        MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID,
        MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID,
        MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID,
        MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID,
    }
    for row in definitions:
        assert row.capabilities.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
        registration = registry.lookup_public_registration(row.definition_id)
        assert any(binding.model_type is row.request_type for binding in registration.schema_bindings)
        assert registration.contract.result_schema is not None
        assert row.result_type is ModeloSpreadsheetExecutionResult
        assert len(registration.schema_bindings) == 2
        assert row.permitted_frontends == frozenset({OperationFrontendProjection.CLI})


def test_calculate_period_and_result_disclosure_are_exact(authority_operation: PinnedAuthorityOperation) -> None:
    definition = _definition(_unavailable, MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID)
    registration = build_modelo_spreadsheet_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = _request(
        definition.definition_id,
        ModeloSpreadsheetCalculateRequest(
            profile_id=_PROFILE, modelo="130", period=_PERIOD, spreadsheet_id="remote-workbook"
        ),
    )
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=authority_operation,
    )
    resolved = resolve_operation_access(registry=registry, request=request, context=context)
    assert resolved.request.periods == frozenset({_PERIOD.to_period()})
    assert AccessAction.COMMIT in resolved.policy.actions
    assert not resolved.policy.requires_all_periods
    assert {item.category for item in resolved.policy.disclosures} == {DisclosureCategory.TAX_VALUES}
    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_operation_access(registry=registry, request=request, context=replace(context, profile_id=uuid4()))
    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_scenario_reference_is_paired_and_original_decoder_preserves_defaults(tmp_path: Path) -> None:
    path = tmp_path / "scenario.json"
    with pytest.raises(ValidationError):
        ModeloSpreadsheetVerifyRequest(profile_id=_PROFILE, modelo="130", period=_PERIOD, scenario_path=str(path))
    assert decode_modelo_spreadsheet_scenario(None, source_path=None).scenario_label == "empty-defaults"
    scenario = decode_modelo_spreadsheet_scenario(
        b'{"inputs_by_casilla_id":{"base_imponible":"125.00"},"bindings":[],"enum_bindings":{"region":42},"scenario_label":""}',
        source_path=path,
    )
    assert str(scenario.inputs_by_casilla_id["base_imponible"]) == "125.00"
    assert scenario.bindings == {} and scenario.enum_bindings == {"region": "42"}
    assert scenario.scenario_label == "scenario"


def test_foreign_worker_profile_is_refused_before_port_construction(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    request = _request(
        MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID,
        ModeloSpreadsheetPullRequest(
            profile_id=_PROFILE, modelo="130", period=_PERIOD, spreadsheet_id="remote-workbook"
        ),
    )
    scope, events, operands = _Scope(), _Events(), _Operands()
    definition = _definition(_unavailable, request.definition_id)
    with override_settings(cadrumo_active_profile=str(uuid4())), pytest.raises(ProfileAccessRefusedError) as error:
        asyncio.run(
            definition.executor_factory.create().execute(
                request, _context(request, authority_operation, scope, events, operands)
            )
        )
    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert not operands.rows and not events.effects and scope.admissions == 0


def test_calculate_admits_provider_without_retaining_commit_or_local_effect(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    scope, events, operands = _Scope(), _Events(), _Operands()

    def calculate(
        request: ModeloSpreadsheetCalculateRequest, *, admit_provider: SpreadsheetProviderAdmission
    ) -> SpreadsheetCalculateFacts:
        admit_provider()
        assert not scope.held and scope.admissions == 1
        return SpreadsheetCalculateFacts(
            spreadsheet_id=request.spreadsheet_id,
            metadata_match="matches",
            cells_read=1,
            operator_edits_populated=1,
            binding_edits_populated=0,
            relation_edits_populated=0,
            computed=(
                SpreadsheetComputedCasilla(
                    casilla_id="base_imponible", value="125.00", formula_id=None, legal_refs=(), source_refs=()
                ),
            ),
        )

    ports = replace(_ports(authority_operation), calculate=calculate)
    definition = _definition(_factory(ports), MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID)
    request = _request(
        definition.definition_id,
        ModeloSpreadsheetCalculateRequest(
            profile_id=_PROFILE, modelo="130", period=_PERIOD, spreadsheet_id="remote-workbook"
        ),
    )
    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        asyncio.run(
            definition.executor_factory.create().execute(
                request, _context(request, authority_operation, scope, events, operands)
            )
        )
    assert events.effects == [OperationEffect.NONE]
    execution_result = operands.rows[0]
    assert isinstance(execution_result, ModeloSpreadsheetExecutionResult)
    projection = execution_result.projection
    assert isinstance(projection, ModeloSpreadsheetCalculateOutcome)
    assert (
        projection.result is not None
        and projection.result.computed[0].value == "125.00"
        and projection.profile_id == _PROFILE
    )


@pytest.mark.parametrize("refuse", [False, True])
def test_export_publication_uses_real_local_commit_and_receipt(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch, refuse: bool
) -> None:
    scope, events, operands = _Scope(refuse=refuse), _Events(), _Operands()
    target = tmp_path / "modelo.xlsx"
    original_write = LocalFileExportSink.write

    def write(sink: LocalFileExportSink, payload: bytes) -> LocalFileExportReceipt:
        assert scope.held
        return original_write(sink, payload)

    monkeypatch.setattr(LocalFileExportSink, "write", write)
    definition = _definition(_factory(_ports(authority_operation)), MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID)
    request = _request(
        definition.definition_id,
        ModeloSpreadsheetExportRequest(profile_id=_PROFILE, modelo="130", period=_PERIOD, output_path=str(target)),
    )
    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        if refuse:
            with pytest.raises(ProfileAccessRefusedError):
                asyncio.run(
                    definition.executor_factory.create().execute(
                        request, _context(request, authority_operation, scope, events, operands)
                    )
                )
            assert not target.exists() and not operands.rows and events.effects == [OperationEffect.NONE]
            return
        asyncio.run(
            definition.executor_factory.create().execute(
                request, _context(request, authority_operation, scope, events, operands)
            )
        )
    assert not scope.held and events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    execution_result = operands.rows[0]
    assert isinstance(execution_result, ModeloSpreadsheetExecutionResult)
    projection = execution_result.projection
    assert isinstance(projection, ModeloSpreadsheetExportOutcome)
    assert projection.result is not None
    assert (
        projection.result.sha256 == sha256_hex(target.read_bytes())
        and projection.result.byte_size == target.stat().st_size
    )
    registration = build_modelo_spreadsheet_registration(definition)
    identity = OperationIdentity(
        operation_id="a" * 64, definition_id=definition.definition_id, subject_ref=request.subject_ref
    )
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=now(),
        result_ref="f" * 64,
    )
    assert registration.result_projector is not None
    assert registration.result_projector(execution_result, receipt) == projection
    with pytest.raises(ValueError, match="terminal receipt"):
        registration.result_projector(execution_result, receipt.model_copy(update={"effect": OperationEffect.NONE}))


@pytest.mark.parametrize("outcome", ["acknowledged", "uncertain", "identity_only"])
def test_verify_requires_actual_write_acknowledgement_and_releases_commit_before_network(
    authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    scope, events, operands = _Scope(), _Events(), _Operands()
    monkeypatch.setattr(
        "cadrumo.application.modelo.modelo_spreadsheet_executor.resolve_active_capability",
        lambda _capability: SimpleNamespace(enabled=True),
    )

    def verify(
        request: ModeloSpreadsheetVerifyRequest,
        scenario: OperatorInputScenario,
        *,
        admit_provider: SpreadsheetProviderAdmission,
        before_mutation: SpreadsheetMutationHandoff,
    ) -> SpreadsheetVerifyAcknowledgement:
        assert scenario.scenario_label == "empty-defaults"
        admit_provider()
        assert not scope.held and not events.effects
        before_mutation()
        assert not scope.held and events.effects == [OperationEffect.UNKNOWN]
        if outcome == "uncertain":
            raise OSError("remote acknowledgement unavailable")
        facts = SpreadsheetVerifyFacts(
            spreadsheet_id="remote-workbook",
            spreadsheet_url="https://docs.google.com/spreadsheets/d/remote-workbook",
            verdict="inconclusive",
            aeat_oracle_present=False,
            computed_count=0,
            divergence_count=0,
            divergences=(),
        )
        return SpreadsheetVerifyAcknowledgement(facts=facts, remote_write_confirmed=outcome == "acknowledged")

    ports = replace(_ports(authority_operation), verify=verify)
    definition = _definition(_factory(ports), MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID)
    request = _request(
        definition.definition_id, ModeloSpreadsheetVerifyRequest(profile_id=_PROFILE, modelo="130", period=_PERIOD)
    )
    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        if outcome == "acknowledged":
            asyncio.run(
                definition.executor_factory.create().execute(
                    request, _context(request, authority_operation, scope, events, operands)
                )
            )
            assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED] and len(operands.rows) == 1
        else:
            with pytest.raises((OSError, ProfileAccessRefusedError)):
                asyncio.run(
                    definition.executor_factory.create().execute(
                        request, _context(request, authority_operation, scope, events, operands)
                    )
                )
            assert events.effects[-1] is OperationEffect.UNKNOWN and not operands.rows


def test_changed_scenario_refuses_before_provider_admission(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    scope, events, operands = _Scope(), _Events(), _Operands()
    monkeypatch.setattr(
        "cadrumo.application.modelo.modelo_spreadsheet_executor.resolve_active_capability",
        lambda _capability: SimpleNamespace(enabled=True),
    )
    source = tmp_path / "scenario.json"
    source.write_bytes(b"changed private scenario")
    definition = _definition(_factory(_ports(authority_operation)), MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID)
    request = _request(
        definition.definition_id,
        ModeloSpreadsheetVerifyRequest(
            profile_id=_PROFILE,
            modelo="130",
            period=_PERIOD,
            scenario_path=str(source),
            scenario_sha256=sha256_hex(b"original private scenario"),
        ),
    )
    with override_settings(cadrumo_active_profile=str(_PROFILE)), pytest.raises(ProfileAccessRefusedError) as error:
        asyncio.run(
            definition.executor_factory.create().execute(
                request, _context(request, authority_operation, scope, events, operands)
            )
        )
    assert error.value.reason is AccessDenialCode.OPERATION_DENIED
    assert scope.admissions == 0 and not operands.rows and events.effects == [OperationEffect.NONE]


def test_prefill_admission_uses_only_published_source_periods_and_requires_a_pin(
    authority_operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> None:
    definition = _definition(_unavailable, MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID)
    registration = build_modelo_spreadsheet_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    # The published Renta revision declares both settlement and evidence
    # relations; the quarterly 130 revision selected here previously had none.
    period = PublicPeriod(filing_year=2024, code="0A")
    payload = ModeloSpreadsheetExportRequest(
        profile_id=_PROFILE,
        modelo="100",
        period=period,
        output_path=str(tmp_path / "modelo.xlsx"),
        prefill_relations=True,
    )
    request = _request(definition.definition_id, payload)
    snapshot = authority_operation.snapshot("100", filing_year=period.filing_year, period=period.code)
    requirements = relation_source_requirements(
        snapshot.revision, filing_year=snapshot.filing_year, period=snapshot.period
    )
    assert requirements and any(row.filing_periods for row in requirements)
    expected = frozenset({period.to_period(), *(value for row in requirements for value in row.filing_periods)})
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=authority_operation,
    )
    resolved = resolve_operation_access(registry=registry, request=request, context=context)
    assert resolved.request.periods == expected and not resolved.policy.requires_all_periods
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(registry=registry, request=request, context=replace(context, authority_operation=None))
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


@pytest.mark.parametrize(
    ("model", "fields"),
    [
        (
            WithholdingObservation,
            {
                "perceptor_tax_id": "synthetic-id",
                "transaction_date": "2026-01-15",
                "clave": "A",
                "incapacity_cash_perception": "0",
                "incapacity_cash_withholding": "0",
                "incapacity_kind_value": "0",
                "incapacity_kind_ingreso_a_cuenta": "0",
                "incapacity_kind_repercutido": "0",
                "foral_retention_estatal": "0",
                "foral_retention_navarra": "0",
                "foral_retention_araba": "0",
                "foral_retention_gipuzkoa": "0",
                "foral_retention_bizkaia": "0",
                "base_retenciones": "0",
            },
        ),
        (
            Modelo720RowObservation,
            {
                "asset_class_code": "C",
                "country_code": "CH",
                "acquisition_date": "2020-01-15",
                "valuation_amount": "120000.00",
            },
        ),
        (
            AtributionMemberObservation,
            {
                "member_tax_id": "synthetic-id",
                "transaction_date": "2026-01-15",
                "share_percentage": "50.00",
                "base_imponible_assigned": "100.00",
                "clave": "A",
            },
        ),
        (Gasto193Observation, {"contributor_tax_id": "synthetic-id", "transaction_date": "2026-01-15"}),
        (Withholding296Observation, {"perceptor_tax_id": "synthetic-id", "transaction_date": "2026-01-15"}),
    ],
)
def test_every_canonical_observation_family_projects_without_losing_fields(
    model: type[BaseModel],
    fields: dict[str, str],
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with validating_governed_facts(authority_operation):
        canonical = model.model_validate_json(canonical_json_bytes({"source_id": "synthetic-source", **fields}))
    wire = project_modelo_spreadsheet_observation(cast(CanonicalSpreadsheetAssembledObservation, canonical))
    assert wire.model_dump(mode="json") == canonical.model_dump(mode="json")


def _refusal_receipt(
    definition: OperationDefinition, evidence: OperationRefusalEvidence, effect: OperationEffect
) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=definition.definition_id,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=1,
        condition=OperationTerminalCondition.REFUSED,
        effect=effect,
        settled_at=now(),
        refusal_ref=evidence.refusal_code,
        refusal_detail_ref=evidence.detail_ref,
    )


@pytest.mark.parametrize("during_publication", [False, True])
def test_output_refusal_retains_closed_facts_and_actual_effect(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    during_publication: bool,
) -> None:
    target = tmp_path / "output.xlsx"
    if during_publication:

        def failed_write(_sink: LocalFileExportSink, _payload: bytes) -> NoReturn:
            raise ModeloExportOutputPathError(
                "SECRET-OS-ERROR",
                translated_message="application.modelo.errors.export_output_path_invalid",
                context={
                    "output_path": "UNRELATED-PATH",
                    "reason": "SECRET-OS-ERROR",
                    "credential": "SECRET-CREDENTIAL",
                },
            )

        monkeypatch.setattr(LocalFileExportSink, "write", failed_write)
    else:
        target.write_bytes(b"original")
    scope, events, operands = _Scope(), _Events(), _Operands()
    definition = _definition(_factory(_ports(authority_operation)), MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID)
    request = _request(
        definition.definition_id,
        ModeloSpreadsheetExportRequest(profile_id=_PROFILE, modelo="130", period=_PERIOD, output_path=str(target)),
    )
    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        evidence = asyncio.run(
            definition.executor_factory.create().execute(
                request, _context(request, authority_operation, scope, events, operands)
            )
        )
    assert isinstance(evidence, OperationRefusalEvidence)
    effect = OperationEffect.UNKNOWN if during_publication else OperationEffect.NONE
    assert events.effects[-1] is effect
    retained = operands.rows[0]
    assert isinstance(retained, ModeloSpreadsheetExecutionResult)
    assert retained.effect == effect.value
    detail = retained.projection.refusal
    assert isinstance(detail, SpreadsheetOutputPathRefusal) and detail.output_path == str(target)
    assert detail.reason == ("publication_failed" if during_publication else "existing_file")
    assert "SECRET-" not in retained.model_dump_json() and "UNRELATED" not in retained.model_dump_json()
    if not during_publication:
        assert target.read_bytes() == b"original"
    registration = build_modelo_spreadsheet_registration(definition)
    assert registration.result_projector is not None
    receipt = _refusal_receipt(definition, evidence, effect)
    assert registration.result_projector(retained, receipt) == retained.projection
    wrong_identity = receipt.identity.model_copy(update={"subject_ref": profile_operation_subject(str(uuid4()))})
    for updates in (
        {"identity": wrong_identity},
        {"refusal_ref": "REFUSED_OUTBOUND_STORAGE_CONFLICT"},
        {"refusal_detail_ref": None},
        {"result_ref": "e" * 64},
        {"condition": OperationTerminalCondition.SUCCEEDED},
        {"effect": OperationEffect.UPDATED},
    ):
        with pytest.raises(ValueError):
            registration.result_projector(retained, receipt.model_copy(update=updates))


def test_canonical_ingress_retains_only_row_ownership_facts(authority_operation: PinnedAuthorityOperation) -> None:
    snapshot = authority_operation.snapshot("349", filing_year=2025, period="1T")
    first, second = collect_row_sets(snapshot.revision)
    row = SpreadsheetRowSet(
        grouping=first.grouping,
        cells=(SpreadsheetRowSetCell(binding=second.columns[0].binding, row_index=3, value="SECRET-CELL-VALUE"),),
    )

    def pull(request: ModeloSpreadsheetPullRequest, *, admit_provider: SpreadsheetProviderAdmission) -> NoReturn:
        del request
        admit_provider()
        assemble_row_sets_for_snapshot((row,), snapshot)
        pytest.fail("canonical ingress must refuse binding substitution")

    ports = replace(_ports(authority_operation), pull=pull)
    definition = _definition(_factory(ports), MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID)
    request = _request(
        definition.definition_id,
        ModeloSpreadsheetPullRequest(
            profile_id=_PROFILE,
            modelo="349",
            period=PublicPeriod(filing_year=2025, code="1T"),
            spreadsheet_id="synthetic-workbook",
            assemble_observations=True,
        ),
    )
    scope, events, operands = _Scope(), _Events(), _Operands()
    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        evidence = asyncio.run(
            definition.executor_factory.create().execute(
                request, _context(request, authority_operation, scope, events, operands)
            )
        )
    assert (
        isinstance(evidence, OperationRefusalEvidence)
        and evidence.refusal_code == MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE
    )
    assert events.effects == [OperationEffect.NONE]
    retained = operands.rows[0]
    assert isinstance(retained, ModeloSpreadsheetExecutionResult) and isinstance(
        retained.projection, ModeloSpreadsheetPullOutcome
    )
    detail = retained.projection.refusal
    assert isinstance(detail, SpreadsheetRowIngressRefusal)
    assert (
        detail.reason == "caller_binding_substitution"
        and detail.grouping == first.grouping
        and detail.declared_grouping == second.grouping
    )
    assert detail.binding_id == second.columns[0].binding and detail.row_index == 3
    assert "SECRET-CELL-VALUE" not in retained.model_dump_json()
    registration = build_modelo_spreadsheet_registration(definition)
    assert registration.result_projector is not None
    assert (
        registration.result_projector(retained, _refusal_receipt(definition, evidence, OperationEffect.NONE))
        == retained.projection
    )
    with pytest.raises(ValueError):
        registration.result_projector(retained, _refusal_receipt(definition, evidence, OperationEffect.UNKNOWN))


@pytest.mark.parametrize("canonical_key", [False, True])
def test_general_or_unrecognized_validation_content_is_not_retained(
    authority_operation: PinnedAuthorityOperation,
    canonical_key: bool,
) -> None:
    def pull(request: ModeloSpreadsheetPullRequest, *, admit_provider: SpreadsheetProviderAdmission) -> NoReturn:
        del request
        admit_provider()
        raise RegistryValidationError(
            "SECRET-EXCEPTION-TEXT",
            translated_message="application.calculations.row_set.errors.row_assembly_failed"
            if canonical_key
            else "other.validation",
            context={
                "validation_error_type": "row_set_ingress",
                "validation_error_detail": "SECRET-DETAIL",
                "grouping": "declared",
                "row_index": 1,
            },
        )

    definition = _definition(
        _factory(replace(_ports(authority_operation), pull=pull)), MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID
    )
    request = _request(
        definition.definition_id,
        ModeloSpreadsheetPullRequest(profile_id=_PROFILE, modelo="130", period=_PERIOD, spreadsheet_id="synthetic"),
    )
    scope, events, operands = _Scope(), _Events(), _Operands()
    with override_settings(cadrumo_active_profile=str(_PROFILE)), pytest.raises(RegistryValidationError):
        asyncio.run(
            definition.executor_factory.create().execute(
                request, _context(request, authority_operation, scope, events, operands)
            )
        )
    assert not operands.rows and events.effects == [OperationEffect.NONE]


def test_refusal_shape_cannot_carry_unreviewed_text_or_incomplete_coordinates() -> None:
    with pytest.raises(ValidationError):
        SpreadsheetRowIngressRefusal(reason="row_ownership_collision", grouping="declared", row_index=1)
    with pytest.raises(ValidationError):
        SpreadsheetRowIngressRefusal.model_validate(
            {"reason": "undeclared_grouping", "grouping": "declared", "row_index": 1, "value": "SECRET"}
        )
    with pytest.raises(ValidationError):
        SpreadsheetOutputPathRefusal.model_validate({"output_path": "output.xlsx", "reason": "SECRET-OS-TEXT"})


def test_snapshot_refusal_is_bound_to_exact_profile_purpose_and_workbook(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    snapshot = authority_operation.snapshot("130", filing_year=2026, period="1T")
    detail = SpreadsheetSnapshotMismatchRefusal(
        spreadsheet_id="synthetic",
        metadata_match="stale",
        workbook_modelo="130",
        snapshot_modelo=snapshot.modelo.id,
        workbook_revision="old",
        snapshot_revision=snapshot.revision.id,
        workbook_engine_version="old",
        expected_engine_version="current",
        workbook_registry_sha="b" * 16,
        snapshot_registry_sha="c" * 16,
    )

    def calculate(
        request: ModeloSpreadsheetCalculateRequest, *, admit_provider: SpreadsheetProviderAdmission
    ) -> SpreadsheetSnapshotMismatchRefusal:
        del request
        admit_provider()
        return detail

    definition = _definition(
        _factory(replace(_ports(authority_operation), calculate=calculate)),
        MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID,
    )
    request = _request(
        definition.definition_id,
        ModeloSpreadsheetCalculateRequest(
            profile_id=_PROFILE, modelo="130", period=_PERIOD, spreadsheet_id="synthetic"
        ),
    )
    scope, events, operands = _Scope(), _Events(), _Operands()
    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        evidence = asyncio.run(
            definition.executor_factory.create().execute(
                request, _context(request, authority_operation, scope, events, operands)
            )
        )
    assert (
        isinstance(evidence, OperationRefusalEvidence) and evidence.refusal_code == "REFUSED_OUTBOUND_STORAGE_CONFLICT"
    )
    retained = operands.rows[0]
    assert isinstance(retained, ModeloSpreadsheetExecutionResult) and isinstance(
        retained.projection, ModeloSpreadsheetCalculateOutcome
    )
    registration = build_modelo_spreadsheet_registration(definition)
    assert registration.result_projector is not None
    receipt = _refusal_receipt(definition, evidence, OperationEffect.NONE)
    assert registration.result_projector(retained, receipt) == retained.projection
    wrong = receipt.identity.model_copy(update={"definition_id": MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID})
    with pytest.raises(ValueError):
        registration.result_projector(retained, receipt.model_copy(update={"identity": wrong}))
    operands.rows.clear()
    changed = request.payload.model_copy(update={"spreadsheet_id": "other"})
    changed_request = _request(definition.definition_id, changed)
    with override_settings(cadrumo_active_profile=str(_PROFILE)), pytest.raises(ProfileAccessRefusedError):
        asyncio.run(
            definition.executor_factory.create().execute(
                changed_request, _context(changed_request, authority_operation, scope, events, operands)
            )
        )
    assert not operands.rows


def test_declared_refusal_result_keeps_exact_destination_and_current_consent(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    definition = _definition(_unavailable, MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID)
    registration = build_modelo_spreadsheet_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    payload = ModeloSpreadsheetPullRequest(
        profile_id=POLICY_PROFILE_ID, modelo="130", period=_PERIOD, spreadsheet_id="synthetic"
    )
    request = OperationRequest[BaseModel](
        definition_id=definition.definition_id,
        subject_ref=profile_operation_subject(str(POLICY_PROFILE_ID)),
        payload=payload,
    )
    context = OperationAccessContext(
        profile_id=POLICY_PROFILE_ID,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=authority_operation,
    )
    resolved = resolve_operation_access(registry=registry, request=request, context=context)
    assert isinstance(policy_decision(resolved, registry, disclosures=resolved.policy.disclosures), AccessAllowed)
    empty_permissions = frozenset[DisclosurePermission]()
    for permissions in (
        empty_permissions,
        frozenset(row.model_copy(update={"destination_id": uuid4()}) for row in resolved.policy.disclosures),
    ):
        denied = policy_decision(resolved, registry, disclosures=permissions)
        assert isinstance(denied, AccessDenied) and denied.code is AccessDenialCode.DISCLOSURE_DENIED
    observed = resolve_operation_access(
        registry=registry, request=request, context=replace(context, action=AccessAction.OBSERVE)
    )
    assert {row.category for row in observed.policy.disclosures} == {DisclosureCategory.OPERATION_METADATA}

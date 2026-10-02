"""Registered workers for the four existing modelo spreadsheet services."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.capabilities import ServiceCapability
from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.relations import relation_source_requirements
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.refusal_evidence import OperationExecutorResult, OperationRefusalEvidence
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..storage.calc_sheets.workbook_export import ModeloWorkbookExport, export_modelo_workbook
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from ..user_profile.capabilities import resolve_active_capability
from .export_sink import LocalFileExportSink, ModeloExportOutputPathError
from .modelo_spreadsheet_operation_contracts import (
    MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE,
    MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID,
    ModeloSpreadsheetCalculateOutcome,
    ModeloSpreadsheetCalculateProjection,
    ModeloSpreadsheetCalculateRequest,
    ModeloSpreadsheetExecutionResult,
    ModeloSpreadsheetExportOutcome,
    ModeloSpreadsheetExportProjection,
    ModeloSpreadsheetExportRequest,
    ModeloSpreadsheetOperationPortsFactory,
    ModeloSpreadsheetOutcome,
    ModeloSpreadsheetProjection,
    ModeloSpreadsheetPullOutcome,
    ModeloSpreadsheetPullProjection,
    ModeloSpreadsheetPullRequest,
    ModeloSpreadsheetRequest,
    ModeloSpreadsheetVerifyOutcome,
    ModeloSpreadsheetVerifyProjection,
    ModeloSpreadsheetVerifyRequest,
    SpreadsheetOutputPathRefusal,
    SpreadsheetRefusal,
    SpreadsheetRowIngressRefusal,
    SpreadsheetSnapshotMismatchRefusal,
)
from .modelo_spreadsheet_operation_scenario import decode_modelo_spreadsheet_scenario

_CONTRACTS: dict[
    str, tuple[type[ModeloSpreadsheetRequest], type[ModeloSpreadsheetProjection], type[ModeloSpreadsheetOutcome]]
] = {
    MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID: (
        ModeloSpreadsheetExportRequest,
        ModeloSpreadsheetExportProjection,
        ModeloSpreadsheetExportOutcome,
    ),
    MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID: (
        ModeloSpreadsheetPullRequest,
        ModeloSpreadsheetPullProjection,
        ModeloSpreadsheetPullOutcome,
    ),
    MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID: (
        ModeloSpreadsheetCalculateRequest,
        ModeloSpreadsheetCalculateProjection,
        ModeloSpreadsheetCalculateOutcome,
    ),
    MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID: (
        ModeloSpreadsheetVerifyRequest,
        ModeloSpreadsheetVerifyProjection,
        ModeloSpreadsheetVerifyOutcome,
    ),
}
MAX_MODELO_SPREADSHEET_SCENARIO_BYTES = PROJECTION_DOCUMENT_MAX_BYTES


def _refusal_code(detail: SpreadsheetRefusal) -> str:
    if isinstance(detail, SpreadsheetOutputPathRefusal):
        return "REFUSED_MODELO_EXPORT_OUTPUT_PATH"
    if isinstance(detail, SpreadsheetRowIngressRefusal):
        return MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE
    return "REFUSED_OUTBOUND_STORAGE_CONFLICT"


def _declared_refusal_codes(definition_id: str) -> frozenset[str]:
    if definition_id == MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID:
        return frozenset({"REFUSED_MODELO_EXPORT_OUTPUT_PATH"})
    if definition_id == MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID:
        return frozenset({MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE, "REFUSED_OUTBOUND_STORAGE_CONFLICT"})
    if definition_id == MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID:
        return frozenset({"REFUSED_OUTBOUND_STORAGE_CONFLICT"})
    return frozenset[str]()


def _row_ingress_refusal(error: RegistryValidationError) -> SpreadsheetRowIngressRefusal | None:
    """Select only canonical ingress facts; never retain general validation text."""
    facts = error.context
    if (
        facts is None
        or error.translated_message != "application.calculations.row_set.errors.row_assembly_failed"
        or facts.get("validation_error_type") != "row_set_ingress"
    ):
        return None
    try:
        return SpreadsheetRowIngressRefusal.model_validate(
            {
                "reason": facts.get("validation_error_detail"),
                "grouping": facts.get("grouping"),
                "row_index": facts.get("row_index"),
                "binding_id": facts.get("binding_id"),
                "declared_grouping": facts.get("declared_grouping"),
                "first_row_set_index": facts.get("first_row_set_index"),
                "second_row_set_index": facts.get("second_row_set_index"),
            },
            strict=True,
        )
    except ValidationError:
        return None


def _output_path_refusal(
    error: ModeloExportOutputPathError, payload: ModeloSpreadsheetExportRequest
) -> SpreadsheetOutputPathRefusal:
    reasons = {
        "path is empty": "empty",
        "path is an existing directory": "existing_directory",
        "path is an existing file": "existing_file",
        "parent directory does not exist": "missing_parent",
        "parent path is not a directory": "parent_not_directory",
    }
    reason = None if error.context is None else error.context.get("reason")
    return SpreadsheetOutputPathRefusal.model_validate(
        {
            "output_path": payload.output_path,
            "reason": reasons.get(reason, "publication_failed") if isinstance(reason, str) else "publication_failed",
        },
        strict=True,
    )


def _require_profile(
    request: OperationRequest[BaseModel], context: OperationExecutorContext
) -> ModeloSpreadsheetRequest:
    payload = request.payload
    pair = _CONTRACTS.get(request.definition_id)
    if pair is None or type(payload) is not pair[0] or not isinstance(payload, ModeloSpreadsheetRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    subject = profile_operation_subject(str(payload.profile_id))
    if (
        request.subject_ref != subject
        or context.identity.definition_id != request.definition_id
        or context.identity.subject_ref != subject
        or require_active_bucket_id() != str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return payload


class ModeloSpreadsheetExecutor:
    """Retain worker custody and delegate algorithms through canonical ports."""

    def __init__(
        self, factory: ModeloSpreadsheetOperationPortsFactory, *, source_reader: Callable[[Path], bytes]
    ) -> None:
        """Bind exact-profile canonical ports and the secure source reader."""
        self._factory = factory
        self._source_reader = source_reader

    async def execute(
        self, request: OperationRequest[BaseModel], context: OperationExecutorContext
    ) -> OperationExecutorResult:
        """Keep provider I/O outside COMMIT and fence actual local publication."""
        payload = _require_profile(request, context)
        await context.events.phase(request.definition_id)
        operation = context.authority_operation
        ports = self._factory(profile_id=payload.profile_id, operation=operation)
        if ports.profile_id != payload.profile_id or ports.operation is not operation:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        period = payload.period.to_period()
        snapshot = operation.snapshot(payload.modelo, filing_year=period.filing_year, period=period.registry_token)
        if (
            snapshot.modelo.id != payload.modelo
            or snapshot.filing_year != period.filing_year
            or snapshot.period != period.registry_token
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        coordinate = ModeloSpreadsheetProjection(
            profile_id=payload.profile_id,
            modelo=snapshot.modelo.id,
            revision=snapshot.revision.id,
            period=payload.period,
        ).model_dump(mode="python")
        loop = asyncio.get_running_loop()
        remote_dispatched = False
        local_publication_started = False

        async def authorize_provider() -> None:
            # Construction can discover ADC or refresh credentials. Admission
            # ends before entering those canonical provider implementations.
            async with context.cancellation.irreversible_section():
                _require_profile(request, context)

        async def authorize_mutation() -> None:
            nonlocal remote_dispatched
            if not isinstance(payload, ModeloSpreadsheetVerifyRequest):
                raise ValueError("spreadsheet read cannot request mutation authority")
            async with context.cancellation.irreversible_section():
                _require_profile(request, context)
                remote_dispatched = True
                await context.events.effect(OperationEffect.UNKNOWN)

        def admit_provider() -> None:
            asyncio.run_coroutine_threadsafe(authorize_provider(), loop).result()

        def before_mutation() -> None:
            asyncio.run_coroutine_threadsafe(authorize_mutation(), loop).result()

        def current_effect() -> OperationEffect:
            return OperationEffect.UNKNOWN if remote_dispatched or local_publication_started else OperationEffect.NONE

        async def refuse(detail: SpreadsheetRefusal) -> OperationRefusalEvidence:
            effect = current_effect()
            refusal_effect: Literal["none", "unknown"] = "unknown" if effect is OperationEffect.UNKNOWN else "none"
            outcome = _CONTRACTS[request.definition_id][2].model_validate(
                {
                    **coordinate,
                    "outcome": "refused",
                    "refusal": detail.model_dump(mode="python"),
                },
                strict=True,
            )
            async with context.cancellation.irreversible_section():
                _require_profile(request, context)
                await context.events.effect(effect)
                retained = ModeloSpreadsheetExecutionResult.model_validate(
                    {"projection": outcome.model_dump(mode="python"), "effect": refusal_effect}, strict=True
                )
                detail_ref = await context.operands.put(retained, written_at=now())
            return OperationRefusalEvidence(refusal_code=_refusal_code(detail), detail_ref=detail_ref)

        async def run() -> OperationExecutorResult:
            nonlocal local_publication_started
            try:
                if isinstance(payload, ModeloSpreadsheetExportRequest):
                    export_payload: ModeloSpreadsheetExportRequest = payload
                    sink = LocalFileExportSink(
                        path=Path(payload.output_path), replace_existing=payload.replace_existing
                    )
                    sink.require_writable()

                    def render() -> ModeloWorkbookExport:
                        with validating_governed_facts(operation):
                            return export_modelo_workbook(
                                modelo=export_payload.modelo,
                                period=period,
                                materializer=ports.materialize,
                                prefill_relations=export_payload.prefill_relations,
                                snapshot_resolver=lambda _modelo, _period: snapshot,
                                plan_builder=ports.plan_builder,
                            )

                    workbook = await asyncio.to_thread(render)
                    async with context.cancellation.irreversible_section():
                        _require_profile(request, context)
                        # Repeat the canonical path precondition before claiming
                        # an actual attempt; an occupied path remains NONE.
                        sink.require_writable()
                        local_publication_started = True
                        await context.events.effect(OperationEffect.UNKNOWN)
                        receipt = await asyncio.to_thread(sink.write, workbook.payload)
                        if (
                            receipt.path != sink.path
                            or receipt.sha256 != workbook.sha256
                            or receipt.byte_size != workbook.byte_size
                        ):
                            raise ValueError("spreadsheet publication receipt contradicts its workbook")
                        await context.events.effect(OperationEffect.UPDATED)
                    projection = ModeloSpreadsheetExportProjection(
                        **coordinate,
                        output_path=str(receipt.path),
                        byte_size=receipt.byte_size,
                        sha256=receipt.sha256,
                        tab_names=workbook.tab_names,
                        casilla_count=workbook.casilla_count,
                        prefill_relations=payload.prefill_relations,
                    )
                elif isinstance(payload, ModeloSpreadsheetPullRequest):
                    facts = await asyncio.to_thread(ports.pull, payload, admit_provider=admit_provider)
                    if isinstance(facts, SpreadsheetSnapshotMismatchRefusal):
                        if facts.spreadsheet_id != payload.spreadsheet_id:
                            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                        return await refuse(facts)
                    if facts.spreadsheet_id != payload.spreadsheet_id:
                        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                    if not payload.assemble_observations and (
                        facts.assembled_groupings or facts.assembled_observation_count
                    ):
                        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                    projection = ModeloSpreadsheetPullProjection(**coordinate, **facts.model_dump(mode="python"))
                    await context.events.effect(OperationEffect.NONE)
                elif isinstance(payload, ModeloSpreadsheetCalculateRequest):
                    facts = await asyncio.to_thread(ports.calculate, payload, admit_provider=admit_provider)
                    if isinstance(facts, SpreadsheetSnapshotMismatchRefusal):
                        if facts.spreadsheet_id != payload.spreadsheet_id:
                            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                        return await refuse(facts)
                    if facts.spreadsheet_id != payload.spreadsheet_id:
                        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                    projection = ModeloSpreadsheetCalculateProjection(**coordinate, **facts.model_dump(mode="python"))
                    await context.events.effect(OperationEffect.NONE)
                elif isinstance(payload, ModeloSpreadsheetVerifyRequest):
                    if not resolve_active_capability(ServiceCapability.GOOGLE_EXPORT).enabled:
                        raise ProfileAccessRefusedError(AccessDenialCode.PROVIDER_REQUIRED)
                    source = None
                    source_path = None
                    if payload.scenario_path is not None:
                        source_path = Path(payload.scenario_path)
                        try:
                            source = await asyncio.to_thread(self._source_reader, source_path)
                        except OSError as error:
                            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from error
                        if (
                            len(source) > MAX_MODELO_SPREADSHEET_SCENARIO_BYTES
                            or sha256_hex(source) != payload.scenario_sha256
                        ):
                            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                    scenario = decode_modelo_spreadsheet_scenario(source, source_path=source_path)
                    acknowledgement = await asyncio.to_thread(
                        ports.verify, payload, scenario, admit_provider=admit_provider, before_mutation=before_mutation
                    )
                    if not remote_dispatched or not acknowledgement.remote_write_confirmed:
                        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                    projection = ModeloSpreadsheetVerifyProjection(
                        **coordinate, **acknowledgement.facts.model_dump(mode="python")
                    )
                    await context.events.effect(OperationEffect.UPDATED)
                else:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            except ModeloExportOutputPathError as error:
                if not isinstance(payload, ModeloSpreadsheetExportRequest):
                    raise
                return await refuse(_output_path_refusal(error, payload))
            except RegistryValidationError as error:
                detail = _row_ingress_refusal(error)
                if (
                    not isinstance(payload, ModeloSpreadsheetPullRequest)
                    or not payload.assemble_observations
                    or detail is None
                ):
                    await context.events.effect(current_effect())
                    raise
                return await refuse(detail)
            except BaseException:
                await context.events.effect(current_effect())
                raise
            if len(canonical_json_bytes(projection.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            effect = (
                "none"
                if isinstance(payload, (ModeloSpreadsheetPullRequest, ModeloSpreadsheetCalculateRequest))
                else "updated"
            )
            outcome = _CONTRACTS[request.definition_id][2].model_validate(
                {
                    **coordinate,
                    "outcome": "succeeded",
                    "result": projection.model_dump(mode="python"),
                },
                strict=True,
            )
            retained = ModeloSpreadsheetExecutionResult.model_validate(
                {"projection": outcome.model_dump(mode="python"), "effect": effect}, strict=True
            )
            return await context.operands.put(retained, written_at=now())

        return await await_cancellation_complete(run(), task_name=request.definition_id)


def build_modelo_spreadsheet_definitions(
    factory: ModeloSpreadsheetOperationPortsFactory, *, source_reader: Callable[[Path], bytes] = Path.read_bytes
) -> tuple[OperationDefinition, ...]:
    """Declare four secure-reference operations without constructing providers."""
    definitions: list[OperationDefinition] = []
    for definition_id, (request_type, _result_type, _outcome_type) in _CONTRACTS.items():
        mutates = definition_id in {
            MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID,
            MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID,
        }
        definitions.append(
            OperationDefinition(
                definition_id=definition_id,
                request_type=request_type,
                result_type=ModeloSpreadsheetExecutionResult,
                executor_factory=OperationExecutorFactory(
                    request_type=request_type,
                    executor_type=ModeloSpreadsheetExecutor,
                    build=lambda: ModeloSpreadsheetExecutor(factory, source_reader=source_reader),
                ),
                phase_codes=(definition_id,),
                interaction_kinds=frozenset(),
                capabilities=OperationCapabilities(
                    durability=OperationDurability.RECORDED,
                    cancellation=OperationCancellation.UNSUPPORTED,
                    deadline=OperationDeadline.ABSENT,
                    replay=OperationReplayPolicy.NONE,
                    baseline=OperationBaselinePolicy.REQUEST_BOUND,
                    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
                    sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
                    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
                    owned_resources=frozenset(),
                    permitted_effects=frozenset(
                        {OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED}
                    )
                    if mutates
                    else frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
                    close_policy=OperationClosePolicy.DETACH_ALLOWED,
                ),
                reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
                refusal_detail_codes=_declared_refusal_codes(definition_id),
                permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
            )
        )
    return tuple(sorted(definitions, key=lambda row: row.definition_id))


def resolve_modelo_spreadsheet_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve filing and relation-source periods from the retained published pin."""
    pair = _CONTRACTS.get(request.definition_id)
    payload = request.payload
    if pair is None or type(payload) is not pair[0] or not isinstance(payload, ModeloSpreadsheetRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    operation = context.authority_operation
    if operation is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    period = payload.period.to_period()
    snapshot = operation.snapshot(payload.modelo, filing_year=period.filing_year, period=period.registry_token)
    periods = {period}
    if isinstance(payload, ModeloSpreadsheetExportRequest) and payload.prefill_relations:
        for requirement in relation_source_requirements(
            snapshot.revision, filing_year=snapshot.filing_year, period=snapshot.period
        ):
            # Canonical filing-period identities are published with each
            # requirement; use the registry's temporal selection unchanged.
            source_periods = requirement.filing_periods or tuple(
                Period.from_year_and_code(requirement.filing_year, code) for code in requirement.periods
            )
            periods.update(source_periods)
    resolved = resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=frozenset(periods))
    provider = Availability.NOT_REQUIRED
    if isinstance(payload, ModeloSpreadsheetVerifyRequest):
        provider = (
            Availability.AVAILABLE
            if resolve_active_capability(ServiceCapability.GOOGLE_EXPORT).enabled
            else Availability.UNAVAILABLE
        )
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}, "provider": provider}
    )
    return replace(resolved, policy=policy)


def build_modelo_spreadsheet_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Compile closed request/result schemas and bind a receipt-checked projection."""
    pair = _CONTRACTS.get(definition.definition_id)
    if (
        pair is None
        or definition.request_type is not pair[0]
        or definition.result_type is not ModeloSpreadsheetExecutionResult
    ):
        raise ValueError("invalid spreadsheet definition contract")

    def project(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
        if type(result) is not ModeloSpreadsheetExecutionResult or not isinstance(
            result, ModeloSpreadsheetExecutionResult
        ):
            raise ValueError("invalid spreadsheet operation result")
        projection = result.projection
        if type(projection) is not pair[2]:
            raise ValueError("spreadsheet result has the wrong public projection")
        expected_effect = (
            OperationEffect.NONE
            if definition.definition_id
            in {MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID, MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID}
            else OperationEffect.UPDATED
        )
        if (
            receipt.identity.definition_id != definition.definition_id
            or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
            or result.effect != receipt.effect.value
            or receipt.failure_error_code is not None
            or receipt.diagnostic_ref is not None
        ):
            raise ValueError("spreadsheet result contradicts its terminal receipt")
        if projection.outcome == "succeeded":
            if (
                receipt.condition is not OperationTerminalCondition.SUCCEEDED
                or receipt.effect is not expected_effect
                or receipt.result_ref is None
                or receipt.refusal_ref is not None
                or receipt.refusal_detail_ref is not None
            ):
                raise ValueError("spreadsheet success has an incompatible receipt")
        elif (
            projection.refusal is None
            or receipt.condition is not OperationTerminalCondition.REFUSED
            or receipt.refusal_ref not in definition.refusal_detail_codes
            or receipt.refusal_ref != _refusal_code(projection.refusal)
            or receipt.refusal_detail_ref is None
            or receipt.result_ref is not None
            or receipt.effect not in {OperationEffect.NONE, OperationEffect.UNKNOWN}
            or (
                receipt.effect is OperationEffect.UNKNOWN
                and not isinstance(projection.refusal, SpreadsheetOutputPathRefusal)
            )
        ):
            raise ValueError("spreadsheet refusal has an incompatible receipt")
        projection = pair[2].model_validate(projection.model_dump(mode="python"), strict=True)
        if len(canonical_json_bytes(projection.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
            raise ValueError("spreadsheet result exceeds its projection limit")
        return projection

    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=pair[0]
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=pair[2]
        ),
        result_projector=project,
        access_resolver=resolve_modelo_spreadsheet_access,
    )


__all__ = [
    "MAX_MODELO_SPREADSHEET_SCENARIO_BYTES",
    "ModeloSpreadsheetExecutor",
    "build_modelo_spreadsheet_definitions",
    "build_modelo_spreadsheet_registration",
    "resolve_modelo_spreadsheet_access",
]

"""Declaration preparation resolves alike on every frontend, and an agent's records carry its session label.

The production registry, its real access resolvers and the real executors run
over a stored profile. Creating, calculating, verifying and renaming a
declaration resolve to one access whichever frontend submits them, including a
calculation that supplies its own inputs or the Modelo 303 filing facts. What
an MCP session records carries its own session label: every modelo operation
whose request types who acted is run under a session host that answers MCP and
under one that answers the command line, and the stored actor is read back.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.review_package_recipient_encryption import (
    build_recipient_encryption_capability,
)
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.application.bucket_event_repository import bucket_event_history_repository
from cadrumo.application.modelo.calculation_request_fields import (
    ModeloCalculationInputFieldsV1,
    ModeloCalculationOverride,
)
from cadrumo.application.modelo.m303_attestation_operation import ModeloWorkM303AttestationPublicResultV2
from cadrumo.application.modelo.recipient_encryption import RecipientEncryptedPackage
from cadrumo.application.modelo.review_package_exchange_operation import (
    ModeloReviewPackageEncryptFeedbackRequest,
)
from cadrumo.application.modelo.review_package_feedback import decrypt_feedback_package_from_originator_envelope
from cadrumo.application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateCallerContext,
    ModeloWorkCalculateOrdinaryM303EvidenceRequestV2,
    ModeloWorkCalculateRequest,
)
from cadrumo.application.modelo.work_change_contracts import ModeloWorkRenameRequest
from cadrumo.application.modelo.work_create_operation import ModeloWorkCreateRequest
from cadrumo.application.modelo.work_verification_contracts import (
    ModeloWorkVerifyPublicResultV2,
    ModeloWorkVerifyRequest,
)
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.execution_actor import OperationExecutionCaller, OperationExecutionCallerReader
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import AccessAction, Availability, SessionKind
from cadrumo.core.operations import OperationTerminalCondition, profile_operation_subject
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.tests.modelo_operation_test_support import seeded_modelo_calculation_revision

from .conformance_family_contract import ConformanceFamily
from .conformance_maritime_preview_support import MARITIME_QUICKFILE_MATERIAL_CONFORMANCE_FAMILY
from .conformance_review_package_exchange_support import _profile_recipient_keypair
from .registered_executor_case_support import (
    _CloseWitness,
    _ExecutionDriver,
    _model_runtime_for,
    _resolve_result_projection,
    _runtime,
    _seeded_conformance_submission,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CLI = OperationFrontendProjection.CLI
_TUI = OperationFrontendProjection.TUI
_MCP = OperationFrontendProjection.MCP
_SUPPLIED_ACTOR = "typed by the caller"
_SESSION_CLIENT = UUID("5aa00000-0000-4000-8000-0000000000dd")
_M303_FILING_FACTS = ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(joint_return_elected=False)


def _context(
    registry: OperationRegistry,
    request: OperationRequest[BaseModel],
    *,
    profile_id: UUID,
    frontend: OperationFrontendProjection,
    operation: PinnedAuthorityOperation,
    action: AccessAction = AccessAction.SUBMIT,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=frontend,
        contract=registry.lookup_public_contract(request.definition_id),
        published_authority=Availability.AVAILABLE,
        authority_operation=operation,
    )


def _seeded_unit(profile_id: UUID, *, operation: PinnedAuthorityOperation) -> tuple[WorkUnit, str]:
    """One stored work unit and the id of its real calculation head."""
    revision_id = seeded_modelo_calculation_revision(profile_id, operation=operation)
    revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
    assert revision is not None
    unit = WorkUnitCatalogueRepository().load().get(revision.work_unit_id)
    assert unit is not None
    return unit, revision_id


def _calculation(unit: WorkUnit, payload: ModeloWorkCalculateRequest) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id="modelo.work.calculate", subject_ref=unit.work_unit_id, payload=payload
    )


def _preparation_requests(
    unit: WorkUnit, revision_id: str, profile_id: UUID
) -> tuple[OperationRequest[BaseModel], ...]:
    """One request of each preparation operation, and each calculation that states its own facts."""
    return (
        _calculation(unit, ModeloWorkCalculateRequest(work_unit_id=unit.work_unit_id, actor=_SUPPLIED_ACTOR)),
        _calculation(
            unit,
            ModeloWorkCalculateRequest(
                work_unit_id=unit.work_unit_id,
                actor=_SUPPLIED_ACTOR,
                caller_context=ModeloWorkCalculateCallerContext.EXPLICIT,
                inputs=ModeloCalculationInputFieldsV1(
                    casilla_overrides=(ModeloCalculationOverride(key="01", value="100.00"),)
                ),
            ),
        ),
        _calculation(
            unit,
            ModeloWorkCalculateRequest(
                work_unit_id=unit.work_unit_id,
                actor=_SUPPLIED_ACTOR,
                ordinary_m303_filing_evidence=_M303_FILING_FACTS,
            ),
        ),
        OperationRequest[BaseModel](
            definition_id="modelo.work.verify",
            subject_ref=unit.work_unit_id,
            payload=ModeloWorkVerifyRequest(calculation_revision_id=revision_id, actor=_SUPPLIED_ACTOR),
        ),
        OperationRequest[BaseModel](
            definition_id="modelo.work.rename",
            subject_ref=unit.work_unit_id,
            payload=ModeloWorkRenameRequest(
                work_unit_id=unit.work_unit_id,
                new_name="Renamed by the test",
                observed_name=unit.name,
                observed_updated_at=unit.updated_at,
                actor=_SUPPLIED_ACTOR,
            ),
        ),
        OperationRequest[BaseModel](
            definition_id="modelo.work.create",
            subject_ref=profile_operation_subject(str(profile_id)),
            payload=ModeloWorkCreateRequest(
                profile_id=profile_id,
                modelo=str(unit.modelo),
                period=PublicPeriod.from_period(unit.period),
                actor=_SUPPLIED_ACTOR,
                allow_not_applicable=True,
            ),
        ),
    )


@pytest.mark.parametrize("action", [AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT])
def test_the_real_resolvers_give_every_frontend_the_same_access_to_each_preparation_request(
    tmp_path: Path, operation: PinnedAuthorityOperation, action: AccessAction
) -> None:
    """A request resolves for MCP and the terminal interface exactly as it resolves for the command line."""
    with _runtime(tmp_path / "admission", cleanup=_CloseWitness()) as (_driver, registry, profile_id):
        unit, revision_id = _seeded_unit(profile_id, operation=operation)

        for request in _preparation_requests(unit, revision_id, profile_id):
            context = _context(
                registry, request, profile_id=profile_id, frontend=_CLI, operation=operation, action=action
            )
            on_cli = resolve_operation_access(registry=registry, request=request, context=context)
            assert on_cli.request.periods == frozenset({unit.period}), request.definition_id
            assert AccessAction.COMMIT in on_cli.policy.actions, request.definition_id
            assert not on_cli.policy.requires_human, request.definition_id
            for frontend in (_TUI, _MCP):
                access = resolve_operation_access(
                    registry=registry, request=request, context=replace(context, frontend=frontend)
                )
                assert access.policy == on_cli.policy, (request.definition_id, frontend)
                assert access.request == on_cli.request.model_copy(update={"frontend": frontend}), (
                    request.definition_id,
                    frontend,
                )


def _session_host(frontend: OperationFrontendProjection) -> OperationExecutionCallerReader:
    """What a session host answers for an invocation it admitted on ``frontend``."""

    def read(identity: OperationIdentity) -> OperationExecutionCaller:
        assert identity.definition_id == "modelo.work.verify"
        return OperationExecutionCaller(frontend=frontend, session_kind=SessionKind.HUMAN, client_id=_SESSION_CLIENT)

    return read


@pytest.mark.parametrize(
    ("frontend", "recorded_actor"),
    [
        (_MCP, f"agent:mcp.human.{_SESSION_CLIENT}"),
        (_CLI, _SUPPLIED_ACTOR),
        (_TUI, _SUPPLIED_ACTOR),
    ],
    ids=["mcp", "cli", "tui"],
)
def test_verification_stores_the_session_label_for_an_agent_and_the_supplied_label_for_a_person(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded_actor: str,
) -> None:
    """The real executor never stores what an MCP caller typed as the actor of its report."""
    with _runtime(tmp_path / "actor", cleanup=_CloseWitness(), execution_caller_reader=_session_host(frontend)) as (
        driver,
        registry,
        profile_id,
    ):
        unit, revision_id = _seeded_unit(profile_id, operation=operation)
        payload = ModeloWorkVerifyRequest(calculation_revision_id=revision_id, actor=_SUPPLIED_ACTOR)

        submitted, observed = asyncio.run(
            driver.run(definition_id="modelo.work.verify", subject_ref=unit.work_unit_id, payload=payload)
        )

        terminal = observed.projection
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        contract = registry.lookup_public_contract("modelo.work.verify")
        assert contract.result_schema is not None
        resolved = asyncio.run(
            driver.services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=submitted.receipt.operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                ModeloWorkVerifyPublicResultV2,
            )
        )
        assert isinstance(resolved, OperationResultProjectionSuccessV1)
        report = VerificationReportCatalogueRepository().load().get(resolved.projection.verification_report_id)
        assert report is not None
        assert report.verified_by == recorded_actor


def _work_session_host(frontend: OperationFrontendProjection) -> OperationExecutionCallerReader:
    """A session host answering for the three preparation steps that record an actor."""

    def read(identity: OperationIdentity) -> OperationExecutionCaller:
        assert identity.definition_id in {"modelo.work.calculate", "modelo.work.create", "modelo.work.rename"}
        return OperationExecutionCaller(frontend=frontend, session_kind=SessionKind.HUMAN, client_id=_SESSION_CLIENT)

    return read


@pytest.mark.parametrize(
    ("frontend", "recorded_actor"),
    [
        (_MCP, f"agent:mcp.human.{_SESSION_CLIENT}"),
        (_CLI, _SUPPLIED_ACTOR),
        (_TUI, _SUPPLIED_ACTOR),
    ],
    ids=["mcp", "cli", "tui"],
)
def test_creation_calculation_and_rename_record_the_session_label_for_an_agent_and_the_supplied_one_otherwise(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded_actor: str,
) -> None:
    """Every event the three real executors append names the label of the session that admitted them."""
    with _runtime(
        tmp_path / "preparation", cleanup=_CloseWitness(), execution_caller_reader=_work_session_host(frontend)
    ) as (driver, _registry_in_use, profile_id):
        unit, _revision_id = _seeded_unit(profile_id, operation=operation)
        other_period = Period.from_year_and_code(unit.period.filing_year, "2T")
        steps: tuple[tuple[str, str, BaseModel], ...] = (
            (
                "modelo.work.rename",
                unit.work_unit_id,
                ModeloWorkRenameRequest(
                    work_unit_id=unit.work_unit_id,
                    new_name="Renamed by the test",
                    observed_name=unit.name,
                    observed_updated_at=unit.updated_at,
                    actor=_SUPPLIED_ACTOR,
                ),
            ),
            (
                "modelo.work.calculate",
                unit.work_unit_id,
                ModeloWorkCalculateRequest(work_unit_id=unit.work_unit_id, actor=_SUPPLIED_ACTOR),
            ),
            (
                "modelo.work.create",
                profile_operation_subject(str(profile_id)),
                ModeloWorkCreateRequest(
                    profile_id=profile_id,
                    modelo=str(unit.modelo),
                    period=PublicPeriod.from_period(other_period),
                    actor=_SUPPLIED_ACTOR,
                    allow_not_applicable=True,
                ),
            ),
        )

        for definition_id, subject_ref, payload in steps:
            history = bucket_event_history_repository(bucket_id=str(profile_id))
            before = set(history.load().events)

            _submitted, observed = asyncio.run(
                driver.run(definition_id=definition_id, subject_ref=subject_ref, payload=payload)
            )

            assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED, definition_id
            appended = [event for event_id, event in history.load().events.items() if event_id not in before]
            assert appended, definition_id
            assert {event.actor for event in appended} == {recorded_actor}, definition_id


_AGENT_LABEL = f"agent:mcp.human.{_SESSION_CLIENT}"
_BY_FRONTEND = pytest.mark.parametrize(
    ("frontend", "recorded_actor"), [(_MCP, _AGENT_LABEL), (_CLI, _SUPPLIED_ACTOR)], ids=["mcp", "cli"]
)

_WRITES_THAT_STORE_AN_EVENT: tuple[tuple[str, tuple[str, ...], ConformanceFamily | None], ...] = (
    ("modelo.export", ("actor",), None),
    ("modelo.filing_record.import", ("actor",), None),
    ("modelo.m145.export", ("actor",), None),
    ("modelo.m145.mark_delivered_to_payer", ("actor",), None),
    ("modelo.m145.mark_locally_completed", ("actor",), None),
    # The scenario that creates its declaration before a later stage refuses, so the chain stores something.
    ("modelo.quickfile", ("actor",), MARITIME_QUICKFILE_MATERIAL_CONFORMANCE_FAMILY),
    ("modelo.review_package.build", ("actor",), None),
    ("modelo.work.amend", ("actor",), None),
    ("modelo.work.discard", ("actor",), None),
    ("modelo.work.file", ("actor",), None),
    ("modelo.work.wizard_attempt", ("calculation", "actor"), None),
)
"""Each write with the path of the label its request types and the scenario that makes it store an event."""


def _host_for(definition_id: str, frontend: OperationFrontendProjection) -> OperationExecutionCallerReader:
    """What a session host answers for an invocation of ``definition_id`` it admitted on ``frontend``."""

    def read(identity: OperationIdentity) -> OperationExecutionCaller:
        assert identity.definition_id == definition_id
        return OperationExecutionCaller(frontend=frontend, session_kind=SessionKind.HUMAN, client_id=_SESSION_CLIENT)

    return read


def _typing(payload: BaseModel, path: tuple[str, ...], label: str) -> BaseModel:
    """Return ``payload`` with ``label`` typed at ``path``, which the request must declare."""
    name, *rest = path
    assert name in type(payload).model_fields, (type(payload).__name__, name)
    if not rest:
        return payload.model_copy(update={name: label})
    nested = getattr(payload, name)
    assert isinstance(nested, BaseModel)
    return payload.model_copy(update={name: _typing(nested, tuple(rest), label)})


@pytest.mark.parametrize(
    ("definition_id", "label_path", "family"),
    _WRITES_THAT_STORE_AN_EVENT,
    ids=[name for name, _path, _family in _WRITES_THAT_STORE_AN_EVENT],
)
@_BY_FRONTEND
def test_a_modelo_write_stores_the_session_label_for_an_agent_and_the_supplied_label_for_a_person(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    definition_id: str,
    label_path: tuple[str, ...],
    family: ConformanceFamily | None,
    frontend: OperationFrontendProjection,
    recorded_actor: str,
) -> None:
    """Every event the real executor appends names the label of the session that admitted it."""
    with (
        _model_runtime_for(definition_id),
        _runtime(
            tmp_path / definition_id,
            cleanup=_CloseWitness(),
            execution_caller_reader=_host_for(definition_id, frontend),
        ) as (driver, registry, profile_id),
    ):
        submission = _seeded_conformance_submission(
            registry.lookup(definition_id), profile_id=profile_id, tmp_path=tmp_path, operation=operation, family=family
        )
        payload = _typing(submission.payload, label_path, _SUPPLIED_ACTOR)
        history = bucket_event_history_repository(bucket_id=str(profile_id))
        before = set(history.load().events) if history.exists() else set()

        _submitted, observed = asyncio.run(
            driver.run(
                definition_id=definition_id,
                subject_ref=submission.subject_ref,
                payload=payload,
                secret=submission.secret,
            )
        )

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        appended = [event for event_id, event in history.load().events.items() if event_id not in before]
        assert appended
        assert {event.actor for event in appended} == {recorded_actor}


def _settled(driver: _ExecutionDriver, definition_id: str, subject_ref: str, payload: BaseModel) -> tuple[str, int]:
    """Run one operation to its successful settlement and return its id and terminal revision."""
    submitted, observed = asyncio.run(driver.run(definition_id=definition_id, subject_ref=subject_ref, payload=payload))
    assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
    operation_id, terminal_revision = submitted.receipt.operation_id, observed.projection.revision
    assert isinstance(operation_id, str) and isinstance(terminal_revision, int)
    return operation_id, terminal_revision


@_BY_FRONTEND
def test_the_modelo_390_attestation_is_captured_under_the_session_label_for_an_agent(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded_actor: str,
) -> None:
    """The attestation is an attachment, and its stored manifest names who captured it."""
    definition_id = "modelo.work.m303_attestation"
    with _runtime(
        tmp_path / "attestation", cleanup=_CloseWitness(), execution_caller_reader=_host_for(definition_id, frontend)
    ) as (driver, registry, profile_id):
        submission = _seeded_conformance_submission(
            registry.lookup(definition_id), profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )
        payload = _typing(submission.payload, ("actor",), _SUPPLIED_ACTOR)

        operation_id, terminal_revision = _settled(driver, definition_id, submission.subject_ref, payload)

        result = _resolve_result_projection(
            driver,
            registry,
            definition_id=definition_id,
            operation_id=operation_id,
            terminal_revision=terminal_revision,
            projection_type=ModeloWorkM303AttestationPublicResultV2,
        )
        assert AttachmentStore().load_manifest(result.attachment_id).captured_by == recorded_actor


@_BY_FRONTEND
def test_review_feedback_names_the_session_label_as_its_submitter_for_an_agent(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded_actor: str,
) -> None:
    """The submitter is read from the feedback inside the envelope the real executor wrote."""
    definition_id = "modelo.review_package.encrypt_feedback"
    with _runtime(
        tmp_path / "feedback", cleanup=_CloseWitness(), execution_caller_reader=_host_for(definition_id, frontend)
    ) as (driver, registry, profile_id):
        submission = _seeded_conformance_submission(
            registry.lookup(definition_id), profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )
        payload = _typing(submission.payload, ("submitted_by",), _SUPPLIED_ACTOR)
        assert isinstance(payload, ModeloReviewPackageEncryptFeedbackRequest)

        _settled(driver, definition_id, submission.subject_ref, payload)

        envelope = RecipientEncryptedPackage.model_validate_json(payload.output.read_text(encoding="utf-8"))
        feedback = decrypt_feedback_package_from_originator_envelope(
            envelope,
            originator_private_key_hex=_profile_recipient_keypair(profile_id).private_key_hex,
            recipient_encryption=build_recipient_encryption_capability(bucket_id=str(profile_id)),
        )
        assert feedback.submitted_by == recorded_actor

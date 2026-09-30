"""Registered certificate-source operations preserve exact profile authority."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.application.auth import certificate_source_operation as operation_module
from cadrumo.application.auth.certificate_source_operation import (
    CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID,
    CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID,
    CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID,
    CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID,
    CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID,
    CertificateSourceCheckProjection,
    CertificateSourceCheckRequest,
    CertificateSourceListProjection,
    CertificateSourceListRequest,
    CertificateSourceOperationExecutor,
    CertificateSourceOperationPorts,
    CertificateSourceRegisterProjection,
    CertificateSourceRegisterRequest,
    CertificateSourceRemoveProjection,
    CertificateSourceRemoveRequest,
    CertificateSourceSelectProjection,
    CertificateSourceSelectRequest,
    build_certificate_source_check_definition,
    build_certificate_source_check_registration,
    build_certificate_source_list_definition,
    build_certificate_source_list_registration,
    build_certificate_source_register_definition,
    build_certificate_source_register_registration,
    build_certificate_source_remove_definition,
    build_certificate_source_remove_registration,
    build_certificate_source_select_definition,
    build_certificate_source_select_registration,
    project_certificate_source_check_result,
    project_certificate_source_list_result,
    project_certificate_source_register_result,
    project_certificate_source_remove_result,
    project_certificate_source_select_result,
)
from cadrumo.application.auth.operator_results import (
    CertificateSourceCheckReport,
    CertificateSourceListResult,
    CertificateSourceMutationResult,
    CertificateSourcePayload,
)
from cadrumo.application.auth.tests._operator_probe_fakes import fake_operator_probe_ports
from cadrumo.application.auth.tests._operator_scope_fakes import build_inward_operator_scope_ports
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationRegistry,
)
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.domain.calculations.registry.tests.authority_lease_support import private_authority_lease

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("9aa00000-0000-4000-8000-000000000099")
_NAME = "delegated"
_PATH = Path("C:/certificates/delegated.p12")


def _ports() -> CertificateSourceOperationPorts:
    return CertificateSourceOperationPorts(
        operator_scope_ports=build_inward_operator_scope_ports(session=None),
        operator_probe_ports=fake_operator_probe_ports(),
        certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
    )


def _definitions_and_registrations():
    ports = _ports()
    definitions = (
        build_certificate_source_check_definition(ports),
        build_certificate_source_list_definition(ports),
        build_certificate_source_register_definition(ports),
        build_certificate_source_remove_definition(ports),
        build_certificate_source_select_definition(ports),
    )
    registrations = (
        build_certificate_source_check_registration(definitions[0]),
        build_certificate_source_list_registration(definitions[1]),
        build_certificate_source_register_registration(definitions[2]),
        build_certificate_source_remove_registration(definitions[3]),
        build_certificate_source_select_registration(definitions[4]),
    )
    return ports, definitions, registrations


def _requests() -> tuple[OperationRequest[BaseModel], ...]:
    values: tuple[tuple[str, BaseModel], ...] = (
        (
            CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID,
            CertificateSourceRegisterRequest(
                profile_id=_PROFILE, name=_NAME, certificate_path=_PATH, friendly_name="Gestor"
            ),
        ),
        (CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID, CertificateSourceListRequest(profile_id=_PROFILE)),
        (
            CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID,
            CertificateSourceSelectRequest(profile_id=_PROFILE, name=_NAME),
        ),
        (
            CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID,
            CertificateSourceRemoveRequest(profile_id=_PROFILE, name=_NAME),
        ),
        (CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID, CertificateSourceCheckRequest(profile_id=_PROFILE)),
    )
    return tuple(
        OperationRequest[BaseModel](
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(_PROFILE)),
            payload=payload,
        )
        for definition_id, payload in values
    )


def test_request_shapes_are_closed_and_use_secure_reference_custody() -> None:
    request = CertificateSourceRegisterRequest(
        profile_id=_PROFILE,
        name="  delegated  ",
        certificate_path=_PATH,
        friendly_name=" Gestor ",
    )
    assert request.name == _NAME
    assert request.friendly_name == "Gestor"
    assert CertificateSourceRegisterRequest.model_validate_json(request.model_dump_json(), strict=True) == request
    with pytest.raises(ValidationError):
        CertificateSourceRegisterRequest(
            profile_id=_PROFILE,
            name="  ",
            certificate_path=_PATH,
        )
    with pytest.raises(ValidationError):
        CertificateSourceRegisterRequest.model_validate(
            {
                "profile_id": _PROFILE,
                "name": _NAME,
                "certificate_path": _PATH,
                "password": "synthetic-passphrase-sentinel",
            }
        )

    ports, definitions, registrations = _definitions_and_registrations()
    del ports
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
    assert tuple(item.definition_id for item in definitions) == tuple(
        sorted(item.definition_id for item in definitions)
    )
    assert tuple(registry.lookup(item.definition_id).permitted_frontends for item in definitions) == tuple(
        frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}) for _ in definitions
    )
    assert all(
        definition.capabilities.request_storage.value == "secure_reference"
        and definition.capabilities.sensitive_input.value == "secure_reference"
        for definition in definitions
    )
    assert "password" not in CertificateSourceRegisterRequest.model_json_schema()["properties"]


@pytest.mark.parametrize("action", [AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT])
def test_every_source_verb_requires_human_authority_and_exact_profile(action: AccessAction) -> None:
    _ports_value, definitions, registrations = _definitions_and_registrations()
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
    for request in _requests():
        contract = registry.lookup_public_contract(request.definition_id)
        context = OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=uuid4(),
            action=action,
            frontend=OperationFrontendProjection.CLI,
            contract=contract,
            published_authority=Availability.AVAILABLE,
        )
        if action is AccessAction.RESULT:
            schema = contract.result_schema
            assert schema is not None
            resolved = resolve_operation_access(registry=registry, request=request, context=context)
            disclosure = next(iter(resolved.policy.disclosures))
            assert disclosure.category is DisclosureCategory.PROFILE_VALUES
            assert disclosure.projection_id == schema.schema_id
            assert resolved.policy.requires_human
        else:
            resolved = resolve_operation_access(registry=registry, request=request, context=context)
            assert resolved.policy.requires_human

        wrong_frontend = replace(context, frontend=OperationFrontendProjection.MCP)
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(registry=registry, request=request, context=wrong_frontend)
        assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED

        wrong_profile = replace(context, profile_id=uuid4())
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(registry=registry, request=request, context=wrong_profile)
        assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_only_source_mutations_require_a_commit_grant() -> None:
    _ports_value, definitions, registrations = _definitions_and_registrations()
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
    mutation_ids = {
        CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID,
        CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID,
        CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID,
    }
    for request in _requests():
        contract = registry.lookup_public_contract(request.definition_id)
        context = OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=uuid4(),
            action=AccessAction.COMMIT,
            frontend=OperationFrontendProjection.TUI,
            contract=contract,
            published_authority=Availability.AVAILABLE,
        )
        if request.definition_id in mutation_ids:
            resolved = resolve_operation_access(registry=registry, request=request, context=context)
            assert AccessAction.COMMIT in resolved.policy.actions
        else:
            with pytest.raises(ProfileAccessRefusedError) as refused:
                resolve_operation_access(registry=registry, request=request, context=context)
            assert refused.value.reason is AccessDenialCode.OPERATION_DENIED


class _Events:
    def __init__(self) -> None:
        self.phases: list[str] = []
        self.effects: list[OperationEffect] = []

    async def phase(self, phase_code: str) -> None:
        self.phases.append(phase_code)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Cancellation:
    def __init__(self) -> None:
        self.inside_irreversible_section = False

    @asynccontextmanager
    async def irreversible_section(self):
        self.inside_irreversible_section = True
        try:
            yield
        finally:
            self.inside_irreversible_section = False


class _Operands:
    def __init__(self, cancellation: _Cancellation, events: _Events) -> None:
        self.cancellation = cancellation
        self.events = events
        self.value: BaseModel | None = None

    async def put(self, operand: BaseModel, *, written_at):
        del written_at
        assert self.events.effects[-1] in {OperationEffect.NONE, OperationEffect.UPDATED}
        assert self.cancellation.inside_irreversible_section is (
            self.events.effects[-2] is OperationEffect.UNKNOWN if len(self.events.effects) > 1 else False
        )
        self.value = operand
        return "d" * 64


class _Context:
    def __init__(self, definition_id: str, authority_operation) -> None:
        self.identity = OperationIdentity(
            operation_id="c" * 64,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        )
        self.authority_operation = authority_operation
        self.events = _Events()
        self.cancellation = _Cancellation()
        self.operands = _Operands(self.cancellation, self.events)


@pytest.mark.parametrize(
    ("definition_id", "service_name", "result", "effect", "projector", "projection_type"),
    (
        (
            CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID,
            "register_operator_certificate_source",
            CertificateSourceMutationResult(name=_NAME, certificate_path=str(_PATH)),
            OperationEffect.UPDATED,
            project_certificate_source_register_result,
            CertificateSourceRegisterProjection,
        ),
        (
            CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID,
            "list_operator_certificate_sources",
            CertificateSourceListResult(
                sources=(CertificateSourcePayload(name=_NAME, certificate_path=str(_PATH), active=True),),
                active_source=_NAME,
            ),
            OperationEffect.NONE,
            project_certificate_source_list_result,
            CertificateSourceListProjection,
        ),
        (
            CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID,
            "select_operator_certificate_source",
            CertificateSourceMutationResult(name=_NAME, certificate_path=str(_PATH), active=True),
            OperationEffect.UPDATED,
            project_certificate_source_select_result,
            CertificateSourceSelectProjection,
        ),
        (
            CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID,
            "remove_operator_certificate_source",
            CertificateSourceMutationResult(name=_NAME, removed=True),
            OperationEffect.UPDATED,
            project_certificate_source_remove_result,
            CertificateSourceRemoveProjection,
        ),
        (
            CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID,
            "check_operator_certificate_sources",
            CertificateSourceCheckReport(entries=(), has_warnings=False),
            OperationEffect.NONE,
            project_certificate_source_check_result,
            CertificateSourceCheckProjection,
        ),
    ),
)
def test_executor_calls_canonical_service_and_projects_correlated_result(
    monkeypatch: pytest.MonkeyPatch,
    definition_id: str,
    service_name: str,
    result: BaseModel,
    effect: OperationEffect,
    projector,
    projection_type: type[BaseModel],
) -> None:
    ports = _ports()
    calls: list[dict[str, object]] = []
    context_ref: list[_Context] = []

    def service(*args, **kwargs):
        del args
        context = context_ref[0]
        if definition_id in {
            CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID,
            CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID,
            CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID,
        }:
            assert context.cancellation.inside_irreversible_section
            assert context.events.effects == [OperationEffect.UNKNOWN]
            assert kwargs["operation"] is context.authority_operation
            assert kwargs["operator_scope_ports"] is ports.operator_scope_ports
        if definition_id == CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID:
            assert kwargs["operator_scope_ports"] is ports.operator_scope_ports
            assert kwargs["operator_probe_ports"] is ports.operator_probe_ports
            assert kwargs["certificate_secret_backend_factory"] is ports.certificate_secret_backend_factory
        if definition_id == CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID:
            assert kwargs == {
                "name": _NAME,
                "certificate_path": _PATH,
                "friendly_name": "Gestor",
                "operation": context.authority_operation,
                "operator_scope_ports": ports.operator_scope_ports,
            }
        elif definition_id in {
            CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID,
            CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID,
        }:
            assert kwargs["name"] == _NAME
        elif definition_id == CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID:
            assert kwargs == {}
        calls.append(kwargs)
        return result

    monkeypatch.setattr(operation_module, service_name, service)
    monkeypatch.setattr(operation_module, "require_active_bucket_id", lambda: str(_PROFILE))
    with private_authority_lease() as authority_operation:
        context = _Context(definition_id, authority_operation)
        context_ref.append(context)
        executor = CertificateSourceOperationExecutor(ports=ports, definition_id=definition_id)
        ref = asyncio.run(_run_executor(executor, _request_for(definition_id), context))

    assert ref == "d" * 64
    assert len(calls) == 1
    expected_effects = (
        [OperationEffect.UNKNOWN, effect]
        if definition_id
        in {
            CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID,
            CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID,
            CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID,
        }
        else [effect]
    )
    assert context.events.effects == expected_effects
    private_result = context.operands.value
    assert private_result == result
    assert private_result is not None
    assert context.events.phases == [
        f"{definition_id}.preflight",
        *([f"{definition_id}.commit"] if len(expected_effects) == 2 else []),
        f"{definition_id}.settlement",
    ]
    receipt = OperationTerminalReceipt(
        identity=context.identity,
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        settled_at=datetime.now(UTC),
        result_ref=ref,
    )
    projected = projector(private_result, receipt)
    assert isinstance(projected, projection_type)
    projected_profile = cast(
        CertificateSourceRegisterProjection
        | CertificateSourceListProjection
        | CertificateSourceSelectProjection
        | CertificateSourceRemoveProjection
        | CertificateSourceCheckProjection,
        projected,
    )
    assert projected_profile.profile_id == _PROFILE


def _request_for(definition_id: str) -> OperationRequest[BaseModel]:
    return next(request for request in _requests() if request.definition_id == definition_id)


async def _run_executor(
    executor: CertificateSourceOperationExecutor,
    request: OperationRequest[BaseModel],
    context: _Context,
) -> str:
    return await executor.execute(request, cast(OperationExecutorContext, context))


def test_remove_noop_is_projected_as_no_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    ports = _ports()
    missing = CertificateSourceMutationResult(name="missing", removed=False)
    monkeypatch.setattr(operation_module, "remove_operator_certificate_source", lambda **_kwargs: missing)
    monkeypatch.setattr(operation_module, "require_active_bucket_id", lambda: str(_PROFILE))
    with private_authority_lease() as authority_operation:
        context = _Context(CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID, authority_operation)
        result_ref = asyncio.run(
            CertificateSourceOperationExecutor(
                ports=ports,
                definition_id=CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID,
            ).execute(
                _request_for(CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID),
                cast(OperationExecutorContext, context),
            )
        )
    assert result_ref == "d" * 64
    assert context.events.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    receipt = OperationTerminalReceipt(
        identity=context.identity,
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=datetime.now(UTC),
        result_ref=result_ref,
    )
    private_result = context.operands.value
    assert private_result is not None
    assert project_certificate_source_remove_result(private_result, receipt).result == missing


def test_read_cancellation_waits_for_blocking_service_and_result_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ports = _ports()
    started = Event()
    release = Event()
    report = CertificateSourceListResult()

    def blocked_read() -> CertificateSourceListResult:
        started.set()
        if not release.wait(timeout=10):
            raise TimeoutError("test did not release the blocked certificate-source read")
        return report

    monkeypatch.setattr(operation_module, "list_operator_certificate_sources", blocked_read)
    monkeypatch.setattr(operation_module, "require_active_bucket_id", lambda: str(_PROFILE))
    with private_authority_lease() as authority_operation:
        context = _Context(CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID, authority_operation)
        executor = CertificateSourceOperationExecutor(
            ports=ports,
            definition_id=CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID,
        )

        async def cancel_during_read() -> None:
            task = asyncio.create_task(
                _run_executor(executor, _request_for(CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID), context)
            )
            await asyncio.wait_for(asyncio.to_thread(started.wait), timeout=5)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task

        asyncio.run(cancel_during_read())

    assert context.events.effects == [OperationEffect.NONE]
    assert context.operands.value == report


@pytest.mark.parametrize(
    ("payload", "definition_id"),
    (
        (
            CertificateSourceRegisterRequest(profile_id=_PROFILE, name=_NAME, certificate_path=_PATH),
            CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID,
        ),
        (CertificateSourceListRequest(profile_id=_PROFILE), CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID),
        (
            CertificateSourceSelectRequest(profile_id=_PROFILE, name=_NAME),
            CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID,
        ),
        (
            CertificateSourceRemoveRequest(profile_id=_PROFILE, name=_NAME),
            CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID,
        ),
        (CertificateSourceCheckRequest(profile_id=_PROFILE), CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID),
    ),
)
def test_executor_refuses_when_active_profile_differs(
    monkeypatch: pytest.MonkeyPatch,
    payload: BaseModel,
    definition_id: str,
) -> None:
    monkeypatch.setattr(operation_module, "require_active_bucket_id", lambda: str(uuid4()))
    with private_authority_lease() as authority_operation:
        context = _Context(definition_id, authority_operation)
        with pytest.raises(ProfileAccessRefusedError) as refused:
            asyncio.run(
                _run_executor(
                    CertificateSourceOperationExecutor(ports=_ports(), definition_id=definition_id),
                    OperationRequest[BaseModel](
                        definition_id=definition_id,
                        subject_ref=profile_operation_subject(str(_PROFILE)),
                        payload=payload,
                    ),
                    context,
                )
            )
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH

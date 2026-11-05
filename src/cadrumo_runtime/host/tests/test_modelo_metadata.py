"""Installed worker enforces persisted Modelo period scope and result disclosure."""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.custody.tests.native_enrollment_recipient import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from cadrumo.application.modelo.operation_shared import (
    MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID,
    MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
)
from cadrumo.application.modelo.work_change_contracts import (
    ModeloWorkDiscardBaseline,
    ModeloWorkDiscardRequest,
    ModeloWorkRenamePublicResultV2,
    ModeloWorkRenameRequest,
)
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.core.period import Period
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from cadrumo.entrypoints.tests.production_operation_registry import production_operation_registry
from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.contracts.deadline_budget import exchange_deadline
from cadrumo_client.contracts.operation_access import (
    OperationContract,
    OperationContractReply,
    OperationProjected,
    OperationReply,
    OperationResult,
    OperationSubmit,
    OperationSubmitted,
)
from cadrumo_client.contracts.profile_access import (
    AccessRefusal,
    SessionRequest,
    SessionsLocked,
)
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import owner_id
from .served_runtime import SyntheticLogin, admit_session, serving_runtime, start_and_settle

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_FIRST = Period.from_year_and_code(2026, "1T")
_SECOND = Period.from_year_and_code(2026, "2T")
_CREATED = datetime(2020, 1, 1, tzinfo=UTC)
_RENAME = MODELO_WORK_RENAME_OPERATION_DEFINITION_ID
_DISCARD = MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID


def _unit(profile_id: UUID, period: Period) -> WorkUnit:
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(profile_id),
            modelo="130",
            filing_year=2026,
            period=period,
            revision_id="2019-y-siguientes",
        ),
        bucket_id=str(profile_id),
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id="2019-y-siguientes",
        name=f"M130 {period.registry_token}",
        created_at=_CREATED,
        updated_at=_CREATED,
    )


def seed_periods(profile_id: UUID) -> tuple[WorkUnit, WorkUnit]:
    """Persist two canonical units into the actual encrypted catalogue."""
    units = (_unit(profile_id, _FIRST), _unit(profile_id, _SECOND))
    repository = WorkUnitCatalogueRepository(
        bucket_id=str(profile_id), objects=secure_object_repository_for_active_bucket()
    )
    catalogue = repository.load()
    for unit in units:
        catalogue = upsert_work_unit(catalogue, unit)
    repository.save(catalogue)
    assert {unit.period for unit in repository.load()} == {_FIRST, _SECOND}
    return units


def _scope(destination_id: UUID) -> AccessScope:
    registry = production_operation_registry()
    disclosures = {
        DisclosurePermission(
            destination_id=destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
    }
    for definition_id in (_RENAME, _DISCARD):
        schema = registry.lookup_public_contract(definition_id).result_schema
        assert schema is not None
        disclosures.add(
            DisclosurePermission(
                destination_id=destination_id,
                projection_id=schema.schema_id,
                category=DisclosureCategory.TAX_VALUES,
            )
        )
    return AccessScope(
        operations=frozenset({_RENAME, _DISCARD}),
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.COMMIT,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
        ),
        disclosures=frozenset(disclosures),
        periods=frozenset({_FIRST}),
        allow_period_independent=False,
        allow_delegation=False,
    )


def issue_scoped_key(subject: AdministrationSubject, *, scope: AccessScope | None = None) -> bytes:
    requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
    subject.owner.requesting = requester
    subject.owner.delivery.endpoint = NativeEnrollmentRecipient(
        requester=requester, secrets_store=subject.client_native
    )
    scope = _scope(requester.client_id) if scope is None else scope
    facts = subject.owner.current
    assert facts.session is not None
    subject.owner.current = changed(
        facts,
        profile=changed(facts.profile, scope=scope),
        session=changed(facts.session, scope=scope),
    )
    request_id = uuid4()
    subject.service.request(request_id, changed(subject.proposal, scope=scope))
    receipt = subject.approve(request_id)
    record = next(item for item in subject.store.enrollment_state().requests if item.request_id == request_id)
    credential = subject.owner.delivery.endpoint.possession(record)
    assert receipt.key_id is not None and credential is not None
    return credential.get_secret_value()


def connect(endpoint: WindowsEndpoint) -> VerifiedConnection:
    return VerifiedConnection(
        endpoint.connect(timeout=HANG_GUARD_SECONDS),
        expected=ClientHello(product_version="test", storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + HANG_GUARD_SECONDS,
    )


def submit(
    connection: VerifiedConnection,
    profile_id: UUID,
    session_id: UUID,
    *,
    definition_id: str,
    subject_ref: str,
    payload_json: str,
) -> OperationReply | AccessRefusal:
    return connection.operation(
        OperationSubmit(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            definition_id=definition_id,
            subject_ref=subject_ref,
            payload_json=payload_json,
        ),
        deadline=exchange_deadline(),
    )


def test_native_modelo_metadata_scope_uses_persisted_period_and_fences_result(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    installation_state = installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation_state.installation_id
    ) as subject:
        profile_id = subject.store.binding.profile_id
        allowed_unit, forbidden_unit = seed_periods(profile_id)
        api_key = issue_scoped_key(subject)
        close_active_bucket_session()

        with serving_runtime(
            endpoint,
            root,
            capture_login=lambda _channel: SyntheticLogin("native-modelo-metadata-test-login"),
            secret_store=lambda: subject.native,
        ):
            api, human = connect(endpoint), connect(endpoint)
            try:
                # The person signs in first; the key admits only while they are signed in.
                human_session = admit_session(human, profile_id, method="password", proof=PROFILE_INPUT.encode())
                api_session = admit_session(api, profile_id, method="api_key", proof=api_key)
                contract = api.operation(
                    OperationContract(
                        request_id=uuid4(),
                        profile_id=profile_id,
                        session_id=api_session,
                        definition_id=_RENAME,
                    ),
                    deadline=time.monotonic() + 5,
                )
                assert isinstance(contract, OperationContractReply), contract
                payload = ModeloWorkRenameRequest(
                    work_unit_id=allowed_unit.work_unit_id,
                    new_name="Scoped native rename",
                    observed_name=allowed_unit.name,
                    observed_updated_at=allowed_unit.updated_at,
                    actor="native-test-operator",
                )
                submitted = submit(
                    api,
                    profile_id,
                    api_session,
                    definition_id=_RENAME,
                    subject_ref=allowed_unit.work_unit_id,
                    payload_json=payload.model_dump_json(),
                )
                assert isinstance(submitted, OperationSubmitted), submitted
                operation_id = submitted.receipt.operation_id
                projection = start_and_settle(api, profile_id, api_session, operation_id, settle_seconds=10)
                assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert projection.effect is OperationEffect.UPDATED
                result_schema = contract.contract.result_schema
                assert result_schema is not None
                result_request = OperationResult(
                    request_id=uuid4(),
                    profile_id=profile_id,
                    session_id=api_session,
                    result=OperationResultProjectionRequestV1(
                        operation_id=operation_id,
                        terminal_revision=projection.revision,
                        definition_contract_digest=contract.contract.definition_contract_digest,
                        result_schema=result_schema,
                    ),
                )
                result = api.operation(result_request, deadline=time.monotonic() + 5)
                assert isinstance(result, OperationProjected), result
                typed = OperationResultProjectionSuccessV1[ModeloWorkRenamePublicResultV2].model_validate_json(
                    json.dumps(result.document)
                )
                assert typed.projection.work_unit_id == allowed_unit.work_unit_id
                assert typed.projection.name == "Scoped native rename"
                assert typed.projection.bucket_id == str(profile_id)

                denied_period = submit(
                    api,
                    profile_id,
                    api_session,
                    definition_id=_RENAME,
                    subject_ref=forbidden_unit.work_unit_id,
                    payload_json=ModeloWorkRenameRequest(
                        work_unit_id=forbidden_unit.work_unit_id,
                        new_name="Forbidden period",
                        observed_name=forbidden_unit.name,
                        observed_updated_at=forbidden_unit.updated_at,
                        actor="native-test-operator",
                    ).model_dump_json(),
                )
                assert isinstance(denied_period, AccessRefusal), denied_period
                assert denied_period.code is AccessDenialCode.PERIOD_DENIED
                denied_discard = submit(
                    api,
                    profile_id,
                    api_session,
                    definition_id=_DISCARD,
                    subject_ref=forbidden_unit.work_unit_id,
                    payload_json=ModeloWorkDiscardRequest(
                        baseline=ModeloWorkDiscardBaseline(
                            work_unit_id=forbidden_unit.work_unit_id,
                            name=forbidden_unit.name,
                            observed_updated_at=forbidden_unit.updated_at,
                        ),
                        reason="not in granted period",
                        actor="native-test-operator",
                    ).model_dump_json(),
                )
                assert isinstance(denied_discard, AccessRefusal), denied_discard
                assert denied_discard.code is AccessDenialCode.PERIOD_DENIED
                mismatched_subject = submit(
                    api,
                    profile_id,
                    api_session,
                    definition_id=_RENAME,
                    subject_ref=forbidden_unit.work_unit_id,
                    payload_json=payload.model_dump_json(),
                )
                assert isinstance(mismatched_subject, AccessRefusal), mismatched_subject
                assert mismatched_subject.code is AccessDenialCode.OPERATION_DENIED
                mismatched_profile = submit(
                    api,
                    uuid4(),
                    api_session,
                    definition_id=_RENAME,
                    subject_ref=allowed_unit.work_unit_id,
                    payload_json=payload.model_dump_json(),
                )
                assert isinstance(mismatched_profile, AccessRefusal), mismatched_profile
                assert mismatched_profile.code is AccessDenialCode.PROFILE_MISMATCH

                locked = human.session(
                    SessionRequest(
                        action="session_lock",
                        request_id=uuid4(),
                        profile_id=profile_id,
                        session_id=human_session,
                        target_session_id=api_session,
                    ),
                    deadline=time.monotonic() + 5,
                )
                assert isinstance(locked, SessionsLocked) and api_session in locked.session_ids
                after_lock = api.operation(
                    result_request.model_copy(update={"request_id": uuid4()}), deadline=time.monotonic() + 5
                )
                assert isinstance(after_lock, AccessRefusal), after_lock
                assert after_lock.code in {
                    AccessDenialCode.SESSION_INACTIVE,
                    AccessDenialCode.AUTHENTICATION_REQUIRED,
                }
            finally:
                api.close()
                human.close()

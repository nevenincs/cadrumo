"""Native revision selection and local filing retain exact profile authority."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import administration_subject, changed
from cadrumo.adapters.persistence.storage.custody.tests.native_enrollment_recipient import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.modelo.revision_selection_operation import (
    ModeloWorkRevisionProjection,
    ModeloWorkRevisionRequest,
)
from cadrumo.application.modelo.work_calculation_contracts import (
    ModeloWorkCalculatePublicResultV2,
    ModeloWorkCalculateRequest,
)
from cadrumo.application.modelo.work_filing_contracts import (
    ModeloWorkFileApproval,
    ModeloWorkFilePublicResultV2,
    ModeloWorkFileRequest,
)
from cadrumo.application.modelo.work_verification_contracts import (
    ModeloWorkVerifyPublicResultV2,
    ModeloWorkVerifyRequest,
)
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationContract,
    RuntimeOperationContractReply,
    RuntimeOperationControl,
    RuntimeOperationProjected,
    RuntimeOperationResult,
    RuntimeOperationSubmitted,
)
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.operation_composition import build_production_operation_registry
from cadrumo.entrypoints.tests.modelo_operation_test_support import (
    seeded_modelo_verification_report,
    seeded_modelo_work_unit,
)

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections
from .test_modelo_metadata import _admit, _connect, _LoginObservation, _submit
from .test_modelo_metadata_history import _observe

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def _run[T: BaseModel](
    client: VerifiedRuntimeConnection,
    profile_id: UUID,
    session_id: UUID,
    *,
    definition_id: str,
    subject_ref: str,
    payload: BaseModel,
    result_type: type[T],
) -> tuple[T, OperationEffect]:
    deadline = time.monotonic() + 30
    contract = client.operation(
        RuntimeOperationContract(
            request_id=uuid4(), profile_id=profile_id, session_id=session_id, definition_id=definition_id
        ),
        deadline=deadline,
    )
    assert isinstance(contract, RuntimeOperationContractReply), contract
    submitted = _submit(
        client,
        profile_id,
        session_id,
        definition_id=definition_id,
        subject_ref=subject_ref,
        payload_json=payload.model_dump_json(),
    )
    assert isinstance(submitted, RuntimeOperationSubmitted), submitted
    operation_id = submitted.receipt.operation_id
    started = client.operation(
        RuntimeOperationControl(
            action="operation_start",
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            operation_id=operation_id,
        ),
        deadline=deadline,
    )
    assert isinstance(started, RuntimeOperationAcknowledged), started
    while True:
        terminal = _observe(client, profile_id, session_id, operation_id).projection
        if terminal.terminal_condition is not None:
            break
        assert time.monotonic() < deadline
        time.sleep(0.02)
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED, terminal
    schema = contract.contract.result_schema
    assert schema is not None
    result = client.operation(
        RuntimeOperationResult(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            result=OperationResultProjectionRequestV1(
                operation_id=operation_id,
                terminal_revision=terminal.revision,
                definition_contract_digest=contract.contract.definition_contract_digest,
                result_schema=schema,
            ),
        ),
        deadline=deadline,
    )
    assert isinstance(result, RuntimeOperationProjected), result
    projected = OperationResultProjectionSuccessV1[
        ModeloWorkRevisionProjection
        | ModeloWorkVerifyPublicResultV2
        | ModeloWorkFilePublicResultV2
        | ModeloWorkCalculatePublicResultV2
    ].model_validate_json(canonical_json_bytes(result.document))
    assert projected.definition_contract_digest == contract.contract.definition_contract_digest
    assert projected.result_schema == schema
    return result_type.model_validate(projected.projection), terminal.effect


@pytest.mark.parametrize("calculate_in_runtime", [False, True])
def test_native_scoped_revision_verify_and_file_return_actual_receipts(
    tmp_path: Path, *, operation: PinnedAuthorityOperation, calculate_in_runtime: bool
) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        profile_id = subject.store.binding.profile_id
        if calculate_in_runtime:
            unit = seeded_modelo_work_unit(profile_id, operation=operation)
            revision_id = report_id = None
        else:
            revision_id, report_id = seeded_modelo_verification_report(profile_id, operation=operation)
            revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
            assert revision is not None
            unit = WorkUnitCatalogueRepository().load().get(revision.work_unit_id)
            assert unit is not None
        requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
        subject.owner.requesting = requester
        recipient = NativeEnrollmentRecipient(requester=requester, secrets_store=subject.client_native)
        subject.owner.delivery.endpoint = recipient
        definitions = frozenset({"modelo.work.revision", "modelo.work.verify", "modelo.work.file"})
        if calculate_in_runtime:
            definitions |= {"modelo.work.calculate"}
        registry = build_production_operation_registry()
        disclosures = {
            DisclosurePermission(
                destination_id=requester.client_id,
                projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                category=DisclosureCategory.OPERATION_METADATA,
            )
        }
        for definition_id in definitions:
            result_schema = registry.lookup_public_contract(definition_id).result_schema
            assert result_schema is not None
            disclosures.add(
                DisclosurePermission(
                    destination_id=requester.client_id,
                    projection_id=result_schema.schema_id,
                    category=DisclosureCategory.TAX_VALUES,
                )
            )
        scope = AccessScope(
            operations=definitions,
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
            periods=frozenset({unit.period}),
            allow_period_independent=False,
            allow_delegation=False,
        )
        facts = subject.owner.current
        assert facts.session is not None
        subject.owner.current = changed(
            facts, profile=changed(facts.profile, scope=scope), session=changed(facts.session, scope=scope)
        )
        request_id = uuid4()
        subject.service.request(request_id, changed(subject.proposal, scope=scope))
        subject.approve(request_id)
        enrollment = next(item for item in subject.store.enrollment_state().requests if item.request_id == request_id)
        credential = recipient.possession(enrollment)
        assert credential is not None
        key = credential.get_secret_value()
        close_active_bucket_session()

        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                client = _connect(endpoint)
                try:
                    session_id = _admit(client, profile_id, method="api_key", proof=key)
                    if calculate_in_runtime:
                        calculate = ModeloWorkCalculateRequest.model_validate_json(
                            canonical_json_bytes(
                                {
                                    "work_unit_id": unit.work_unit_id,
                                    "actor": "native-operator",
                                    "caller_context": "explicit",
                                    "inputs": {
                                        "binding_overrides": [
                                            {"key": key, "value": "0"}
                                            for key in (
                                                "irpf.previous_year_economic_activity_net_income",
                                                "modelo-130-resultados-negativos-anteriores",
                                                "modelo-130-pagos-fraccionados-anteriores",
                                            )
                                        ]
                                    },
                                }
                            )
                        )
                        calculated, calculate_effect = _run(
                            client,
                            profile_id,
                            session_id,
                            definition_id="modelo.work.calculate",
                            subject_ref=unit.work_unit_id,
                            payload=calculate,
                            result_type=ModeloWorkCalculatePublicResultV2,
                        )
                        assert calculate_effect is OperationEffect.UPDATED
                        assert calculated.revision_published
                        assert calculated.calculation.bucket_id == str(profile_id)
                        assert calculated.unit.work_unit_id == unit.work_unit_id
                        assert calculated.unit.current_calculation_revision_id == calculated.calculation_revision_id
                        assert calculated.calculation.registry_snapshot_ref.revision_id == unit.revision_id
                        assert calculated.calculation.period.to_period() == unit.period
                        revision_id = calculated.calculation_revision_id
                        repeated, repeat_effect = _run(
                            client,
                            profile_id,
                            session_id,
                            definition_id="modelo.work.calculate",
                            subject_ref=unit.work_unit_id,
                            payload=calculate,
                            result_type=ModeloWorkCalculatePublicResultV2,
                        )
                        assert repeated.calculation_revision_id == revision_id
                        assert not repeated.revision_published
                        # The revision witness does not cover incidental writers.
                        assert repeat_effect is OperationEffect.UNKNOWN
                    assert revision_id is not None
                    selected, read_effect = _run(
                        client,
                        profile_id,
                        session_id,
                        definition_id="modelo.work.revision",
                        subject_ref=profile_operation_subject(str(profile_id)),
                        payload=ModeloWorkRevisionRequest(profile_id=profile_id, calculation_revision_id=revision_id),
                        result_type=ModeloWorkRevisionProjection,
                    )
                    assert read_effect is OperationEffect.NONE
                    assert selected.verification_report_id == report_id
                    assert selected.unit.work_unit_id == unit.work_unit_id
                    verified, verify_effect = _run(
                        client,
                        profile_id,
                        session_id,
                        definition_id="modelo.work.verify",
                        subject_ref=unit.work_unit_id,
                        payload=ModeloWorkVerifyRequest(calculation_revision_id=revision_id, actor="native-operator"),
                        result_type=ModeloWorkVerifyPublicResultV2,
                    )
                    assert verify_effect is (OperationEffect.UPDATED if calculate_in_runtime else OperationEffect.NONE)
                    if report_id is not None:
                        assert verified.verification.report.verification_report_id == report_id
                    assert verified.verification.published is calculate_in_runtime
                    report_id = verified.verification_report_id
                    assert verified.advisories.work_unit_id == unit.work_unit_id
                    assert verified.advisories.calculation_revision_id == revision_id
                    assert verified.advisories.period == unit.period.registry_token
                    filing = ModeloWorkFileRequest(
                        approval=ModeloWorkFileApproval(
                            calculation_revision_id=revision_id, verification_report_id=report_id
                        ),
                        actor="native-operator",
                    )
                    receipts = []
                    for expected_effect in (OperationEffect.UPDATED, OperationEffect.NONE):
                        filed, file_effect = _run(
                            client,
                            profile_id,
                            session_id,
                            definition_id="modelo.work.file",
                            subject_ref=unit.work_unit_id,
                            payload=filing,
                            result_type=ModeloWorkFilePublicResultV2,
                        )
                        assert file_effect is expected_effect
                        assert filed.published is (expected_effect is OperationEffect.UPDATED)
                        record = filed.record.to_record()
                        assert record.bucket_id == str(profile_id)
                        assert record.calculation_revision_id == revision_id
                        assert not record.aeat_accepted
                        assert filed.handoff_required
                        assert filed.advisories == verified.advisories
                        receipts.append(record)
                    assert receipts[0] == receipts[1]
                    denied = _submit(
                        client,
                        profile_id,
                        session_id,
                        definition_id="modelo.work.file",
                        subject_ref=revision_id,
                        payload_json=filing.model_dump_json(),
                    )
                    assert isinstance(denied, RuntimeAccessRefusal)
                    assert denied.code is AccessDenialCode.OPERATION_DENIED
                finally:
                    client.close()
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    running.result(timeout=20)
                except Exception:
                    if primary is None:
                        raise
                finally:
                    endpoint.close()

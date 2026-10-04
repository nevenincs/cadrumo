"""A native human session reads one exact-profile registered workbench generation."""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from textual.pilot import Pilot
from textual.widgets import Input, Select, Static

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.workbench_generation import read_workbench_generation
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.custody.tests.native_enrollment_recipient import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.master_key.active_session import (
    close_active_bucket_session,
    current_active_bucket_session,
)
from cadrumo.application.modelo.operation_definitions import MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.work_verification_contracts import ModeloWorkVerifyPublicResultV2
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationId
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationSchemaIdentityV1
from cadrumo.application.overview.home import HomeAccountSession, HomeSessionPosture
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationContract,
    RuntimeOperationContractReply,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationPage,
    RuntimeOperationResultPage,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal
from cadrumo.application.runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES, ProjectionPageRequest
from cadrumo.application.search.workbench import WorkbenchDestinationAdmissionState
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    LoginEligibility,
    OsLoginContext,
    SessionKind,
)
from cadrumo.application.workbench_generation_contracts import WorkbenchGenerationAvailability, WorkbenchGenerationV1
from cadrumo.application.workbench_generation_operation import (
    WORKBENCH_GENERATION_OPERATION_DEFINITION_ID,
    WorkbenchGenerationOperationRequest,
)
from cadrumo.application.workbench_generation_projection import (
    WorkbenchGenerationOperationProjection,
    project_workbench_generation,
    restore_workbench_generation,
)
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.identity.digest import ContentDigest
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.operation_composition import build_production_operation_registry
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.tests.modelo_operation_test_support import seeded_modelo_calculation_revision
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.app import CadrumoTuiApp, RootPresentationV1
from cadrumo.entrypoints.tui.components.account_chrome import AccountActionV1
from cadrumo.entrypoints.tui.declarations.overview import DeclarationsOverviewScreen
from cadrumo.entrypoints.tui.launcher import main, run_precomposed_runtime_root_session
from cadrumo.entrypoints.tui.modelo.lifecycle import ModeloWorkspaceLifecycleDoor
from cadrumo.entrypoints.tui.modelo.workbench.installed import InstalledModeloWorkbench
from cadrumo.entrypoints.tui.modelo.workbench.screen import ModeloWorkbenchScreen
from cadrumo.entrypoints.tui.navigation import TuiFocusIdentityV1, TuiNavigationTargetV1, TuiScreenContextV1
from cadrumo.entrypoints.tui.operations.runtime_controller import RuntimeOperationController
from cadrumo.entrypoints.tui.profile.overview import ProfileManagerScreen
from cadrumo.entrypoints.tui.runtime_session import RuntimeRestrictedSessionApp
from cadrumo.entrypoints.tui.runtime_workbench import RuntimeWorkbenchRoot
from cadrumo.entrypoints.tui.secret.runtime_login import RuntimeLoginScreen
from cadrumo.entrypoints.tui.secret.runtime_login_contracts import RuntimeLoginMethod
from cadrumo.entrypoints.workbench_generation_composition import compose_secure_workbench_generation_provider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "tui-workbench-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _connect(endpoint: WindowsRuntimeEndpoint) -> VerifiedRuntimeConnection:
    return VerifiedRuntimeConnection(
        endpoint.connect(timeout=3),
        expected=RuntimeClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )


def _submit_and_settle(
    client: RuntimeFrontendClient, profile_id: UUID
) -> tuple[OperationId, int, ContentDigest, OperationSchemaIdentityV1]:
    """Use the real registered contract and wait for the durable terminal receipt."""
    deadline = time.monotonic() + 60
    contract = client.operation(
        RuntimeOperationContract(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=client.session_id,
            definition_id=WORKBENCH_GENERATION_OPERATION_DEFINITION_ID,
        ),
        deadline=deadline,
    )
    assert isinstance(contract, RuntimeOperationContractReply)
    schema = contract.contract.result_schema
    assert schema is not None
    submitted = client.operation(
        RuntimeOperationSubmit(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=client.session_id,
            definition_id=WORKBENCH_GENERATION_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
            payload_json=WorkbenchGenerationOperationRequest(
                profile_id=profile_id, output_language=OutputLanguage.ES
            ).model_dump_json(),
        ),
        deadline=deadline,
    )
    assert isinstance(submitted, RuntimeOperationSubmitted)
    operation_id = submitted.receipt.operation_id
    started = client.operation(
        RuntimeOperationControl(
            action="operation_start",
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=client.session_id,
            operation_id=operation_id,
        ),
        deadline=deadline,
    )
    assert isinstance(started, RuntimeOperationAcknowledged)
    while True:
        observed = client.operation(
            RuntimeOperationObserve(
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=client.session_id,
                observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32),
            ),
            deadline=deadline,
        )
        assert isinstance(observed, RuntimeOperationObserved)
        assert isinstance(observed.observation, OperationObservationSuccessV1)
        projection = observed.observation.projection
        if projection.terminal_condition is not None:
            assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
            return operation_id, projection.revision, contract.contract.definition_contract_digest, schema
        assert time.monotonic() < deadline
        time.sleep(0.02)


async def _verify_from_installed_workspace(
    actions: ModeloWorkspaceLifecycleDoor,
    client: RuntimeFrontendClient,
    profile_id: UUID,
    work_unit_id: str,
) -> tuple[RuntimeOperationController, OperationPublicProjectionV1, ModeloWorkVerifyPublicResultV2]:
    """Submit and read one verification through the installed workspace door."""
    controller = await actions.verify()
    assert isinstance(controller, RuntimeOperationController)
    assert controller.client is client
    assert controller.session_id == client.session_id
    assert client.profile_id == profile_id
    deadline = time.monotonic() + 60
    while True:
        observation = await controller.observe(0, page_limit=32)
        assert isinstance(observation, OperationObservationSuccessV1)
        projection = observation.projection
        assert projection.operation_id == controller.operation_id
        assert projection.definition_id == MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID
        assert projection.subject_ref == work_unit_id
        if projection.lifecycle is OperationLifecycle.TERMINAL:
            break
        assert time.monotonic() < deadline
        await asyncio.sleep(0.02)
    assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert projection.effect is OperationEffect.UPDATED
    result = await controller.read_settled_result(projection, ModeloWorkVerifyPublicResultV2, result_version=2)
    return controller, projection, result


def _require_runtime_app(value: object) -> CadrumoTuiApp:
    assert isinstance(value, CadrumoTuiApp)
    return value


def test_in_process_secure_generation_captures_the_seeded_profile(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Expose application capture exceptions directly, without the worker envelope."""
    with administration_subject(tmp_path, os_owner_id=owner_id()) as subject:
        profile_id = subject.store.binding.profile_id
        calculation_revision_id = seeded_modelo_calculation_revision(profile_id, operation=operation)
        calculation = CalculationRevisionCatalogueRepository().load().get(calculation_revision_id)
        assert calculation is not None
        work_unit = WorkUnitCatalogueRepository().load().get(calculation.work_unit_id)
        assert work_unit is not None

        account_session = HomeAccountSession(
            posture=HomeSessionPosture.ACTIVE,
            profile_label="Enrollment tests",
        )
        registry = build_production_operation_registry()
        provider = compose_secure_workbench_generation_provider(
            profile_id=str(profile_id),
            operation=operation,
            operation_contracts=registry.public_contract_set,
            account_session_reader=lambda: account_session,
        )
        with override_settings(cadrumo_output_language=OutputLanguage.ES.value):
            generation = provider()

        projection = project_workbench_generation(profile_id, generation)
        projection_bytes = canonical_json_bytes(projection.model_dump(mode="json", serialize_as_any=True))
        parsed_projection = WorkbenchGenerationOperationProjection.model_validate_json(projection_bytes)
        restored_generation = restore_workbench_generation(parsed_projection)
        assert project_workbench_generation(profile_id, restored_generation) == projection
        assert restored_generation.search.availability == generation.search.availability
        if generation.search.availability is WorkbenchGenerationAvailability.AVAILABLE:
            assert restored_generation.search.projection is not None

        public_declarations = parsed_projection.generation.declarations.projection
        assert public_declarations is not None
        tampered_declarations = parsed_projection.generation.declarations.model_copy(
            update={"projection": public_declarations.model_copy(update={"bucket_id": str(uuid4())})}
        )
        tampered_generation = parsed_projection.generation.model_copy(update={"declarations": tampered_declarations})
        tampered_projection = parsed_projection.model_copy(update={"generation": tampered_generation})
        with pytest.raises(ValidationError, match="workbench projection profile mismatch"):
            WorkbenchGenerationOperationProjection.model_validate_json(
                canonical_json_bytes(tampered_projection.model_dump(mode="json", serialize_as_any=True))
            )

        contract = registry.lookup_public_contract(WORKBENCH_GENERATION_OPERATION_DEFINITION_ID)
        result_schema = contract.result_schema
        assert result_schema is not None
        document = OperationResultProjectionSuccessV1[WorkbenchGenerationOperationProjection](
            result_schema=result_schema,
            definition_contract_digest=contract.definition_contract_digest,
            projection=projection,
        )
        document_bytes = canonical_json_bytes(document.model_dump(mode="json", serialize_as_any=True))
        assert len(document_bytes) <= PROJECTION_DOCUMENT_MAX_BYTES
        parsed_document = OperationResultProjectionSuccessV1[
            WorkbenchGenerationOperationProjection
        ].model_validate_json(document_bytes)
        assert parsed_document == document
        assert restore_workbench_generation(parsed_document.projection) == restored_generation

    assert generation.contract_version == 1
    assert generation.home.projection is not None
    declarations = generation.declarations.projection
    assert declarations is not None
    assert declarations.bucket_id == str(profile_id)
    assert any(row.work_unit_id == work_unit.work_unit_id for row in declarations.declarations)
    assert declarations.creation_targets


def test_native_human_generation_is_exact_profile_and_key_cannot_submit_or_read(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
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
        requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
        subject.owner.requesting = requester
        subject.owner.delivery.endpoint = NativeEnrollmentRecipient(
            requester=requester, secrets_store=subject.client_native
        )
        calculation_revision_id = seeded_modelo_calculation_revision(
            subject.store.binding.profile_id, operation=operation
        )
        calculation = CalculationRevisionCatalogueRepository().load().get(calculation_revision_id)
        assert calculation is not None
        work_unit = WorkUnitCatalogueRepository().load().get(calculation.work_unit_id)
        assert work_unit is not None
        work_unit_id = work_unit.work_unit_id
        profile_id = subject.store.binding.profile_id
        operation_ids = frozenset(
            {WORKBENCH_GENERATION_OPERATION_DEFINITION_ID, MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID}
        )
        registry = build_production_operation_registry()
        disclosures = {
            DisclosurePermission(
                destination_id=requester.client_id,
                projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                category=DisclosureCategory.OPERATION_METADATA,
            )
        }
        for definition_id in operation_ids:
            result_schema = registry.lookup_public_contract(definition_id).result_schema
            assert result_schema is not None
            categories = (
                (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
                if definition_id == WORKBENCH_GENERATION_OPERATION_DEFINITION_ID
                else (DisclosureCategory.TAX_VALUES,)
            )
            disclosures.update(
                DisclosurePermission(
                    destination_id=requester.client_id,
                    projection_id=result_schema.schema_id,
                    category=category,
                )
                for category in categories
            )
        scope = changed(
            subject.proposal.scope,
            operations=operation_ids,
            actions=frozenset(
                {
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.COMMIT,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                }
            ),
            disclosures=frozenset(disclosures),
            periods=frozenset({work_unit.period}),
            allow_period_independent=True,
        )
        facts = subject.owner.current
        assert facts.session is not None
        subject.owner.current = changed(
            facts, profile=changed(facts.profile, scope=scope), session=changed(facts.session, scope=scope)
        )
        subject.proposal = changed(subject.proposal, scope=scope)
        enrollment_request = uuid4()
        subject.service.request(enrollment_request, subject.proposal)
        subject.approve(enrollment_request)
        record = subject.store.enrollment_state().requests[0]
        possession = subject.owner.delivery.endpoint.possession(record)
        assert possession is not None
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
        # The installed runtime validates the operation graph before listening.
        profiles.prepare_registry()
        server = RuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                with ExitStack() as cleanup:
                    human_raw, api_raw, second_raw, mcp_raw = (
                        _connect(endpoint),
                        _connect(endpoint),
                        _connect(endpoint),
                        _connect(endpoint),
                    )
                    human = RuntimeFrontendClient(
                        human_raw, profile_id=profile_id, frontend=OperationFrontendProjection.TUI
                    )
                    api = RuntimeFrontendClient(
                        api_raw, profile_id=profile_id, frontend=OperationFrontendProjection.TUI
                    )
                    second = RuntimeFrontendClient(
                        second_raw, profile_id=profile_id, frontend=OperationFrontendProjection.TUI
                    )
                    mcp = RuntimeFrontendClient(
                        mcp_raw, profile_id=profile_id, frontend=OperationFrontendProjection.MCP
                    )
                    cleanup.callback(human.close)
                    cleanup.callback(api.close)
                    cleanup.callback(second.close)
                    cleanup.callback(mcp.close)
                    password = bytearray(PROFILE_INPUT.encode())
                    human.login_password(password)
                    assert not any(password)
                    key = bytearray(possession.get_secret_value())
                    api.login_api_key(key)
                    assert not any(key)
                    second_password = bytearray(PROFILE_INPUT.encode())
                    second.login_password(second_password)
                    assert not any(second_password)
                    mcp_key = bytearray(possession.get_secret_value())
                    mcp.login_api_key(mcp_key)
                    assert not any(mcp_key)

                    mcp_contract = mcp_raw.operation(
                        RuntimeOperationContract(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=mcp.session_id,
                            definition_id=WORKBENCH_GENERATION_OPERATION_DEFINITION_ID,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(mcp_contract, RuntimeAccessRefusal)
                    assert mcp_contract.code is AccessDenialCode.FRONTEND_DENIED

                    foreign = uuid4()
                    wrong = human_raw.operation(
                        RuntimeOperationSubmit(
                            request_id=uuid4(),
                            profile_id=foreign,
                            session_id=human.session_id,
                            definition_id=WORKBENCH_GENERATION_OPERATION_DEFINITION_ID,
                            subject_ref=profile_operation_subject(str(foreign)),
                            payload_json=WorkbenchGenerationOperationRequest(
                                profile_id=foreign, output_language=OutputLanguage.ES
                            ).model_dump_json(),
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(wrong, RuntimeAccessRefusal)
                    assert wrong.code is AccessDenialCode.PROFILE_MISMATCH

                    api_denied = api_raw.operation(
                        RuntimeOperationSubmit(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=api.session_id,
                            definition_id=WORKBENCH_GENERATION_OPERATION_DEFINITION_ID,
                            subject_ref=profile_operation_subject(str(profile_id)),
                            payload_json=WorkbenchGenerationOperationRequest(
                                profile_id=profile_id, output_language=OutputLanguage.ES
                            ).model_dump_json(),
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(api_denied, RuntimeAccessRefusal)
                    assert api_denied.code is AccessDenialCode.HUMAN_AUTHORITY_REQUIRED

                    operation_id, revision, digest, schema = _submit_and_settle(human, profile_id)
                    result = OperationResultProjectionRequestV1(
                        operation_id=operation_id,
                        terminal_revision=revision,
                        definition_contract_digest=digest,
                        result_schema=schema,
                    )
                    owner_page = RuntimeOperationResultPage(
                        request_id=uuid4(),
                        profile_id=profile_id,
                        session_id=human.session_id,
                        result=result,
                        page=ProjectionPageRequest(),
                    )
                    original = human_raw.operation(owner_page, deadline=time.monotonic() + 5)
                    assert isinstance(original, RuntimeOperationPage)
                    assert original.operation_id == operation_id
                    document = human.read_result_document(result, timeout=30)
                    decoded = OperationResultProjectionSuccessV1[
                        WorkbenchGenerationOperationProjection
                    ].model_validate_json(canonical_json_bytes(document))
                    assert restore_workbench_generation(decoded.projection).contract_version == 1
                    fresh_observe = RuntimeOperationObserve(
                        request_id=uuid4(),
                        profile_id=profile_id,
                        session_id=second.session_id,
                        observation=OperationObservationRequestV1(
                            operation_id=operation_id, after_cursor=0, page_limit=32
                        ),
                    )
                    fresh_observed = second_raw.operation(fresh_observe, deadline=time.monotonic() + 5)
                    assert isinstance(fresh_observed, RuntimeOperationObserved)
                    assert isinstance(fresh_observed.observation, OperationObservationSuccessV1)
                    assert fresh_observed.observation.projection.revision == revision
                    assert (
                        fresh_observed.observation.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    )
                    mcp_observed = mcp_raw.operation(
                        changed(fresh_observe, request_id=uuid4(), session_id=mcp.session_id),
                        deadline=time.monotonic() + 5,
                    )
                    # The key-authenticated MCP session is neither human nor on a
                    # declared frontend; either refusal keeps the operation private.
                    assert isinstance(mcp_observed, RuntimeAccessRefusal)
                    assert mcp_observed.code in {
                        AccessDenialCode.HUMAN_AUTHORITY_REQUIRED,
                        AccessDenialCode.FRONTEND_DENIED,
                    }
                    other = second_raw.operation(
                        changed(owner_page, request_id=uuid4(), session_id=second.session_id),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(other, RuntimeAccessRefusal)
                    assert other.code is AccessDenialCode.OPERATION_DENIED
                    api_result = api_raw.operation(
                        RuntimeOperationResultPage(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=api.session_id,
                            result=result,
                            page=ProjectionPageRequest(),
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(api_result, RuntimeAccessRefusal)
                    assert api_result.code is AccessDenialCode.HUMAN_AUTHORITY_REQUIRED
                    generation = read_workbench_generation(human, output_language=OutputLanguage.ES, timeout=60)
                    assert generation.contract_version == 1
                    assert generation.home.projection is not None
                    assert generation.home.projection.account.profile_label == "Enrollment tests"
                    assert generation.home.projection.account.expires_at is not None
                    assert generation.ledger_admission.destination == "workbench.ledger"
                    assert generation.declarations_admission.destination == "workbench.declarations"
                    assert generation.aeat_sync_admission.destination == "workbench.aeat_sync"
                    native_declarations = generation.declarations.projection
                    assert native_declarations is not None
                    assert native_declarations.bucket_id == str(profile_id)
                    assert any(row.work_unit_id == work_unit_id for row in native_declarations.declarations)

                    generation_projection = project_workbench_generation(profile_id, generation)
                    generation_wire = canonical_json_bytes(generation_projection.model_dump(mode="json"))
                    generation_roundtrip = WorkbenchGenerationOperationProjection.model_validate_json(generation_wire)
                    restored_generation = restore_workbench_generation(generation_roundtrip)
                    assert project_workbench_generation(profile_id, restored_generation) == generation_projection
                    generation_document = OperationResultProjectionSuccessV1[WorkbenchGenerationOperationProjection](
                        result_schema=schema,
                        definition_contract_digest=digest,
                        projection=generation_projection,
                    )
                    generation_document_bytes = canonical_json_bytes(generation_document.model_dump(mode="json"))
                    assert len(generation_document_bytes) <= PROJECTION_DOCUMENT_MAX_BYTES
                    logging.getLogger(__name__).info(
                        "native workbench generation: %d canonical bytes", len(generation_document_bytes)
                    )

                    async def reject_recovery() -> RuntimeFrontendClient:
                        raise AssertionError("workbench capture must not open profile recovery")

                    root = RuntimeWorkbenchRoot(
                        human,
                        profile_label="Enrollment tests",
                        output_language=OutputLanguage.ES,
                        open_recovery_client=reject_recovery,
                    )
                    api_root = RuntimeWorkbenchRoot(
                        api,
                        profile_label="Enrollment tests",
                        output_language=OutputLanguage.ES,
                        open_recovery_client=reject_recovery,
                    )
                    with ThreadPoolExecutor(max_workers=1) as reader:
                        binding = reader.submit(root.load).result(timeout=90)
                        presented = reader.submit(binding.refresh_home).result(timeout=5)
                        assert isinstance(presented, RootPresentationV1)
                        assert presented.destination_catalogue is binding.destination_catalogue
                        assert presented.workbench_search_service is binding.workbench_search_service
                        assert presented.account_factories is binding.account_factories
                        assert presented.home.account.profile_label == "Enrollment tests"
                        route = presented.destination_catalogue.resolve("workbench.profile")
                        assert route.admission.state is WorkbenchDestinationAdmissionState.AVAILABLE
                        screen = presented.destination_catalogue.create_screen(
                            TuiNavigationTargetV1(
                                destination="workbench.profile",
                                focus=TuiFocusIdentityV1(
                                    destination="workbench.profile", semantic_key="profile.overview"
                                ),
                            )
                        )
                        assert isinstance(screen, ProfileManagerScreen)
                        assert screen.overview.profile_id == str(profile_id)
                        account_screen = presented.account_factories.profile(
                            TuiScreenContextV1(destination="workbench.profile")
                        )
                        assert account_screen.overview.content_digest == screen.overview.content_digest
                        declarations_screen = presented.destination_catalogue.create_screen(
                            TuiNavigationTargetV1(
                                destination="workbench.declarations",
                                focus=TuiFocusIdentityV1(
                                    destination="workbench.declarations",
                                    semantic_key="declarations.work",
                                    restore_token=work_unit_id,
                                ),
                            )
                        )
                        assert isinstance(declarations_screen, DeclarationsOverviewScreen)
                        declaration = next(
                            item
                            for item in declarations_screen.controller.projection.declarations
                            if item.work_unit_id == work_unit_id
                        )
                        workspace_screen = declarations_screen.controller.modelo_workspace_factory
                        assert workspace_screen is not None
                        opened_workspace = workspace_screen(declaration)
                        assert isinstance(opened_workspace, ModeloWorkbenchScreen)
                        workbench = opened_workspace._reader
                        assert isinstance(workbench, InstalledModeloWorkbench)
                        # The form, its edit baseline and the facts the actions need are read by
                        # the worker's registered operation over this human session.
                        loaded = reader.submit(workbench.load, OutputLanguage.ES).result(timeout=90)
                        assert loaded.form.work_unit_id == work_unit_id
                        assert loaded.form.calculation_revision_id == calculation_revision_id
                        assert workbench.edit_refusal() is None
                        card_box = loaded.form.result_addresses[0] if loaded.form.result_addresses else None
                        if card_box is not None:
                            card = reader.submit(workbench.help_card, card_box, OutputLanguage.ES).result(timeout=90)
                            assert card.casilla_id == card_box
                        actions = workbench._door()
                        assert isinstance(actions, ModeloWorkspaceLifecycleDoor)
                        assert actions.work_unit_id == work_unit_id
                        assert actions.calculation_revision_id == calculation_revision_id
                        assert actions.verification_report_id is None
                        assert actions.asks_modelo_390 is False
                        assert callable(actions.refresh_after_success)

                        _, terminal, verification = asyncio.run(
                            _verify_from_installed_workspace(actions, human, profile_id, work_unit_id)
                        )
                        assert terminal.effect is OperationEffect.UPDATED
                        assert verification.verification_report_id
                        assert verification.calculation_revision_id == calculation_revision_id
                        assert verification.verification.report.verification_report_id == (
                            verification.verification_report_id
                        )
                        assert verification.verification.report.calculation_revision_id == calculation_revision_id
                        assert verification.verification.published
                        refresh = actions.refresh_after_success
                        assert callable(refresh)

                        captured = reader.submit(refresh).result(timeout=90)
                        assert isinstance(captured, WorkbenchGenerationV1)
                        assert declarations_screen.controller.refresh_from_capture()
                        reread = reader.submit(workbench.load, OutputLanguage.ES).result(timeout=90)
                        assert reread.form.calculation_revision_id == calculation_revision_id
                        refreshed_actions = workbench._door()
                        assert refreshed_actions.calculation_revision_id == calculation_revision_id
                        assert refreshed_actions.verification_report_id == verification.verification_report_id
                        with pytest.raises(RuntimeFrontendRefusedError) as api_root_denied:
                            reader.submit(api_root.load).result(timeout=90)
                        assert api_root_denied.value.reason == AccessDenialCode.HUMAN_AUTHORITY_REQUIRED.value

                    async def inspect_root(pilot: Pilot[object]) -> None:
                        app = _require_runtime_app(pilot.app)
                        async with asyncio.timeout(90):
                            while app.account_session is None:
                                await pilot.pause(0.05)
                        assert app.account_session.profile_label == "Enrollment tests"
                        assert (
                            app.destination_catalogue.resolve("workbench.profile").admission.state
                            is WorkbenchDestinationAdmissionState.AVAILABLE
                        )
                        assert not hasattr(app, "services")
                        app.exit()

                    assert (
                        asyncio.run(
                            run_precomposed_runtime_root_session(
                                load_root=lambda: binding, headless=True, auto_pilot=inspect_root
                            )
                        )
                        is None
                    )

                    original_session = human.session_id
                    locked = human.lock()
                    assert original_session in locked.session_ids
                    with ThreadPoolExecutor(max_workers=1) as reader, pytest.raises(AccountSessionExpiredError):
                        reader.submit(root.load).result(timeout=5)
                    retired = human_raw.operation(
                        changed(owner_page, request_id=uuid4()), deadline=time.monotonic() + 5
                    )
                    assert isinstance(retired, RuntimeAccessRefusal)
                    repeated_other = second_raw.operation(
                        changed(owner_page, request_id=uuid4(), session_id=second.session_id),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(repeated_other, RuntimeAccessRefusal)
                    assert repeated_other.code is AccessDenialCode.OPERATION_DENIED
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    try:
                        running.result(timeout=20)
                    except Exception:
                        if primary is None:
                            raise
                finally:
                    endpoint.close()


def test_installed_launcher_owns_human_and_api_sessions_without_local_custody(tmp_path: Path) -> None:
    """The default launcher logs in through native IPC, then recomposes fresh roots."""
    storage_root = tmp_path / "cadrumo-storage"
    storage_root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=storage_root)
    installation = runtime_installation(
        storage_root=storage_root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
        subject.owner.requesting = requester
        subject.owner.delivery.endpoint = NativeEnrollmentRecipient(
            requester=requester, secrets_store=subject.client_native
        )
        enrollment_request = uuid4()
        subject.service.request(enrollment_request, subject.proposal)
        subject.approve(enrollment_request)
        record = subject.store.enrollment_state().requests[0]
        possession = subject.owner.delivery.endpoint.possession(record)
        assert possession is not None
        profile_id = subject.store.binding.profile_id
        close_active_bucket_session()

        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=storage_root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: subject.native,
        )
        # The installed runtime validates the operation graph before listening.
        profiles.prepare_registry()
        server = RuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        stages: list[str] = []
        seen_session_ids: list[UUID] = []
        observer: RuntimeFrontendClient

        async def launched_session(*, kind: SessionKind) -> UUID:
            sessions = await asyncio.to_thread(observer.sessions)
            others = tuple(session for session in sessions if session.session_id != observer.session_id)
            assert len(others) == 1
            assert others[0].profile_id == profile_id
            assert others[0].kind is kind
            assert others[0].session_id not in seen_session_ids
            seen_session_ids.append(others[0].session_id)
            return others[0].session_id

        async def drive(pilot: Pilot[object]) -> None:
            app: object = pilot.app
            assert current_active_bucket_session() is None
            if isinstance(app, CadrumoTuiApp):
                root_app = _require_runtime_app(pilot.app)
                async with asyncio.timeout(90):
                    while root_app.account_session is None:
                        await pilot.pause(0.05)
                assert root_app.account_session.profile_label == "Enrollment tests"
                assert (
                    root_app.destination_catalogue.resolve("workbench.profile").admission.state
                    is WorkbenchDestinationAdmissionState.AVAILABLE
                )
                assert not hasattr(root_app, "services")
                await launched_session(kind=SessionKind.HUMAN)
                if "root-change-user" not in stages:
                    stages.append("root-change-user")
                    root_app.run_account_action(AccountActionV1.CHANGE_USER)
                else:
                    stages.append("root-close")
                    root_app.exit()
                return
            if isinstance(app, RuntimeRestrictedSessionApp):
                async with asyncio.timeout(30):
                    while str(profile_id) not in str(app.query_one("#restricted-profile", Static).render()):
                        await pilot.pause(0.05)
                assert not hasattr(app, "services")
                await launched_session(kind=SessionKind.API_KEY)
                stages.append("restricted-change-user")
                await pilot.click("#restricted-change-user")
                return

            screen = pilot.app.screen
            assert isinstance(screen, RuntimeLoginScreen)
            method = (
                RuntimeLoginMethod.API_KEY
                if "root-change-user" in stages and "restricted-change-user" not in stages
                else RuntimeLoginMethod.PASSWORD
            )
            stages.append(f"login-{method.value}")
            selected = cast("Select[RuntimeLoginMethod]", screen.query_one("#runtime-login-method", Select))
            selected.value = method
            await pilot.pause()
            credential = screen.query_one("#runtime-login-credential", Input)
            assert credential.password
            credential.value = (
                possession.get_secret_value().decode("utf-8") if method is RuntimeLoginMethod.API_KEY else PROFILE_INPUT
            )
            await pilot.click("#runtime-login-submit")
            assert credential.value == ""

        with override_settings(cadrumo_local_storage_root=storage_root), ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                with ExitStack() as cleanup:
                    observer = RuntimeFrontendClient(
                        _connect(endpoint), profile_id=profile_id, frontend=OperationFrontendProjection.TUI
                    )
                    cleanup.callback(observer.close)
                    observer_password = bytearray(PROFILE_INPUT.encode())
                    observer.login_password(observer_password)
                    assert not any(observer_password)
                    assert main(headless=True, auto_pilot=drive) == 0
                    assert stages == [
                        "login-password",
                        "root-change-user",
                        "login-api_key",
                        "restricted-change-user",
                        "login-password",
                        "root-close",
                    ]
                    assert len(seen_session_ids) == len(set(seen_session_ids)) == 3
                    # Client close and the server's verified EOF/disconnect run on
                    # different threads; wait only for that bounded cleanup.
                    deadline = time.monotonic() + 5
                    while True:
                        remaining = {session.session_id for session in observer.sessions()}
                        if remaining == {observer.session_id} or time.monotonic() >= deadline:
                            break
                        time.sleep(0.02)
                    assert remaining == {observer.session_id}
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    try:
                        running.result(timeout=20)
                    except Exception:
                        if primary is None:
                            raise
                finally:
                    endpoint.close()

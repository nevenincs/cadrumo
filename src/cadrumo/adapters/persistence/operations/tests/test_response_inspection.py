"""Capability-bound REVIEW inspection leaves the real response bearer intact."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

import pytest

from cadrumo.adapters.outbound.aeat.browser.factory import default_browser_session_factory
from cadrumo.adapters.outbound.aeat.sede.censal_datos import fetch_censal_datos
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.application.operations.composition import compose_operation_services
from cadrumo.application.operations.frontend_requests import (
    OperationResponseApplyRequestV1,
    OperationResponseControlRefusalV1,
    OperationResponseControlRequestV1,
    OperationResponseControlSuccessV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.projection_services import OperationResponseAuthorityBroker
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.user_profile.censal_operation import (
    CensalOperationRequest,
    build_censal_operation_definition,
    build_censal_operation_registration,
)
from cadrumo.core.operations import OperationEffect, OperationLifecycle

from .supervision_support import run_to_settlement
from .test_censal_operation_executor import (
    _OPERATOR_SCOPE_PORTS,
    NOW,
    _observation,
    _scoped_authority_operation,
    censal_request_payload,
    subject,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter, pytest.mark.usefixtures("operation")]


@pytest.mark.parametrize("response_action", ["apply", "reject"])
def test_inspect_then_respond_uses_one_original_censal_capability(tmp_path: Path, response_action: str) -> None:
    with subject(tmp_path) as (profile_id, objects, _session):
        root = tmp_path / "operations"

        async def acquire():
            return _observation()

        definition = build_censal_operation_definition(
            certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
            browser_session_factory=default_browser_session_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            censal_fetch_port=fetch_censal_datos,
            acquire=acquire,
        )
        registry = OperationRegistry(
            definitions=(definition,),
            public_registrations=(build_censal_operation_registration(definition),),
        )
        journal = OperationJournalRepository(storage_root=root)
        services = compose_operation_services(
            registry=registry,
            authority_operation=_scoped_authority_operation(),
            journal=journal,
            reader=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=root),
            operands=operation_secure_reference_repository(objects=objects),
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: NOW,
            lease_duration=timedelta(minutes=1),
            execution_timeout=timedelta(minutes=5),
            cleanup_timeout=timedelta(minutes=1),
        )
        request = OperationRequest[CensalOperationRequest](
            definition_id=definition.definition_id,
            subject_ref=profile_id,
            payload=censal_request_payload(profile_id),
        )

        async def run() -> None:
            submission = await services.submission.submit(request, actor_ref="operator:reviewer")
            capability = submission.response_capability
            assert capability is not None
            operation_id = submission.receipt.operation_id
            waiting = await run_to_settlement(services.submission.supervisor, operation_id)
            assert waiting.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
            pending = waiting.pending_interaction
            assert pending is not None
            control = OperationResponseControlRequestV1(
                operation_id=operation_id,
                interaction_id=pending.request.interaction_id,
                revision=pending.request.revision,
                actor_ref="operator:reviewer",
            )

            no_bearer = await services.inspect_response(control, None)
            assert isinstance(await no_bearer.inspect(control), OperationResponseControlRefusalV1)

            forged = OperationResponseAuthorityBroker().reserve(operation_id, "operator:reviewer")
            wrong = await services.inspect_response(control, forged)
            assert isinstance(await wrong.inspect(control), OperationResponseControlRefusalV1)
            forged.close()
            assert isinstance(
                await (await services.inspect_response(control, capability)).inspect(
                    control.model_copy(update={"actor_ref": "operator:intruder"})
                ),
                OperationResponseControlRefusalV1,
            )
            assert isinstance(
                await (await services.inspect_response(control, capability)).inspect(
                    control.model_copy(update={"revision": control.revision + 1})
                ),
                OperationResponseControlRefusalV1,
            )
            with pytest.raises(ValueError, match="response authority is unavailable"):
                services._response_broker.inspect(
                    control,
                    pending.model_copy(update={"reviewed_proposal_digest": "0" * 64}),
                    capability,
                    clock=lambda: NOW,
                )

            inspector = await services.inspect_response(control, capability)
            inspected = await inspector.inspect(control)
            assert isinstance(inspected, OperationResponseControlSuccessV1)
            assert inspected.permitted_intents == frozenset({"apply", "reject"})
            assert isinstance(await inspector.inspect(control), OperationResponseControlSuccessV1)

            mutation = (
                OperationResponseApplyRequestV1(**control.model_dump(), responded_at=NOW)
                if response_action == "apply"
                else OperationResponseRejectRequestV1(**control.model_dump(), responded_at=NOW)
            )
            responder = await services.response(mutation, capability)
            if isinstance(mutation, OperationResponseApplyRequestV1):
                result = await responder.apply(mutation)
            else:
                result = await responder.reject(mutation)
            assert isinstance(result, OperationResponseMutationSuccessV1)
            assert result.response_action == response_action
            settled = await services.submission.supervisor.await_terminal(operation_id)
            assert settled.effect is (OperationEffect.UPDATED if response_action == "apply" else OperationEffect.NONE)

            replay = await services.response(mutation, capability)
            if isinstance(mutation, OperationResponseApplyRequestV1):
                replayed = await replay.apply(mutation)
            else:
                replayed = await replay.reject(mutation)
            assert isinstance(replayed, OperationResponseControlRefusalV1)
            assert isinstance(await inspector.inspect(control), OperationResponseControlRefusalV1)
            await services.shutdown()

        asyncio.run(run())

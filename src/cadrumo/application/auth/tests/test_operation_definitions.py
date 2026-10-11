"""Auth operation-definition registry contract tests."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.application.auth.operation_definitions import (
    AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
    AUTH_LOGOUT_OPERATION_DEFINITION_ID,
    AUTH_RESET_OPERATION_DEFINITION_ID,
    AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
    PROFILE_ROTATION_OPERATION_DEFINITION_ID,
    AuthOperationPorts,
    AuthTeardownOperationRequest,
    build_auth_operation_definitions,
    build_auth_operation_registrations,
)
from cadrumo.application.auth.protocols import BrowserSessionPort
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.capabilities import OperationRequestStoragePolicy
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.config import Settings
from cadrumo.core.operations import profile_operation_subject

from ._operator_probe_fakes import fake_operator_probe_ports
from ._operator_scope_fakes import build_inward_operator_scope_ports
from .certificate_secret_fakes import InMemoryCertificateSecretBackendFactory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


async def _unopened_browser_session(settings: Settings) -> BrowserSessionPort:
    """The registry shape is inspected here; no executor ever opens a browser."""
    del settings
    raise AssertionError("registry-shape tests never open a browser session")


AUTH_DEFINITIONS = build_auth_operation_definitions(
    ports=AuthOperationPorts(
        certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
        browser_session_factory=_unopened_browser_session,
        operator_probe_ports=fake_operator_probe_ports(),
        operator_scope_ports=build_inward_operator_scope_ports(session=None),
    ),
)


def test_auth_families_have_one_canonical_registered_operation_each() -> None:
    registry = OperationRegistry(definitions=AUTH_DEFINITIONS)
    definition_ids = tuple(definition.definition_id for definition in AUTH_DEFINITIONS)
    assert definition_ids == (
        AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
        AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
        AUTH_LOGOUT_OPERATION_DEFINITION_ID,
        AUTH_RESET_OPERATION_DEFINITION_ID,
        PROFILE_ROTATION_OPERATION_DEFINITION_ID,
    )
    assert len(set(definition_ids)) == len(definition_ids)
    assert {
        definition_id
        for definition_id in definition_ids
        if registry.lookup(definition_id).capabilities.request_storage
        is OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL
    } == set()
    assert all(
        registry.lookup(definition_id).capabilities.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
        for definition_id in (
            AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
            AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
            AUTH_LOGOUT_OPERATION_DEFINITION_ID,
            AUTH_RESET_OPERATION_DEFINITION_ID,
            PROFILE_ROTATION_OPERATION_DEFINITION_ID,
        )
    )
    assert "auth.profile.login" not in definition_ids
    assert registry.lookup(PROFILE_ROTATION_OPERATION_DEFINITION_ID).ephemeral_secret is not None
    assert all(
        registry.lookup(definition_id).ephemeral_secret is None
        for definition_id in (
            AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
            AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
            AUTH_LOGOUT_OPERATION_DEFINITION_ID,
            AUTH_RESET_OPERATION_DEFINITION_ID,
        )
    )


_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000c1")
_DESTINATION = UUID("5aa00000-0000-4000-8000-0000000000c2")
_TEARDOWN_DEFINITIONS = (AUTH_LOGOUT_OPERATION_DEFINITION_ID, AUTH_RESET_OPERATION_DEFINITION_ID)
_TEARDOWN_ACCESSES = (AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT, AccessAction.OBSERVE)


def _teardown_registry() -> OperationRegistry:
    return OperationRegistry(
        definitions=AUTH_DEFINITIONS,
        public_registrations=build_auth_operation_registrations(AUTH_DEFINITIONS),
    )


@pytest.mark.parametrize("access", _TEARDOWN_ACCESSES)
@pytest.mark.parametrize("definition_id", _TEARDOWN_DEFINITIONS)
def test_teardown_resolves_the_same_access_on_every_frontend(definition_id: str, access: AccessAction) -> None:
    registry = _teardown_registry()
    request = OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=AuthTeardownOperationRequest(),
    )

    resolved = {
        frontend: resolve_operation_access(
            registry=registry,
            request=request,
            context=OperationAccessContext(
                profile_id=_PROFILE,
                destination_id=_DESTINATION,
                action=access,
                frontend=frontend,
                contract=registry.lookup_public_contract(definition_id),
                published_authority=Availability.AVAILABLE,
            ),
        )
        for frontend in OperationFrontendProjection
    }

    for frontend, admitted in resolved.items():
        assert admitted.request.frontend is frontend
        assert admitted.request.definition_id == definition_id
        assert AccessAction.COMMIT in admitted.policy.actions
        assert admitted.policy == resolved[OperationFrontendProjection.CLI].policy


def test_teardown_refuses_a_request_resolved_under_the_other_definitions_contract() -> None:
    """Reset cannot be resolved under the contract logout registered."""
    registry = _teardown_registry()
    request = OperationRequest[BaseModel](
        definition_id=AUTH_RESET_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=AuthTeardownOperationRequest(),
    )
    registration = registry.lookup_public_registration(AUTH_RESET_OPERATION_DEFINITION_ID)
    assert registration.access_resolver is not None
    borrowed = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=_DESTINATION,
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.MCP,
        contract=registry.lookup_public_contract(AUTH_LOGOUT_OPERATION_DEFINITION_ID),
        published_authority=Availability.AVAILABLE,
    )

    with pytest.raises(ProfileAccessRefusedError) as refused:
        registration.access_resolver(request, borrowed)

    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE

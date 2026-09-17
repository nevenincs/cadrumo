"""Auth operation-definition registry contract tests."""

from __future__ import annotations

import pytest

from cadrumo.application.auth.operation_definitions import (
    AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
    AUTH_LOGOUT_OPERATION_DEFINITION_ID,
    AUTH_RESET_OPERATION_DEFINITION_ID,
    AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
    PROFILE_LOGIN_OPERATION_DEFINITION_ID,
    PROFILE_ROTATION_OPERATION_DEFINITION_ID,
    AuthOperationPorts,
    build_auth_operation_definitions,
)
from cadrumo.application.auth.protocols import BrowserSessionPort
from cadrumo.application.operations.capabilities import OperationRequestStoragePolicy
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.core.config import Settings

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
        PROFILE_LOGIN_OPERATION_DEFINITION_ID,
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
    } == {
        PROFILE_LOGIN_OPERATION_DEFINITION_ID,
    }
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
    assert registry.lookup(PROFILE_LOGIN_OPERATION_DEFINITION_ID).ephemeral_secret is not None
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

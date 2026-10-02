"""Registered apoderado request custody, projection, and canonical prewrite rules."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....core.operations import OperationEffect
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ..apoderado_operation import (
    APODERADO_CHECK_OPERATION_DEFINITION_ID,
    APODERADO_CONFIGURE_OPERATION_DEFINITION_ID,
    APODERADO_REPRESENTED_NIF_SECRET_KIND,
    APODERADO_STATUS_OPERATION_DEFINITION_ID,
    ApoderadoConfigureRequest,
    ApoderadoOperationPorts,
    ApoderadoOperationProjection,
    ApoderadoStatusSnapshot,
    build_apoderado_operation_definitions,
    build_apoderado_operation_registrations,
)
from ..apoderado_service import ApoderadoStatus

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("3a3a3a3a-3a3a-4a3a-8a3a-3a3a3a3a3a3a")
_OTHER = UUID("4b4b4b4b-4b4b-4b4b-8b4b-4b4b4b4b4b4b")


def _unused_factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ApoderadoOperationPorts:
    raise AssertionError(f"unexpected execution for {bucket_id}")


def test_apoderado_definitions_bind_the_real_public_graph_and_one_use_identity_slot() -> None:
    """All four routes compile; configure never places NIF in its request."""
    definitions = build_apoderado_operation_definitions(_unused_factory)
    registrations = build_apoderado_operation_registrations(definitions)
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
    assert {definition.definition_id for definition in registry.definitions} == {
        "auth.apoderado.status",
        "auth.apoderado.configure",
        "auth.apoderado.clear",
        "auth.apoderado.check",
    }
    configure = registry.lookup(APODERADO_CONFIGURE_OPERATION_DEFINITION_ID)
    assert configure.ephemeral_secret is not None
    assert configure.ephemeral_secret.secret_kind == APODERADO_REPRESENTED_NIF_SECRET_KIND
    assert "represented_nif" not in ApoderadoConfigureRequest.model_fields
    assert (
        OperationFrontendProjection.MCP in registry.lookup(APODERADO_STATUS_OPERATION_DEFINITION_ID).permitted_frontends
    )
    assert (
        OperationFrontendProjection.MCP in registry.lookup(APODERADO_CHECK_OPERATION_DEFINITION_ID).permitted_frontends
    )
    assert OperationFrontendProjection.MCP not in configure.permitted_frontends


def test_apoderado_public_status_is_complete_and_rejects_a_foreign_profile() -> None:
    """The public status copies all canonical facts under one UUID binding."""
    status = ApoderadoStatus(
        bucket_id=str(_PROFILE),
        configured=True,
        represented_nif="12345678Z",
        granted_scopes=("ALL",),
        catalogue_version="v1",
        configured_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    snapshot = ApoderadoStatusSnapshot.from_status(status)
    assert snapshot.bucket_id == _PROFILE
    assert snapshot.represented_nif == status.represented_nif
    assert snapshot.granted_scopes == status.granted_scopes
    with pytest.raises(ValidationError):
        ApoderadoOperationProjection(
            profile_id=_OTHER,
            operation_id=APODERADO_STATUS_OPERATION_DEFINITION_ID,
            outcome="completed",
            effect=OperationEffect.NONE,
            status=snapshot,
        )

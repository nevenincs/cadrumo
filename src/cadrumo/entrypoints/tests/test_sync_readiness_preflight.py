"""Shared worker preflight retains the exact actionable local blockers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from ...application.auth.operator_results import AuthLoginPreconditionError
from ...application.auth.sync_readiness import AuthSyncReadiness, AuthSyncRequirement
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from .. import auth_read_composition, live_state_composition

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_worker_refusal_keeps_required_fields_and_never_opens_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    ports = SimpleNamespace(
        certificate_secret_backend_factory=object(), operator_probe_ports=object(), operator_scope_ports=object()
    )
    monkeypatch.setattr(auth_read_composition, "compose_auth_read_ports", lambda _profile: ports)
    report = AuthSyncReadiness(
        provider="clave_movil",
        route="app_request",
        requirements=(
            AuthSyncRequirement(field="auth.fecha_validez", satisfied=False, reason="dni_validity_required"),
        ),
    )
    monkeypatch.setattr(live_state_composition, "build_auth_sync_readiness", lambda **_kwargs: report)
    with pytest.raises(AuthLoginPreconditionError) as failure:
        live_state_composition.preflight_filed_history_provider(uuid4(), cast(PinnedAuthorityOperation, object()))
    assert failure.value.translated_message == "application.auth.sync.errors.requirements_missing"
    error_context = failure.value.context
    assert error_context is not None
    assert error_context["required_fields"] == "auth.fecha_validez"
    assert error_context["provider"] == "clave_movil"
    assert error_context["route"] == "app_request"
    assert error_context["reasons"]

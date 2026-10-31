"""Kind, scope and replay contracts for durable auth cleanup preparation."""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from ....core.config import Settings
from ...tests.operator_scope_fakes import build_inward_operator_scope_ports_for_active_route
from ...workflow.state_models import WorkflowState
from .. import operator_revocation as revocation
from ..models import (
    AuthCleanupIntent,
    AuthCleanupOperationKind,
    AuthState,
    CertificateSecretMutationEventKind,
    CertificateSecretMutationIntent,
)
from ..operator_cleanup import assert_auth_cleanup_request_matches
from ..operator_results import (
    AuthConfigureNoActiveBucketError,
    AuthOperationScopeConflictError,
    CertificateSecretMutationInProgressError,
)
from .certificate_secret_fakes import InMemoryCertificateSecretBackendFactory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_STARTED_AT = datetime(2026, 1, 1, tzinfo=UTC)
_BUCKET_ID = "11111111-1111-4111-8111-111111111111"


def _intent(kind: AuthCleanupOperationKind, *, all_providers: bool = False) -> AuthCleanupIntent:
    return AuthCleanupIntent(
        operation_id="a" * 64,
        operation_kind=kind,
        bucket_id=_BUCKET_ID,
        provider_ids=("certificate", "clave_movil") if all_providers else ("certificate",),
        all_providers=all_providers,
        started_at=_STARTED_AT,
        session_provider_ids=("certificate",),
    )


@pytest.mark.parametrize("kind", tuple(AuthCleanupOperationKind))
@pytest.mark.parametrize(
    ("intent_all", "provider", "request_all", "matches"),
    (
        (False, "certificate", False, True),
        (False, "clave_movil", False, False),
        (False, None, False, True),
        (False, None, True, False),
        (True, None, True, True),
        (True, "certificate", True, True),
        (True, "certificate", False, False),
        (True, None, False, False),
    ),
)
def test_cleanup_request_matches_only_its_existing_kind_and_scope(
    kind: AuthCleanupOperationKind, intent_all: bool, provider: str | None, request_all: bool, matches: bool
) -> None:
    intent = _intent(kind, all_providers=intent_all)
    before = intent.model_dump_json()

    if matches:
        assert_auth_cleanup_request_matches(intent, operation_kind=kind, provider=provider, all_providers=request_all)
    else:
        with pytest.raises(AuthOperationScopeConflictError):
            assert_auth_cleanup_request_matches(
                intent, operation_kind=kind, provider=provider, all_providers=request_all
            )
    assert intent.model_dump_json() == before


@pytest.mark.parametrize("kind", tuple(AuthCleanupOperationKind))
def test_wrong_cleanup_kind_refuses_before_resolving_an_unknown_provider(kind: AuthCleanupOperationKind) -> None:
    other_kind = (
        AuthCleanupOperationKind.RESET if kind is AuthCleanupOperationKind.LOGOUT else AuthCleanupOperationKind.LOGOUT
    )
    with pytest.raises(AuthOperationScopeConflictError):
        assert_auth_cleanup_request_matches(
            _intent(other_kind), operation_kind=kind, provider="unknown-provider", all_providers=False
        )


@pytest.mark.parametrize("kind", tuple(AuthCleanupOperationKind))
def test_matching_resume_retains_the_exact_intent_without_preparing_another(
    monkeypatch: pytest.MonkeyPatch, kind: AuthCleanupOperationKind
) -> None:
    intent = _intent(kind)
    state = WorkflowState(auth=AuthState(cleanup_intent=intent), updated_at=_STARTED_AT)

    def unexpected_plan(**_kwargs: object) -> AuthCleanupIntent:
        raise AssertionError("a resumed cleanup must not prepare a new intent")

    monkeypatch.setattr(revocation, "build_auth_cleanup_intent", unexpected_plan)
    prepared = revocation._prepare_cleanup_intent(
        state,
        certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
        settings=Settings(),
        bucket_id=_BUCKET_ID,
        provider="certificate",
        all_providers=False,
        operation_kind=kind,
        started_at=datetime(2026, 2, 1, tzinfo=UTC),
    )

    assert prepared is state
    assert prepared.auth.cleanup_intent is intent
    assert intent.started_at == _STARTED_AT


@pytest.mark.parametrize("kind", tuple(AuthCleanupOperationKind))
@pytest.mark.parametrize("effects", (False, True))
def test_preparation_retains_the_requested_kind_and_only_stores_a_plan_with_effects(
    monkeypatch: pytest.MonkeyPatch, kind: AuthCleanupOperationKind, effects: bool
) -> None:
    state = WorkflowState(auth=AuthState(provider="certificate"), updated_at=_STARTED_AT)
    intent = _intent(kind).model_copy(update={"session_provider_ids": ("certificate",) if effects else ()})
    planned: list[dict[str, object]] = []

    def build_plan(**kwargs: object) -> AuthCleanupIntent:
        planned.append(kwargs)
        return intent

    monkeypatch.setattr(revocation, "build_auth_cleanup_intent", build_plan)
    settings = Settings()
    backend_factory = InMemoryCertificateSecretBackendFactory()
    prepared = revocation._prepare_cleanup_intent(
        state,
        certificate_secret_backend_factory=backend_factory,
        settings=settings,
        bucket_id=_BUCKET_ID,
        provider=None,
        all_providers=False,
        operation_kind=kind,
        started_at=_STARTED_AT,
    )

    assert planned == [
        {
            "certificate_secret_backend_factory": backend_factory,
            "settings": settings,
            "bucket_id": _BUCKET_ID,
            "auth": state.auth,
            "provider_ids": ("certificate",),
            "all_providers": False,
            "operation_kind": kind,
            "started_at": _STARTED_AT,
        }
    ]
    if effects:
        assert prepared.auth.cleanup_intent is intent
        assert state.auth.cleanup_intent is None
        assert prepared.auth.provider == state.auth.provider
    else:
        assert prepared is state


@pytest.mark.parametrize("kind", tuple(AuthCleanupOperationKind))
@pytest.mark.parametrize("mismatch", ("kind", "provider"))
def test_mismatched_resume_preserves_the_existing_intent(kind: AuthCleanupOperationKind, mismatch: str) -> None:
    intent = _intent(kind)
    state = WorkflowState(auth=AuthState(cleanup_intent=intent), updated_at=_STARTED_AT)
    requested_kind = (
        (AuthCleanupOperationKind.RESET if kind is AuthCleanupOperationKind.LOGOUT else AuthCleanupOperationKind.LOGOUT)
        if mismatch == "kind"
        else kind
    )
    before = state.model_dump_json()

    with pytest.raises(AuthOperationScopeConflictError):
        revocation._prepare_cleanup_intent(
            state,
            certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
            settings=Settings(),
            bucket_id=_BUCKET_ID,
            provider="clave_movil" if mismatch == "provider" else "certificate",
            all_providers=False,
            operation_kind=requested_kind,
            started_at=datetime(2026, 2, 1, tzinfo=UTC),
        )

    assert state.auth.cleanup_intent is intent
    assert state.model_dump_json() == before


@pytest.mark.parametrize("kind", tuple(AuthCleanupOperationKind))
def test_pending_certificate_mutation_refuses_before_cleanup_resume(kind: AuthCleanupOperationKind) -> None:
    mutation = CertificateSecretMutationIntent(
        operation_id="b" * 64,
        bucket_id=_BUCKET_ID,
        source_name="personal",
        event_kind=CertificateSecretMutationEventKind.SET,
        started_at=_STARTED_AT,
        prior_present=False,
    )
    state = WorkflowState(
        auth=AuthState(cleanup_intent=_intent(kind), certificate_secret_mutation_intent=mutation),
        updated_at=_STARTED_AT,
    )
    with pytest.raises(CertificateSecretMutationInProgressError):
        revocation._prepare_cleanup_intent(
            state,
            certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
            settings=Settings(),
            bucket_id=_BUCKET_ID,
            provider="unknown-provider",
            all_providers=False,
            operation_kind=kind,
            started_at=_STARTED_AT,
        )
    assert state.auth.certificate_secret_mutation_intent is mutation


@pytest.mark.parametrize("kind", tuple(AuthCleanupOperationKind))
@pytest.mark.parametrize("outcome", ("success", "failure", "missing_bucket"))
def test_preparation_scope_retains_lock_lifetime_order_and_original_failure(
    monkeypatch: pytest.MonkeyPatch, kind: AuthCleanupOperationKind, outcome: str
) -> None:
    """Effects execute inside both scopes; a missing profile never prepares an intent."""
    from ...workflow import persistence

    trace: list[str] = []
    settings = Settings()
    state = WorkflowState(auth=AuthState(cleanup_intent=_intent(kind)), updated_at=_STARTED_AT)
    ports = build_inward_operator_scope_ports_for_active_route()

    class Repository:
        def update(self, callback: Callable[[WorkflowState], WorkflowState]) -> WorkflowState:
            trace.append("prepare")
            return callback(state)

    repository = Repository()

    def load_settings() -> Settings:
        trace.append("settings")
        return settings

    @contextmanager
    def storage_span(
        received_settings: Settings, *, target_bucket_id: str | None, operator_scope_ports: object
    ) -> Generator[str | None]:
        assert received_settings is settings
        assert target_bucket_id == _BUCKET_ID
        assert operator_scope_ports is ports
        trace.append("storage_enter")
        try:
            yield None if outcome == "missing_bucket" else _BUCKET_ID
        finally:
            trace.append("storage_exit")

    @contextmanager
    def mutation_span(*, settings: Settings, bucket_id: str, operator_scope_ports: object) -> Generator[None]:
        assert settings is load_settings_result
        assert bucket_id == _BUCKET_ID
        assert operator_scope_ports is ports
        trace.append("mutation_enter")
        try:
            yield
        finally:
            trace.append("mutation_exit")

    def workflow_repository() -> Repository:
        trace.append("repository")
        return repository

    def clock() -> datetime:
        trace.append("clock")
        return _STARTED_AT

    load_settings_result = settings
    monkeypatch.setattr(revocation, "load_settings", load_settings)
    monkeypatch.setattr(revocation, "_revocation_storage_span", storage_span)
    monkeypatch.setattr(revocation, "_auth_mutation_span", mutation_span)
    monkeypatch.setattr(revocation, "now", clock)
    monkeypatch.setattr(persistence, "workflow_state_repository", workflow_repository)
    scope = revocation._prepared_cleanup_scope(
        certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
        provider="certificate",
        all_providers=False,
        target_bucket_id=_BUCKET_ID,
        operator_scope_ports=ports,
        operation_kind=kind,
    )
    error = OSError("synthetic effect failure")
    if outcome == "missing_bucket":
        with pytest.raises(AuthConfigureNoActiveBucketError), scope:
            raise AssertionError("a missing bucket cannot reach effects")
        assert trace == ["settings", "storage_enter", "storage_exit"]
        return
    if outcome == "failure":
        with pytest.raises(OSError) as raised, scope as cleanup:
            assert cleanup.settings is settings
            assert cleanup.bucket_id == _BUCKET_ID
            assert cleanup.repository is repository
            assert cleanup.state is state
            trace.append("effect")
            raise error
        assert raised.value is error
    else:
        with scope as cleanup:
            assert cleanup.state is state
            trace.append("effect")
    assert trace == [
        "settings",
        "storage_enter",
        "mutation_enter",
        "repository",
        "clock",
        "prepare",
        "effect",
        "mutation_exit",
        "storage_exit",
    ]

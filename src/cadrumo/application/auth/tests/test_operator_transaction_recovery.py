"""Real-storage proofs for auth CAS, cleanup recovery, and interleaving."""

from __future__ import annotations

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import copy_context
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier, Event

import pytest
from pydantic import SecretStr

from cadrumo.application.auth.models import AuthCleanupOperationKind, CertificateSecretMutationEventKind
from cadrumo.application.workflow.persistence import WorkflowStateRepository, workflow_state_repository
from cadrumo.application.workflow.state_models import WorkflowState

from ....adapters.outbound.aeat.auth import session_store
from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.storage import RepositoryError
from ....adapters.persistence.storage.bucket import bucket_paths
from ....application.wizard.catalogue import WIZARD_FLOWS
from ....core import AuthProviderKind
from ....core.config import load_settings
from ....domain.buckets import BucketEvent, BucketEventType
from ....domain.contribuyente import required_profile_keys
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from ....tests.user_profile import register_minimal_profile
from ..acquisition_lock import acquire_auth_acquisition_lock
from ..actions import update_auth
from ..certificate_source_operations import (
    register_operator_certificate_source,
    remove_operator_certificate_source_secret,
    resolve_certificate_source_secret,
    set_operator_certificate_source_secret,
)
from ..operator import (
    _build_auth_cleanup_intent,
    configure_operator_auth,
    logout_operator_auth,
    reset_operator_auth,
)
from ..operator_results import AuthCleanupInProgressError, CertificateSecretMutationInProgressError
from ..operator_scope import auth_mutation_span
from ..sessions import ensure_authenticated_aeat_session, storage_state_paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"
_STARTED_AT = datetime(2026, 7, 16, 17, 0, tzinfo=UTC)


def _create_profile(*, provider: str) -> None:
    assert WIZARD_FLOWS
    assert required_profile_keys()
    with open_test_profile_session(_BUCKET_ID):
        register_minimal_profile(profile_id=_BUCKET_ID)
        configure_operator_auth(provider)


def _seed_cleanup_intent(*, operation_kind: AuthCleanupOperationKind) -> None:
    settings = load_settings()
    repository = workflow_state_repository()

    def prepare(state: WorkflowState) -> WorkflowState:
        intent = _build_auth_cleanup_intent(
            settings=settings,
            bucket_id=_BUCKET_ID,
            auth=state.auth,
            provider_ids=(AuthProviderKind.CERTIFICATE.value,),
            all_providers=False,
            operation_kind=operation_kind,
            started_at=_STARTED_AT,
        )
        return state.model_copy(
            update={"auth": state.auth.model_copy(update={"cleanup_intent": intent})},
        )

    repository.update(prepare)


@contextmanager
def _blocking_workflow_update_trigger(db_path: Path):
    trigger_name = "fail_auth_cleanup_finalize"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            f"""
            CREATE TRIGGER {trigger_name}
            BEFORE UPDATE ON secure_objects
            WHEN OLD.namespace = 'cadrumo.workflow'
            BEGIN
                SELECT RAISE(ABORT, 'auth cleanup finalize blocked');
            END
            """,
        )
        connection.commit()
    try:
        yield
    finally:
        with sqlite3.connect(db_path) as connection:
            connection.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
            connection.commit()


@contextmanager
def _blocking_bucket_event_update_trigger(db_path: Path):
    trigger_name = "fail_certificate_secret_event_finalize"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            f"""
            CREATE TRIGGER {trigger_name}
            BEFORE UPDATE ON secure_objects
            WHEN OLD.namespace = 'cadrumo.domain.buckets.event_history'
            BEGIN
                SELECT RAISE(ABORT, 'certificate secret event finalize blocked');
            END
            """,
        )
        connection.commit()
    try:
        yield
    finally:
        with sqlite3.connect(db_path) as connection:
            connection.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
            connection.commit()


def _event_count(event_type: BucketEventType) -> int:
    return sum(event.event_type is event_type for event in BucketEventHistoryRepository().load().events.values())


def _events(event_type: BucketEventType) -> tuple[BucketEvent, ...]:
    return tuple(
        event for event in BucketEventHistoryRepository().load().events.values() if event.event_type is event_type
    )


def test_workflow_state_update_retries_real_revision_conflict_without_losing_change(
    tmp_path: Path,
) -> None:
    """A nested real write forces CAS retry and both independent changes survive."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        outer = WorkflowStateRepository(objects=profile.repository)
        concurrent = WorkflowStateRepository(objects=profile.repository)
        first_attempt = True

        def transform(state: WorkflowState) -> WorkflowState:
            nonlocal first_attempt
            if first_attempt:
                first_attempt = False
                concurrent.update(lambda current: update_auth(current, provider="clave_movil"))
            return state.model_copy(
                update={
                    "auth": state.auth.model_copy(
                        update={"certificate_path": str(tmp_path / "operator.p12")},
                    ),
                },
            )

        updated = outer.update(transform)

        assert first_attempt is False
        assert updated.auth.provider == "clave_movil"
        assert updated.auth.certificate_path == str(tmp_path / "operator.p12")
        assert outer.load().auth == updated.auth


def test_concurrent_first_workflow_writers_retry_absent_row_collision(
    tmp_path: Path,
) -> None:
    """Two first writers observe absence, then the CAS loser retries cleanly."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        barrier = Barrier(2)
        provider_repository = WorkflowStateRepository(objects=profile.repository)
        certificate_repository = WorkflowStateRepository(objects=profile.repository)

        def provider_write() -> None:
            first_attempt = True

            def transform(state: WorkflowState) -> WorkflowState:
                nonlocal first_attempt
                if first_attempt:
                    first_attempt = False
                    barrier.wait(timeout=10)
                return update_auth(state, provider="clave_movil")

            provider_repository.update(transform)

        def certificate_write() -> None:
            first_attempt = True

            def transform(state: WorkflowState) -> WorkflowState:
                nonlocal first_attempt
                if first_attempt:
                    first_attempt = False
                    barrier.wait(timeout=10)
                return update_auth(
                    state,
                    certificate_path=str(tmp_path / "operator.p12"),
                )

            certificate_repository.update(transform)

        contexts = (copy_context(), copy_context())
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = (
                executor.submit(contexts[0].run, provider_write),
                executor.submit(contexts[1].run, certificate_write),
            )
            for future in futures:
                future.result(timeout=30)

        final = provider_repository.load()
        assert final.auth.provider == "clave_movil"
        assert final.auth.certificate_path == str(tmp_path / "operator.p12")


def test_concurrent_auth_writers_are_serialized_without_losing_events(
    tmp_path: Path,
) -> None:
    """Two real writer threads preserve both workflow and durable events."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(provider="clave_movil")
        certificate_path = tmp_path / "operator.p12"
        certificate_path.write_bytes(b"certificate")
        barrier = Barrier(2)

        def configure(provider: str, path: Path | None) -> None:
            barrier.wait(timeout=10)
            with open_test_profile_session(_BUCKET_ID):
                configure_operator_auth(provider, certificate_path=path)

        contexts = (copy_context(), copy_context())
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = (
                executor.submit(
                    contexts[0].run,
                    configure,
                    "certificate",
                    certificate_path,
                ),
                executor.submit(
                    contexts[1].run,
                    configure,
                    "clave_movil",
                    None,
                ),
            )
            for future in futures:
                future.result(timeout=30)

        with open_test_profile_session(_BUCKET_ID):
            final = workflow_state_repository().load()
            durable = BucketEventHistoryRepository().load()

        configured_workflow_objects = {
            event.object_id for event in final.bucket_events if event.action == "auth.provider.configured"
        }
        configured_durable_objects = {
            event.object_id
            for event in durable.events.values()
            if event.event_type is BucketEventType.AUTH_PROVIDER_CONFIGURED
        }
        assert final.auth.provider in {"certificate", "clave_movil"}
        assert configured_workflow_objects == {"certificate", "clave_movil"}
        assert configured_durable_objects == {"certificate", "clave_movil"}


def test_certificate_secret_set_event_failure_resumes_original_set_once(
    tmp_path: Path,
) -> None:
    """A failed event commit preserves SET classification and a secret-free intent."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        certificate_path = tmp_path / "operator.p12"
        certificate_path.write_bytes(b"certificate")
        blocked_path = tmp_path / "blocked.p12"
        blocked_path.write_bytes(b"blocked")
        _create_profile(provider="certificate")
        with open_test_profile_session(_BUCKET_ID):
            register_operator_certificate_source(name="personal", certificate_path=certificate_path)
            repository = workflow_state_repository()
            db_path = bucket_paths(storage_root, _BUCKET_ID).database_file

            with _blocking_bucket_event_update_trigger(db_path), pytest.raises(RepositoryError):
                set_operator_certificate_source_secret(
                    name="personal",
                    secret=SecretStr("first-private-passphrase"),
                )

            pending = repository.load().auth.certificate_secret_mutation_intent
            resolved_after_failure = resolve_certificate_source_secret(
                name="personal",
                bucket_id=_BUCKET_ID,
            )
            assert pending is not None
            assert pending.event_kind is CertificateSecretMutationEventKind.SET
            assert pending.prior_present is False
            assert pending.completion_witness == f"secret-record:{pending.operation_id}"
            assert "first-private-passphrase" not in pending.model_dump_json()
            assert resolved_after_failure is not None
            assert resolved_after_failure.get_secret_value() == "first-private-passphrase"
            assert _event_count(BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_SET) == 0

            with pytest.raises(CertificateSecretMutationInProgressError) as blocked_error:
                configure_operator_auth("clave_movil")
            assert "first-private-passphrase" not in repr(blocked_error.value)
            with pytest.raises(CertificateSecretMutationInProgressError):
                register_operator_certificate_source(
                    name="blocked",
                    certificate_path=blocked_path,
                )
            with pytest.raises(CertificateSecretMutationInProgressError):
                reset_operator_auth(provider="certificate")
            with pytest.raises(CertificateSecretMutationInProgressError):
                set_operator_certificate_source_secret(
                    name="personal",
                    secret=SecretStr("different-retry-passphrase"),
                )
            unchanged = resolve_certificate_source_secret(
                name="personal",
                bucket_id=_BUCKET_ID,
            )
            assert unchanged is not None
            assert unchanged.get_secret_value() == "first-private-passphrase"

            resumed = set_operator_certificate_source_secret(
                name="personal",
                secret=SecretStr("first-private-passphrase"),
            )
            final = repository.load()
            events = _events(BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_SET)

        assert resumed.rotated is False
        assert resumed.has_secret is True
        assert final.auth.certificate_secret_mutation_intent is None
        assert len(events) == 1
        assert events[0].occurred_at == pending.started_at
        assert events[0].payload["operation_id"] == pending.operation_id
        assert "first-private-passphrase" not in events[0].model_dump_json()


def test_certificate_secret_rotation_event_failure_resumes_original_rotation_once(
    tmp_path: Path,
) -> None:
    """A failed event commit cannot reclassify a rotation as another mutation."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        certificate_path = tmp_path / "operator.p12"
        certificate_path.write_bytes(b"certificate")
        _create_profile(provider="certificate")
        with open_test_profile_session(_BUCKET_ID):
            register_operator_certificate_source(name="personal", certificate_path=certificate_path)
            set_operator_certificate_source_secret(
                name="personal",
                secret=SecretStr("original-passphrase"),
            )
            repository = workflow_state_repository()
            db_path = bucket_paths(storage_root, _BUCKET_ID).database_file

            with _blocking_bucket_event_update_trigger(db_path), pytest.raises(RepositoryError):
                set_operator_certificate_source_secret(
                    name="personal",
                    secret=SecretStr("rotated-passphrase"),
                )

            pending = repository.load().auth.certificate_secret_mutation_intent
            assert pending is not None
            assert pending.event_kind is CertificateSecretMutationEventKind.ROTATED
            assert pending.prior_present is True
            assert _event_count(BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_ROTATED) == 0

            resumed = set_operator_certificate_source_secret(
                name="personal",
                secret=SecretStr("rotated-passphrase"),
            )
            resolved = resolve_certificate_source_secret(name="personal", bucket_id=_BUCKET_ID)
            events = _events(BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_ROTATED)

        assert resumed.rotated is True
        assert resolved is not None
        assert resolved.get_secret_value() == "rotated-passphrase"
        assert len(events) == 1
        assert events[0].occurred_at == pending.started_at
        assert events[0].payload["operation_id"] == pending.operation_id


def test_certificate_secret_remove_event_failure_reports_original_removal_once(
    tmp_path: Path,
) -> None:
    """A failed event commit resumes an already-completed removal truthfully."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        certificate_path = tmp_path / "operator.p12"
        certificate_path.write_bytes(b"certificate")
        _create_profile(provider="certificate")
        with open_test_profile_session(_BUCKET_ID):
            register_operator_certificate_source(name="personal", certificate_path=certificate_path)
            set_operator_certificate_source_secret(
                name="personal",
                secret=SecretStr("private-passphrase"),
            )
            repository = workflow_state_repository()
            db_path = bucket_paths(storage_root, _BUCKET_ID).database_file

            with _blocking_bucket_event_update_trigger(db_path), pytest.raises(RepositoryError):
                remove_operator_certificate_source_secret(name="personal")

            pending = repository.load().auth.certificate_secret_mutation_intent
            assert pending is not None
            assert pending.event_kind is CertificateSecretMutationEventKind.REMOVED
            assert pending.prior_present is True
            assert pending.completion_witness == f"secret-absent:{pending.operation_id}"
            assert resolve_certificate_source_secret(name="personal", bucket_id=_BUCKET_ID) is None
            assert _event_count(BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_REMOVED) == 0

            resumed = remove_operator_certificate_source_secret(name="personal")
            repeated = remove_operator_certificate_source_secret(name="personal")
            final = repository.load()
            events = _events(BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_REMOVED)

        assert resumed.removed is True
        assert repeated.removed is False
        assert final.auth.certificate_secret_mutation_intent is None
        assert len(events) == 1
        assert events[0].occurred_at == pending.started_at
        assert events[0].payload["operation_id"] == pending.operation_id


def test_logout_write_failure_resumes_cleanup_and_emits_session_event_once(
    tmp_path: Path,
) -> None:
    """A real SQLite abort after session deletion leaves a resumable intent."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _create_profile(provider="certificate")
        with open_test_profile_session(_BUCKET_ID):
            repository = workflow_state_repository()
            repository.update(
                lambda state: state.model_copy(
                    update={
                        "auth": state.auth.model_copy(
                            update={"authenticated_at": _STARTED_AT, "subject": "operator"},
                        ),
                    },
                ),
            )
            session_path = storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state
            session_store.save(
                session_path,
                storage_state={},
                metadata={"provider_kind": "certificate"},
            )
            _seed_cleanup_intent(operation_kind=AuthCleanupOperationKind.LOGOUT)
            db_path = bucket_paths(storage_root, _BUCKET_ID).database_file

            with _blocking_workflow_update_trigger(db_path), pytest.raises(RepositoryError):
                logout_operator_auth(provider="certificate")

            interrupted = repository.load()
            assert interrupted.auth.cleanup_intent is not None
            assert session_store.exists(session_path) is False
            assert _event_count(BucketEventType.AUTH_SESSION_CLEARED) == 0

            resumed = logout_operator_auth(provider="certificate")
            rerun = logout_operator_auth(provider="certificate")
            final = repository.load()
            durable_event_count = _event_count(BucketEventType.AUTH_SESSION_CLEARED)

        assert resumed.removed_sessions == 1
        assert resumed.cleared_session_state is True
        assert rerun.removed_sessions == 0
        assert rerun.cleared_session_state is False
        assert final.auth.cleanup_intent is None
        assert final.auth.provider == "certificate"
        assert final.auth.authenticated_at is None
        assert durable_event_count == 1
        assert sum(event.action == "auth.session.cleared" for event in final.bucket_events) == 1


def test_reset_write_failure_resumes_real_cleanup_and_emits_effects_once(
    tmp_path: Path,
) -> None:
    """Secrets, sessions, and locks remain truthfully accounted after retry."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        cert_path = tmp_path / "operator.p12"
        cert_path.write_bytes(b"certificate")
        _create_profile(provider="certificate")
        settings = load_settings()
        with (
            open_test_profile_session(_BUCKET_ID),
            acquire_auth_acquisition_lock(
                settings,
                AuthProviderKind.CERTIFICATE,
                ttl_seconds=60,
                operation="reset-recovery-test",
            ),
        ):
            register_operator_certificate_source(name="personal", certificate_path=cert_path)
            set_operator_certificate_source_secret(name="personal", secret=SecretStr("private"))
            session_path = storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state
            session_store.save(
                session_path,
                storage_state={},
                metadata={"provider_kind": "certificate"},
            )
            _seed_cleanup_intent(operation_kind=AuthCleanupOperationKind.RESET)
            db_path = bucket_paths(storage_root, _BUCKET_ID).database_file

            with _blocking_workflow_update_trigger(db_path), pytest.raises(RepositoryError):
                reset_operator_auth(provider="certificate")

            interrupted = workflow_state_repository().load()
            assert interrupted.auth.cleanup_intent is not None
            assert session_store.exists(session_path) is False
            assert resolve_certificate_source_secret(name="personal", bucket_id=_BUCKET_ID) is None
            assert _event_count(BucketEventType.AUTH_PROVIDER_CLEARED) == 0

            resumed = reset_operator_auth(provider="certificate")
            rerun = reset_operator_auth(provider="certificate")
            final = workflow_state_repository().load()
            durable_event_counts = {
                event_type: _event_count(event_type)
                for event_type in (
                    BucketEventType.AUTH_PROVIDER_CLEARED,
                    BucketEventType.AUTH_SESSION_CLEARED,
                    BucketEventType.AUTH_LOCK_CLEARED,
                    BucketEventType.AUTH_CERTIFICATE_SOURCE_REMOVED,
                    BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_REMOVED,
                )
            }

        assert resumed.removed_sessions == 1
        assert resumed.cleared_locks == 1
        assert resumed.removed_certificate_sources == 1
        assert resumed.removed_certificate_secrets == 1
        assert rerun.removed_sessions == 0
        assert rerun.cleared_locks == 0
        assert final.auth.cleanup_intent is None
        assert final.auth.provider is None
        assert durable_event_counts[BucketEventType.AUTH_PROVIDER_CLEARED] == 1
        assert durable_event_counts[BucketEventType.AUTH_SESSION_CLEARED] == 1
        assert durable_event_counts[BucketEventType.AUTH_LOCK_CLEARED] == 1
        assert durable_event_counts[BucketEventType.AUTH_CERTIFICATE_SOURCE_REMOVED] == 1
        assert durable_event_counts[BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_REMOVED] == 1


def test_pending_cleanup_refuses_new_auth_configuration_source_and_secret_writes(
    tmp_path: Path,
) -> None:
    """Pending cleanup owns auth custody until the matching reset resumes."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        old_path = tmp_path / "old.p12"
        blocked_path = tmp_path / "blocked.p12"
        old_path.write_bytes(b"old")
        blocked_path.write_bytes(b"blocked")
        _create_profile(provider="certificate")
        with open_test_profile_session(_BUCKET_ID):
            register_operator_certificate_source(name="old", certificate_path=old_path)
            set_operator_certificate_source_secret(name="old", secret=SecretStr("old-secret"))
            _seed_cleanup_intent(operation_kind=AuthCleanupOperationKind.RESET)

            with pytest.raises(AuthCleanupInProgressError):
                configure_operator_auth("clave_movil")
            with pytest.raises(AuthCleanupInProgressError):
                register_operator_certificate_source(
                    name="blocked",
                    certificate_path=blocked_path,
                )
            with pytest.raises(AuthCleanupInProgressError):
                set_operator_certificate_source_secret(
                    name="old",
                    secret=SecretStr("replacement"),
                )

            blocked = workflow_state_repository().load()
            old_secret = resolve_certificate_source_secret(name="old", bucket_id=_BUCKET_ID)
            result = reset_operator_auth(provider="certificate")
            final = workflow_state_repository().load()

        assert result.removed_certificate_sources == 1
        assert blocked.auth.provider == "certificate"
        assert set(blocked.auth.certificate_sources) == {"old"}
        assert old_secret is not None
        assert old_secret.get_secret_value() == "old-secret"
        assert final.auth.provider is None
        assert final.auth.certificate_sources == {}


@pytest.mark.asyncio
async def test_pending_cleanup_refuses_central_live_session_writer(
    tmp_path: Path,
) -> None:
    """Backend live reads cannot recreate session custody during reset recovery."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(provider="certificate")
        with open_test_profile_session(_BUCKET_ID):
            _seed_cleanup_intent(operation_kind=AuthCleanupOperationKind.RESET)

            with pytest.raises(AuthCleanupInProgressError):
                await ensure_authenticated_aeat_session(
                    load_settings(),
                    kind=AuthProviderKind.CERTIFICATE,
                )

            pending = workflow_state_repository().load()

        assert pending.auth.cleanup_intent is not None


def test_failed_reset_serializes_and_refuses_concurrent_central_session_writer(
    tmp_path: Path,
) -> None:
    """A real reset failure leaves intent that the queued live writer must honor."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _create_profile(provider="certificate")
        with open_test_profile_session(_BUCKET_ID):
            _seed_cleanup_intent(operation_kind=AuthCleanupOperationKind.RESET)

        db_path = bucket_paths(storage_root, _BUCKET_ID).database_file
        reset_locked = Event()
        continue_reset = Event()
        writer_started = Event()

        def failing_reset() -> None:
            with open_test_profile_session(_BUCKET_ID):
                settings = load_settings()
                with auth_mutation_span(settings=settings, bucket_id=_BUCKET_ID):
                    reset_locked.set()
                    assert continue_reset.wait(timeout=10)
                    reset_operator_auth(provider="certificate")

        def central_session_writer() -> None:
            """The second actor, authenticated to the same profile as the first.

            It opens its own custody session because that is what a real
            concurrent writer holds: an auth operation may not borrow another
            context's session, so without one this thread would be refused for
            missing custody long before it could meet the cleanup intent this
            test is about.
            """
            writer_started.set()
            with open_test_profile_session(_BUCKET_ID):
                asyncio.run(
                    ensure_authenticated_aeat_session(
                        load_settings(),
                        kind=AuthProviderKind.CERTIFICATE,
                        fresh=True,
                    ),
                )

        contexts = (copy_context(), copy_context())
        with (
            _blocking_workflow_update_trigger(db_path),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            reset_future = executor.submit(contexts[0].run, failing_reset)
            assert reset_locked.wait(timeout=10)
            writer_future = executor.submit(contexts[1].run, central_session_writer)
            assert writer_started.wait(timeout=10)
            assert writer_future.done() is False
            continue_reset.set()

            with pytest.raises(RepositoryError):
                reset_future.result(timeout=30)
            with pytest.raises(AuthCleanupInProgressError):
                writer_future.result(timeout=30)

        with open_test_profile_session(_BUCKET_ID):
            pending = workflow_state_repository().load()
        assert pending.auth.cleanup_intent is not None

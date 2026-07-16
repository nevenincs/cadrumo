"""Operator-facing certificate-source registry verbs for the config CLI.

Wraps the pure :mod:`~application.auth._certificate_sources` state
transformations with the same active-bucket gating, secure-object
persistence, and typed bucket-event emission that
:func:`~application.auth.configure_operator_auth` uses, so registering,
listing, selecting, or removing a named certificate source is exposed
through ``aeat config auth certificate ...`` with identical safety
guarantees.

:func:`~application.auth.check_operator_certificate_sources` extends the registry with
expiry/rotation awareness: it re-runs the same local PKCS#12 health
probe the single-certificate ``auth test`` path already performs
(:mod:`~application.auth._operator_probes`) against every registered
source rather than only the active ``certificate_path``, so a gestor
managing several apoderado certificates gets a renewal reminder for
each one individually.

See Also:
    :mod:`~application.auth._certificate_sources`
        Pure :class:`~application.workflow.WorkflowState` transformations
        this module persists.
    :func:`~application.auth.configure_operator_auth`
        Sibling operator verb configuring the active auth *provider*;
        this module manages named certificate *sources* within the
        certificate provider.
    :func:`~application.auth.probe_provider_configuration`
        Sibling single-certificate expiry probe this module's
        :func:`~application.auth.check_operator_certificate_sources` reuses per named
        source.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import SecretStr

from ...core.config import Settings, load_settings
from ...core.errors import AeatError
from ...core.time import now
from .._workflow_auth_models import (
    CertificateSecretMutationEventKind,
    CertificateSecretMutationIntent,
)
from ..auth_credentials import (
    ActiveCertificateCredentials,
)
from ._certificate_secret_backend import (
    SECURE_STORAGE_BACKEND_LABEL,
    SecureStorageCertificateSecretBackend,
)
from ._certificate_sources import (
    CertificateSourceNotFoundError as _StateCertificateSourceNotFoundError,
)
from ._certificate_sources import (
    _auth_state,
    list_certificate_sources,
    register_certificate_source,
    remove_certificate_source,
    select_certificate_source,
)
from ._certificate_sources import (
    active_certificate_source as _active_certificate_source,
)
from ._credential_resolution import (
    resolve_active_certificate_credentials,
    resolve_active_certificate_credentials_from_state,
    resolve_certificate_source_secret,
)
from ._mutation import AuthBucketEventSpec, build_auth_bucket_events
from ._operator_probes import ProviderProbeResult, _probe_certificate_bundle
from ._operator_results import (
    AuthConfigureDanglingActiveProfileError,
    AuthConfigureNoActiveBucketError,
    CertificateSourceCheckEntry,
    CertificateSourceCheckReport,
    CertificateSourceListResult,
    CertificateSourceMutationResult,
    CertificateSourceNotFoundError,
    CertificateSourcePayload,
    CertificateSourceSecretMutationResult,
)
from ._operator_scope import (
    active_profile_storage_span,
    assert_auth_cleanup_not_in_progress,
    assert_auth_recovery_not_in_progress,
    assert_certificate_secret_mutation_not_in_progress,
    auth_mutation_span,
)

if TYPE_CHECKING:
    from ...domain.buckets import BucketEvent, BucketEventType
    from ..workflow import WorkflowState, WorkflowStateRepository


def _gate_active_bucket() -> str:
    """Resolve the active bucket id or raise the shared refusal errors.

    Mirrors the gating :func:`~application.auth.configure_operator_auth`
    performs so a certificate-source mutation cannot land against a
    missing or dangling active profile.

    Returns:
        The active bucket id.
    """
    from ...core import resolve_active_bucket_id
    from ..workflow import assess_active_profile_health, workflow_state_repository

    if resolve_active_bucket_id() is None:
        raise AuthConfigureNoActiveBucketError(
            translated_message="application.auth.operator.errors.no_active_bucket",
        )
    state_repo = workflow_state_repository()
    current_state = state_repo.load()
    profile_health = assess_active_profile_health(current_state)
    active_bucket_id = profile_health.active_profile
    if active_bucket_id is None:
        raise AuthConfigureNoActiveBucketError(
            translated_message="application.auth.operator.errors.no_active_bucket",
        )
    if profile_health.status == "dangling_pointer":
        raise AuthConfigureDanglingActiveProfileError(
            translated_message="application.auth.operator.errors.dangling_active_profile",
            context={"active_profile": active_bucket_id},
        )
    if profile_health.status in {"missing_profile_record", "profile_record_unreadable"}:
        raise AuthConfigureDanglingActiveProfileError(
            translated_message="application.auth.operator.errors.unreadable_active_profile",
            context={
                "active_profile": active_bucket_id,
                "status": profile_health.status,
                "next_action": profile_health.next_action,
            },
        )
    return active_bucket_id


@contextmanager
def _certificate_mutation_span(*, resume_certificate_secret: bool = False) -> Iterator[str]:
    """Open the active bucket and serialize one certificate auth mutation."""
    settings = load_settings()
    with active_profile_storage_span(settings) as bucket_id:
        if bucket_id is None:
            raise AuthConfigureNoActiveBucketError(
                translated_message="application.auth.operator.errors.no_active_bucket",
            )
        with auth_mutation_span(settings=settings, bucket_id=bucket_id):
            active_bucket_id = _gate_active_bucket()
            from ..workflow import workflow_state_repository

            current = workflow_state_repository().load()
            if resume_certificate_secret:
                assert_auth_cleanup_not_in_progress(current)
            else:
                assert_auth_recovery_not_in_progress(current)
            yield active_bucket_id


def _persist_with_event(
    *,
    active_bucket_id: str,
    transform: Callable[[WorkflowState], WorkflowState],
    event_type: BucketEventType,
    object_id: str,
    payload: dict[str, str],
) -> WorkflowState:
    from ..workflow import workflow_state_repository

    occurred_at = now()
    state_repo = workflow_state_repository()
    return state_repo.update_with_bucket_events(
        lambda current: (
            transform(_state_without_pending_auth_recovery(current)),
            build_auth_bucket_events(
                bucket_id=active_bucket_id,
                events=(
                    AuthBucketEventSpec(
                        event_type,
                        object_id,
                        payload,
                        occurred_at,
                    ),
                ),
            ),
        ),
    )


def _state_without_pending_auth_recovery(state: WorkflowState) -> WorkflowState:
    """Return ``state`` only when no resumable auth operation owns the bucket."""
    assert_auth_recovery_not_in_progress(state)
    return state


def register_operator_certificate_source(
    *,
    name: str,
    certificate_path: Path,
    friendly_name: str | None = None,
) -> CertificateSourceMutationResult:
    """Register (or re-point) a named certificate source for the active profile.

    Raises:
        AuthConfigureNoActiveBucketError: When no active profile bucket
            exists yet.
        AuthConfigureDanglingActiveProfileError: When the active-profile
            pointer does not resolve to a registered bucket.

    Returns:
        A :class:`~application.auth.CertificateSourceMutationResult`.
    """
    from ...domain.buckets import BucketEventType

    with _certificate_mutation_span() as active_bucket_id:
        _persist_with_event(
            active_bucket_id=active_bucket_id,
            transform=lambda state: register_certificate_source(
                state,
                name=name,
                certificate_path=certificate_path,
                friendly_name=friendly_name,
            ),
            event_type=BucketEventType.AUTH_CERTIFICATE_SOURCE_REGISTERED,
            object_id=name.strip(),
            payload={"name": name.strip(), "certificate_path": str(certificate_path)},
        )
    return CertificateSourceMutationResult(name=name.strip(), certificate_path=str(certificate_path))


def list_operator_certificate_sources() -> CertificateSourceListResult:
    """Return every registered certificate source for the active profile.

    Returns:
        A :class:`~application.auth.CertificateSourceListResult`.
    """
    from ..workflow import workflow_state_repository

    state = workflow_state_repository().load()
    active_record = _active_certificate_source(state)
    active_name = active_record.name if active_record is not None else None
    sources = list_certificate_sources(state)
    return CertificateSourceListResult(
        sources=tuple(
            CertificateSourcePayload(
                name=record.name,
                certificate_path=record.certificate_path,
                friendly_name=record.friendly_name or "",
                active=record.name == active_name,
                registered_at=record.registered_at.isoformat(),
            )
            for record in sources
        ),
        active_source=active_name or "",
    )


def select_operator_certificate_source(*, name: str) -> CertificateSourceMutationResult:
    """Mark ``name`` the active certificate source for the active profile.

    Selecting a source mirrors its path onto ``AuthState.certificate_path``
    so every existing certificate-provider consumer (the backend health
    probe, live login preconditions, ``auth status``/``auth test``) reads
    the newly selected source without further changes.

    Raises:
        AuthConfigureNoActiveBucketError: When no active profile bucket
            exists yet.
        AuthConfigureDanglingActiveProfileError: When the active-profile
            pointer does not resolve to a registered bucket.
        CertificateSourceNotFoundError: When ``name`` is not registered.

    Returns:
        A :class:`~application.auth.CertificateSourceMutationResult`.
    """
    from ...domain.buckets import BucketEventType

    normalized_name = name.strip()
    with _certificate_mutation_span() as active_bucket_id:
        from ..workflow import workflow_state_repository

        current = workflow_state_repository().load()
        record = current.auth.certificate_sources.get(normalized_name)
        if record is None:
            raise CertificateSourceNotFoundError(
                translated_message="application.auth.operator.errors.certificate_source_not_found",
                context={"name": normalized_name},
            )
        try:
            next_state = _persist_with_event(
                active_bucket_id=active_bucket_id,
                transform=lambda state: select_certificate_source(state, name=normalized_name),
                event_type=BucketEventType.AUTH_CERTIFICATE_SOURCE_SELECTED,
                object_id=normalized_name,
                payload={"name": normalized_name, "certificate_path": record.certificate_path},
            )
        except _StateCertificateSourceNotFoundError as exc:
            raise CertificateSourceNotFoundError(
                translated_message="application.auth.operator.errors.certificate_source_not_found",
                context={"name": normalized_name},
            ) from exc
        record = next_state.auth.certificate_sources[normalized_name]
    return CertificateSourceMutationResult(
        name=name.strip(),
        certificate_path=record.certificate_path,
        active=True,
    )


def remove_operator_certificate_source(*, name: str) -> CertificateSourceMutationResult:
    """Remove the named certificate source from the active profile's registry.

    A ``name`` that is not registered is a no-op (``removed=False``), not
    an error, matching the idempotent-removal convention used elsewhere
    in the auth surface.

    Raises:
        AuthConfigureNoActiveBucketError: When no active profile bucket
            exists yet.
        AuthConfigureDanglingActiveProfileError: When the active-profile
            pointer does not resolve to a registered bucket.

    Returns:
        A :class:`~application.auth.CertificateSourceMutationResult`.
    """
    from ...domain.buckets import BucketEventType
    from ..workflow import workflow_state_repository

    normalized_name = name.strip()
    with _certificate_mutation_span() as active_bucket_id:
        current_state = workflow_state_repository().load()
        removed = normalized_name in current_state.auth.certificate_sources
        if removed:
            _persist_with_event(
                active_bucket_id=active_bucket_id,
                transform=lambda state: remove_certificate_source(state, name=normalized_name)[0],
                event_type=BucketEventType.AUTH_CERTIFICATE_SOURCE_REMOVED,
                object_id=normalized_name,
                payload={"name": normalized_name},
            )
    return CertificateSourceMutationResult(name=name.strip(), removed=removed)


def check_operator_certificate_sources(*, settings: Settings | None = None) -> CertificateSourceCheckReport:
    """Classify expiry/rotation health for every registered certificate source.

    Reuses the same local PKCS#12 probe
    (:func:`~application.auth._operator_probes._probe_certificate_bundle`)
    the single-certificate ``auth test`` path already runs — classifying
    ``ok`` / ``expiring`` / ``expired`` / ``corrupt`` / ``unreadable`` /
    ``file_missing`` — but applies it to every named source in the
    registry rather than only the active ``certificate_path``. A gestor
    with several apoderado certificates therefore gets one renewal
    reminder per entity, not only for whichever certificate happens to
    be selected.

    Every named source's passphrase resolves only through
    :func:`~application.auth.resolve_certificate_source_secret` (the
    per-source :class:`~application.auth.CertificateSecretBackend`). An
    absent secret or secure-storage read failure is projected explicitly
    as ``None`` so the probe fails closed; a named source never inherits
    the global
    :attr:`~core.config.Settings.cadrumo_certificate_password_secret`.
    The unnamed Settings credential remains the supported single-certificate
    contract only when no named source is selected and therefore is never part
    of this registry-wide check.

    This is a pure read: it opens the explicit or active profile's storage
    session when needed, but it never mutates state or emits a bucket event.

    Returns:
        A :class:`~application.auth.CertificateSourceCheckReport` with one
        :class:`~application.auth.CertificateSourceCheckEntry` per
        registered source, sorted by name (matching
        :func:`~application.auth.list_operator_certificate_sources`).
    """
    from ..workflow import workflow_state_repository

    resolved_settings = settings or load_settings()
    with active_profile_storage_span(resolved_settings) as active_bucket_id:
        if active_bucket_id is None:
            return CertificateSourceCheckReport(entries=(), has_warnings=False)
        state = workflow_state_repository().load()
        active_record = _active_certificate_source(state)
        active_name = active_record.name if active_record is not None else None
        sources = list_certificate_sources(state)
        entries: list[CertificateSourceCheckEntry] = []
        has_warnings = False
        for record in sources:
            try:
                per_source_secret = resolve_certificate_source_secret(
                    name=record.name,
                    bucket_id=active_bucket_id,
                    settings=resolved_settings,
                )
            except (OSError, AeatError):
                per_source_secret = None
            credentials = ActiveCertificateCredentials(
                certificate_path=Path(record.certificate_path),
                password=per_source_secret,
                friendly_name=record.friendly_name,
                source_name=record.name,
            )
            outcome = _probe_certificate_bundle(
                record.certificate_path,
                settings=resolved_settings,
                certificate_credentials=credentials,
            )
            if outcome.result in (ProviderProbeResult.EXPIRING, ProviderProbeResult.EXPIRED):
                has_warnings = True
            entries.append(
                CertificateSourceCheckEntry(
                    name=record.name,
                    certificate_path=record.certificate_path,
                    friendly_name=record.friendly_name or "",
                    active=record.name == active_name,
                    result=str(outcome.result),
                    summary=outcome.summary,
                    days_until_expiry=outcome.days_until_expiry,
                ),
            )
        return CertificateSourceCheckReport(entries=tuple(entries), has_warnings=has_warnings)


def set_operator_certificate_source_secret(
    *,
    name: str,
    secret: SecretStr,
) -> CertificateSourceSecretMutationResult:
    """Set (or rotate) the passphrase for a registered certificate source.

    The named source MUST already be registered
    (:func:`~application.auth.register_operator_certificate_source`) — a secret is bound
    to an existing source, never freestanding. The secret always persists
    to the sole encrypted secure-storage backend; there is no backend
    choice. The secret itself is never persisted to
    :class:`~application.workflow.WorkflowState` or emitted in the mutation
    result; only whether one is now present.

    Raises:
        AuthConfigureNoActiveBucketError: When no active profile bucket
            exists yet.
        AuthConfigureDanglingActiveProfileError: When the active-profile
            pointer does not resolve to a registered bucket.
        CertificateSourceNotFoundError: When ``name`` is not registered.

    Returns:
        A :class:`~application.auth.CertificateSourceSecretMutationResult`.
    """
    from ..workflow import workflow_state_repository

    normalized_name = name.strip()
    with _certificate_mutation_span(resume_certificate_secret=True) as active_bucket_id:
        backend = SecureStorageCertificateSecretBackend(bucket_id=active_bucket_id)
        repository = workflow_state_repository()
        intent = _prepare_certificate_secret_mutation(
            repository=repository,
            backend=backend,
            active_bucket_id=active_bucket_id,
            source_name=normalized_name,
            removing=False,
            secret=secret,
        )
        if intent is None:
            raise RuntimeError("certificate secret set prepared no durable mutation intent")
        _complete_certificate_secret_mutation(
            repository=repository,
            backend=backend,
            intent=intent,
            secret=secret,
        )
        _finalize_certificate_secret_mutation(repository=repository, intent=intent)
    return CertificateSourceSecretMutationResult(
        name=normalized_name,
        backend=SECURE_STORAGE_BACKEND_LABEL,
        has_secret=True,
        rotated=intent.event_kind is CertificateSecretMutationEventKind.ROTATED,
    )


def remove_operator_certificate_source_secret(*, name: str) -> CertificateSourceSecretMutationResult:
    """Remove the persisted passphrase for a registered certificate source.

    A ``name`` with no registered secret is a no-op (``removed=False``),
    matching the idempotent-removal convention used elsewhere on the
    auth surface. The removal always targets the sole encrypted
    secure-storage backend; there is no backend choice and no keyring
    cleanup path.

    Raises:
        AuthConfigureNoActiveBucketError: When no active profile bucket
            exists yet.
        AuthConfigureDanglingActiveProfileError: When the active-profile
            pointer does not resolve to a registered bucket.

    Returns:
        A :class:`~application.auth.CertificateSourceSecretMutationResult`.
    """
    normalized_name = name.strip()
    with _certificate_mutation_span(resume_certificate_secret=True) as active_bucket_id:
        from ..workflow import workflow_state_repository

        backend = SecureStorageCertificateSecretBackend(bucket_id=active_bucket_id)
        repository = workflow_state_repository()
        intent = _prepare_certificate_secret_mutation(
            repository=repository,
            backend=backend,
            active_bucket_id=active_bucket_id,
            source_name=normalized_name,
            removing=True,
            secret=None,
        )
        if intent is not None:
            _complete_certificate_secret_mutation(
                repository=repository,
                backend=backend,
                intent=intent,
                secret=None,
            )
            _finalize_certificate_secret_mutation(repository=repository, intent=intent)
    return CertificateSourceSecretMutationResult(
        name=normalized_name,
        backend=SECURE_STORAGE_BACKEND_LABEL,
        has_secret=False,
        removed=intent is not None and intent.prior_present,
    )


def _auth_state_certificate_sources(state: WorkflowState) -> dict[str, object]:
    return dict(_auth_state(state).certificate_sources)


def _prepare_certificate_secret_mutation(
    *,
    repository: WorkflowStateRepository,
    backend: SecureStorageCertificateSecretBackend,
    active_bucket_id: str,
    source_name: str,
    removing: bool,
    secret: SecretStr | None,
) -> CertificateSecretMutationIntent | None:
    """Persist or resume the secret-free intent for one certificate-secret mutation."""
    started_at = now()

    def prepare(state: WorkflowState) -> WorkflowState:
        assert_auth_cleanup_not_in_progress(state)
        existing = state.auth.certificate_secret_mutation_intent
        if existing is not None:
            matching_kind = (
                existing.event_kind is CertificateSecretMutationEventKind.REMOVED
                if removing
                else existing.event_kind
                in {
                    CertificateSecretMutationEventKind.SET,
                    CertificateSecretMutationEventKind.ROTATED,
                }
            )
            matching_request = (
                True
                if removing
                else (secret is not None and existing.request_witness == backend.request_witness(source_name, secret))
            )
            if existing.source_name != source_name or not matching_kind or not matching_request:
                assert_certificate_secret_mutation_not_in_progress(state)
                raise AssertionError("pending certificate-secret intent did not refuse")
            return state
        if not removing and source_name not in _auth_state_certificate_sources(state):
            raise CertificateSourceNotFoundError(
                translated_message="application.auth.operator.errors.certificate_source_not_found",
                context={"name": source_name},
            )
        prior_present = backend.get(source_name) is not None
        if removing and not prior_present:
            return state
        event_kind = (
            CertificateSecretMutationEventKind.REMOVED
            if removing
            else (
                CertificateSecretMutationEventKind.ROTATED if prior_present else CertificateSecretMutationEventKind.SET
            )
        )
        operation_material = "|".join(
            (
                active_bucket_id,
                source_name,
                event_kind.value,
                started_at.isoformat(),
            ),
        )
        intent = CertificateSecretMutationIntent(
            operation_id=hashlib.sha256(operation_material.encode("utf-8")).hexdigest(),
            bucket_id=active_bucket_id,
            source_name=source_name,
            event_kind=event_kind,
            started_at=started_at,
            prior_present=prior_present,
            request_witness=(None if secret is None else backend.request_witness(source_name, secret)),
        )
        return state.model_copy(
            update={
                "auth": state.auth.model_copy(
                    update={"certificate_secret_mutation_intent": intent},
                ),
            },
        )

    prepared = repository.update(prepare)
    return prepared.auth.certificate_secret_mutation_intent


def _complete_certificate_secret_mutation(
    *,
    repository: WorkflowStateRepository,
    backend: SecureStorageCertificateSecretBackend,
    intent: CertificateSecretMutationIntent,
    secret: SecretStr | None,
) -> None:
    """Complete the secure-storage effect and persist its non-secret witness."""
    if intent.completion_witness is None:
        if intent.event_kind is CertificateSecretMutationEventKind.REMOVED:
            backend.remove(intent.source_name)
            completion_witness = f"secret-absent:{intent.operation_id}"
        else:
            if secret is None:
                raise RuntimeError("certificate secret set recovery requires the retried secret")
            if intent.request_witness != backend.request_witness(intent.source_name, secret):
                raise RuntimeError("certificate secret retry does not match durable intent")
            if backend.mutation_operation_id(intent.source_name) != intent.operation_id:
                backend.set(
                    intent.source_name,
                    secret,
                    operation_id=intent.operation_id,
                    occurred_at=intent.started_at,
                )
            completion_witness = f"secret-record:{intent.operation_id}"

        def mark_completed(state: WorkflowState) -> WorkflowState:
            current = state.auth.certificate_secret_mutation_intent
            if current is None or current.operation_id != intent.operation_id:
                raise RuntimeError("certificate-secret mutation intent changed during completion")
            if current.completion_witness is not None:
                return state
            completed = current.model_copy(
                update={"completion_witness": completion_witness},
            )
            return state.model_copy(
                update={
                    "auth": state.auth.model_copy(
                        update={"certificate_secret_mutation_intent": completed},
                    ),
                },
            )

        repository.update(mark_completed)


def _finalize_certificate_secret_mutation(
    *,
    repository: WorkflowStateRepository,
    intent: CertificateSecretMutationIntent,
) -> None:
    """Atomically append the original stable event and clear its durable intent."""
    from ...domain.buckets import BucketEventType

    event_types = {
        CertificateSecretMutationEventKind.SET: BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_SET,
        CertificateSecretMutationEventKind.ROTATED: BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_ROTATED,
        CertificateSecretMutationEventKind.REMOVED: BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_REMOVED,
    }

    def finalize(state: WorkflowState) -> tuple[WorkflowState, tuple[BucketEvent, ...]]:
        current = state.auth.certificate_secret_mutation_intent
        if current is None or current.operation_id != intent.operation_id:
            raise RuntimeError("certificate-secret mutation intent changed during finalization")
        if current.completion_witness is None:
            raise RuntimeError("certificate-secret mutation has no completion witness")
        updated = state.model_copy(
            update={
                "auth": state.auth.model_copy(
                    update={"certificate_secret_mutation_intent": None},
                ),
            },
        )
        events = build_auth_bucket_events(
            bucket_id=current.bucket_id,
            events=(
                AuthBucketEventSpec(
                    event_types[current.event_kind],
                    current.source_name,
                    {
                        "name": current.source_name,
                        "backend": SECURE_STORAGE_BACKEND_LABEL,
                        "operation_id": current.operation_id,
                    },
                    current.started_at,
                ),
            ),
        )
        return updated, events

    repository.update_with_bucket_events(finalize)


__all__ = [
    "ActiveCertificateCredentials",
    "check_operator_certificate_sources",
    "list_operator_certificate_sources",
    "register_operator_certificate_source",
    "remove_operator_certificate_source",
    "remove_operator_certificate_source_secret",
    "resolve_active_certificate_credentials",
    "resolve_active_certificate_credentials_from_state",
    "resolve_certificate_source_secret",
    "select_operator_certificate_source",
    "set_operator_certificate_source_secret",
]

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

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, SecretStr

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.config import Settings, load_settings, override_settings
from ...core.time import now
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
    auth_mutation_span,
)

if TYPE_CHECKING:
    from ...domain.buckets import BucketEventType
    from ..workflow import WorkflowState


class ActiveCertificateCredentials(BaseModel):
    """The certificate path + passphrase the certificate provider must use.

    The single typed credential bundle produced by
    :func:`~application.auth.resolve_active_certificate_credentials` and
    consumed by ``certificate check``, ``auth status`` / ``auth test``,
    and ``auth login`` so every surface resolves the same certificate
    bytes and the same secret. The passphrase (when present) comes only
    from encrypted secure storage for a named source, or from the global
    single-certificate settings when no named source is selected; it is
    never persisted to workflow state.
    """

    model_config = _STRICT_FROZEN

    certificate_path: Path | None = None
    password: SecretStr | None = None
    friendly_name: str | None = None
    source_name: str | None = None


def _active_bucket_id_for_secret_resolution() -> str | None:
    """Return the active bucket id for per-source secret resolution, or ``None``.

    Unlike :func:`~application.auth._certificate_sources_operator._gate_active_bucket`, this never raises: per-source
    secret resolution is a best-effort enhancement to a pure-read probe
    (:func:`~application.auth.check_operator_certificate_sources`), not a mutation gated on
    a healthy active profile. An absent or dangling profile simply
    yields no per-source secret, falling back to the shared
    :attr:`~core.config.Settings.cadrumo_certificate_password_secret`.
    """
    from ...core import resolve_active_bucket_id

    return resolve_active_bucket_id()


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
def _certificate_mutation_span() -> Iterator[str]:
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

            assert_auth_cleanup_not_in_progress(workflow_state_repository().load())
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
            transform(_state_without_pending_cleanup(current)),
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


def _state_without_pending_cleanup(state: WorkflowState) -> WorkflowState:
    """Return ``state`` only when no resumable auth cleanup owns the bucket."""
    assert_auth_cleanup_not_in_progress(state)
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

    Each source's passphrase resolves through
    :func:`~application.auth.resolve_certificate_source_secret` first (the
    per-source :class:`~application.auth.CertificateSecretBackend`); when no per-source secret is
    registered, the probe falls back to the shared, env-only
    :attr:`~core.config.Settings.cadrumo_certificate_password_secret` —
    preserving the pre-registry single-certificate contract for sources
    that never adopted a per-source secret.

    This is a pure read: it does not require an active profile bucket
    beyond what loading workflow state needs, and it never mutates
    state or emits a bucket event.

    Returns:
        A :class:`~application.auth.CertificateSourceCheckReport` with one
        :class:`~application.auth.CertificateSourceCheckEntry` per
        registered source, sorted by name (matching
        :func:`~application.auth.list_operator_certificate_sources`).
    """
    from ..workflow import workflow_state_repository

    resolved_settings = settings or load_settings()
    state = workflow_state_repository().load()
    active_record = _active_certificate_source(state)
    active_name = active_record.name if active_record is not None else None
    sources = list_certificate_sources(state)
    active_bucket_id = _active_bucket_id_for_secret_resolution()

    entries: list[CertificateSourceCheckEntry] = []
    has_warnings = False
    for record in sources:
        per_source_secret: SecretStr | None = None
        if active_bucket_id is not None:
            per_source_secret = resolve_certificate_source_secret(name=record.name, bucket_id=active_bucket_id)
        if per_source_secret is not None:
            with override_settings(cadrumo_certificate_password_secret=per_source_secret) as scoped_settings:
                outcome = _probe_certificate_bundle(record.certificate_path, settings=scoped_settings)
        else:
            outcome = _probe_certificate_bundle(record.certificate_path, settings=resolved_settings)
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


def resolve_certificate_source_secret(*, name: str, bucket_id: str) -> SecretStr | None:
    """Return the passphrase registered for certificate source ``name``, or ``None``.

    Reads through the sole
    :class:`~application.auth.SecureStorageCertificateSecretBackend`
    scoped to ``bucket_id``; there is no keyring alternative and no
    backend selector. It never falls back to a global setting itself —
    callers that also want the
    :attr:`~core.config.Settings.cadrumo_certificate_password_secret`
    single-certificate credential compose that precedence explicitly,
    keeping it visible at the call site rather than hidden inside this
    resolver.
    """
    backend = SecureStorageCertificateSecretBackend(bucket_id=bucket_id)
    return backend.get(name)


def resolve_active_certificate_credentials(*, settings: Settings | None = None) -> ActiveCertificateCredentials:
    """Resolve the certificate path + passphrase the certificate provider must use.

    The single authority for "which certificate, and with which passphrase"
    across ``certificate check``, ``auth status`` / ``auth test``, and
    ``auth login``, so every surface consumes the same certificate bytes.
    Resolution is:

    - When a named certificate source is selected, its registered path is
      the certificate and its passphrase comes ONLY from encrypted secure
      storage. A selected source with no bound secret fails closed
      (``password`` is ``None``); it never silently falls back to the
      global :attr:`~core.config.Settings.cadrumo_certificate_password_secret`.
    - When no named source is selected, the single-certificate global
      settings (:attr:`~core.config.Settings.cadrumo_certificate_path` /
      :attr:`~core.config.Settings.cadrumo_certificate_password_secret`)
      are the credential — the pre-registry contract for an operator who
      configured one certificate through ``auth configure --file``.

    Best-effort and non-raising: an absent or dangling active profile
    yields the global settings credential rather than an error, matching
    the read-only surfaces that consume it.
    """
    resolved = settings or load_settings()
    active_record = _safe_active_certificate_source()
    if active_record is None:
        return ActiveCertificateCredentials(
            certificate_path=resolved.cadrumo_certificate_path,
            password=resolved.cadrumo_certificate_password_secret,
            friendly_name=resolved.cadrumo_certificate_friendly_name,
            source_name=None,
        )
    bucket_id = _active_bucket_id_for_secret_resolution()
    password: SecretStr | None = None
    if bucket_id is not None:
        from ...core.errors import AeatError

        try:
            password = resolve_certificate_source_secret(name=active_record.name, bucket_id=bucket_id)
        except (OSError, AeatError):
            password = None
    return ActiveCertificateCredentials(
        certificate_path=Path(active_record.certificate_path),
        password=password,
        friendly_name=active_record.friendly_name or resolved.cadrumo_certificate_friendly_name,
        source_name=active_record.name,
    )


def _safe_active_certificate_source():
    """Return the selected certificate source record, or ``None`` when unavailable.

    Non-raising: a missing or unreadable workflow state (no active
    profile, dangling pointer) resolves to ``None`` so the active-credential
    resolver falls back to the global single-certificate settings rather
    than propagating a storage error onto a read-only surface.
    """
    from ...core.errors import AeatError
    from ..workflow import workflow_state_repository

    try:
        state = workflow_state_repository().load()
    except (OSError, AeatError):
        return None
    return _active_certificate_source(state)


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
    from ...domain.buckets import BucketEventType
    from ..workflow import workflow_state_repository

    normalized_name = name.strip()
    with _certificate_mutation_span() as active_bucket_id:
        state = workflow_state_repository().load()
        if normalized_name not in _auth_state_certificate_sources(state):
            raise CertificateSourceNotFoundError(
                translated_message="application.auth.operator.errors.certificate_source_not_found",
                context={"name": normalized_name},
            )
        backend = SecureStorageCertificateSecretBackend(bucket_id=active_bucket_id)
        rotated = backend.get(normalized_name) is not None
        backend.set(normalized_name, secret)
        event_type = (
            BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_ROTATED
            if rotated
            else BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_SET
        )
        _record_certificate_secret_event(
            active_bucket_id=active_bucket_id,
            event_type=event_type,
            object_id=normalized_name,
            payload={"name": normalized_name, "backend": SECURE_STORAGE_BACKEND_LABEL},
        )
    return CertificateSourceSecretMutationResult(
        name=normalized_name,
        backend=SECURE_STORAGE_BACKEND_LABEL,
        has_secret=True,
        rotated=rotated,
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
    from ...domain.buckets import BucketEventType

    normalized_name = name.strip()
    with _certificate_mutation_span() as active_bucket_id:
        backend = SecureStorageCertificateSecretBackend(bucket_id=active_bucket_id)
        removed = backend.remove(normalized_name)
        if removed:
            _record_certificate_secret_event(
                active_bucket_id=active_bucket_id,
                event_type=BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_REMOVED,
                object_id=normalized_name,
                payload={"name": normalized_name, "backend": SECURE_STORAGE_BACKEND_LABEL},
            )
    return CertificateSourceSecretMutationResult(
        name=normalized_name,
        backend=SECURE_STORAGE_BACKEND_LABEL,
        has_secret=False,
        removed=removed,
    )


def _auth_state_certificate_sources(state: WorkflowState) -> dict[str, object]:
    return dict(_auth_state(state).certificate_sources)


def _record_certificate_secret_event(
    *,
    active_bucket_id: str,
    event_type: BucketEventType,
    object_id: str,
    payload: dict[str, str],
) -> None:
    """Append a bucket event for a certificate-secret mutation.

    Certificate secrets are NOT part of :class:`~application.workflow.WorkflowState`
    (they live only in the :class:`~application.auth.CertificateSecretBackend`), so this
    records only the bucket-event audit trail — there is no
    ``WorkflowState`` write to co-persist, unlike
    :func:`~application.auth._certificate_sources_operator._persist_with_event`.
    """
    occurred_at = now()
    from ..workflow import workflow_state_repository

    workflow_state_repository().update_with_bucket_events(
        lambda state: (
            state,
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


__all__ = [
    "ActiveCertificateCredentials",
    "check_operator_certificate_sources",
    "list_operator_certificate_sources",
    "register_operator_certificate_source",
    "remove_operator_certificate_source",
    "remove_operator_certificate_source_secret",
    "resolve_active_certificate_credentials",
    "resolve_certificate_source_secret",
    "select_operator_certificate_source",
    "set_operator_certificate_source_secret",
]

"""View session custody and publication."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager, ExitStack
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, SkipValidation, TypeAdapter

from ...core.auth_provider import AuthProviderKind
from ...core.errors.hierarchy import (
    InternalInvariantError,
    ViewCaptureIdentityMismatchError,
)
from ...core.logging import get_logger
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import OperationEffect
from ..auth_credentials import ActiveCertificateCredentials
from ..workflow.persistence import workflow_state_repository
from .acquisition_lock import (
    AuthAcquisitionLockedError,
    acquire_auth_acquisition_lock,
    auth_lock_ttl_seconds,
)
from .certificate_secret_backend import CertificateSecretBackendFactory
from .operator_scope import (
    active_profile_storage_span,
    assert_auth_recovery_not_in_progress,
    auth_mutation_span,
)
from .operator_scope_ports import OperatorScopePorts
from .protocols import (
    BrowserContextPort,
    BrowserContextProvisioner,
    BrowserSessionFactoryPort,
    SessionWriteStage,
    ViewLoginSessionFactoryPort,
)
from .providers import AuthProvider
from .session_types import AeatSession
from .sessions import (
    AuthProfileIdentityMismatchError,
    AuthSessionUnavailableError,
    ClaveCredentialsIncompleteError,
    PersistedSessionProbeProvider,
    assert_session_identity_matches_expected,
    build_provider,
    ensure_authenticated_aeat_session,
    get_session_store,
    prepare_clave_auth,
    provider_lifecycle,
    resolve_provider_kind,
    storage_state_paths,
)

if TYPE_CHECKING:
    from ...core.config import Settings
    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext

_logger = get_logger(__name__)
_JSON_OBJECT = TypeAdapter(dict[str, object])


@runtime_checkable
class _ViewContextProvisioningProvider(Protocol):
    """Provider whose login credential a view context presents from its construction."""

    def view_context_provisioner(self) -> BrowserContextProvisioner: ...


class ViewSessionBaseline(BaseModel):
    """The stored session a running view was seeded from or last published.

    A view publication overwrites custody only while the stored digest still
    equals ``storage_state_sha256``. ``None`` records that nothing was stored,
    so a publication then requires custody to be still empty.
    """

    model_config = STRICT_FROZEN_CONFIG

    provider_kind: AuthProviderKind
    storage_state_sha256: str | None = Field(min_length=1)


class ViewSessionSeed(BaseModel):
    """Encrypted-custody storage state a view context is constructed from.

    ``storage_state`` holds browser cookies and local storage. It is passed only
    to ``new_context(storage_state=...)`` and is excluded from ``repr``. It is
    ``None`` when no stored session passed the provider's verification: the view
    then opens signed out, and the person signs in inside it.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    baseline: ViewSessionBaseline
    storage_state: SkipValidation[Mapping[str, object] | None] = Field(repr=False)

    @property
    def signed_in(self) -> bool:
        """Whether the view opens with a session the provider verified."""
        return self.storage_state is not None


class ViewSessionPublicationOutcome(StrEnum):
    """Closed outcomes of publishing a view's storage state back to custody."""

    PUBLISHED = "published"
    UNCHANGED = "unchanged"
    KEPT_NEWER = "kept-newer"
    VERIFICATION_FAILED = "verification-failed"
    IDENTITY_MISMATCH = "identity-mismatch"
    """AEAT shows the captured session signed in as a taxpayer other than the profile's."""
    UNKNOWN = "unknown"


class ViewSessionPublication(BaseModel):
    """Result of one view publication.

    ``baseline`` is the precondition for any later publication by the same
    view: the new stored digest after ``PUBLISHED``, otherwise the baseline the
    view already held.
    """

    model_config = STRICT_FROZEN_CONFIG

    outcome: ViewSessionPublicationOutcome
    baseline: ViewSessionBaseline


@runtime_checkable
class _ViewCaptureProvider(Protocol):
    """Provider that authors and proves its own record for a view's captured storage state."""

    async def adopt_view_capture(self, storage_state: Mapping[str, object]) -> AeatSession: ...


#: Providers whose own login can run inside the view, as assistance the person watches.
VIEW_ASSISTED_PROVIDERS = frozenset({AuthProviderKind.CERTIFICATE, AuthProviderKind.CLAVE_MOVIL})


async def resume_view_session(
    settings: Settings,
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_scope_ports: OperatorScopePorts,
    profile_decode_context: ProfileDecodeContext,
    effect_guard: Callable[[], AbstractAsyncContextManager[None]],
    on_session_write: Callable[[OperationEffect], Awaitable[None]],
) -> ViewSessionSeed:
    """Resume the configured provider's stored session for a view, or open the view signed out.

    The provider's own persisted-session probe proves the stored record,
    identity gates included, and never falls back to a fresh login: a view
    whose custody holds no valid session opens signed out, and the person
    signs in inside it, by hand or with the provider's assistance. A probe's
    refreshed record is published under ``effect_guard`` exactly as a sync
    publishes it; a refused probe stages its invalidation and that stage is
    discarded, so opening a view deletes nothing. No acquisition lock is held
    once this returns.
    """
    with active_profile_storage_span(settings, operator_scope_ports=operator_scope_ports) as bucket_id:
        if bucket_id is None:
            raise AuthSessionUnavailableError(
                translated_message="application.auth.sessions.errors.no_session",
            )
        with auth_mutation_span(
            settings=settings,
            bucket_id=bucket_id,
            operator_scope_ports=operator_scope_ports,
        ):
            assert_auth_recovery_not_in_progress(workflow_state_repository().load())
            kind = resolve_provider_kind(
                settings,
                None,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_scope_ports=operator_scope_ports,
            )
            store = get_session_store()
            path = storage_state_paths(kind).storage_state
            signed_out = ViewSessionSeed(
                baseline=ViewSessionBaseline(
                    provider_kind=kind,
                    storage_state_sha256=store.durable_storage_state_sha256(path),
                ),
                storage_state=None,
            )
            try:
                settings, expected_identity = prepare_clave_auth(
                    settings,
                    kind,
                    operator_scope_ports=operator_scope_ports,
                    profile_decode_context=profile_decode_context,
                    logs_in=False,
                )
            except (AuthProfileIdentityMismatchError, ClaveCredentialsIncompleteError):
                return signed_out
            with store.defer_writes() as staged:
                provider = build_provider(
                    settings,
                    kind,
                    certificate_secret_backend_factory=certificate_secret_backend_factory,
                    browser_session_factory=browser_session_factory,
                    certificate_credentials=None,
                    operator_scope_ports=operator_scope_ports,
                )
                if not await _probe_stored_view_session(provider, expected_identity=expected_identity):
                    return signed_out
                if staged.has_changes:
                    async with effect_guard():
                        await on_session_write(OperationEffect.UNKNOWN)
                        staged.publish()
                        await on_session_write(OperationEffect.UPDATED)
            persisted = store.load(path)
            if persisted is None:
                return signed_out
            storage_state = persisted.storage_state
            return ViewSessionSeed(
                baseline=ViewSessionBaseline(
                    provider_kind=kind,
                    storage_state_sha256=store.storage_state_sha256(storage_state),
                ),
                storage_state=storage_state,
            )


def view_context_provisioner(
    settings: Settings,
    *,
    baseline: ViewSessionBaseline,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_scope_ports: OperatorScopePorts,
) -> BrowserContextProvisioner | None:
    """Return what a view context must present at construction for the configured provider, if anything.

    A certificate session is valid only while the browser presents the same
    client certificate, and a certificate login in the view needs it too, so
    the view context carries it exactly as the provider's own contexts do,
    signed in or not. Cl@ve sessions live in the storage state alone.
    """
    if baseline.provider_kind is not AuthProviderKind.CERTIFICATE:
        return None
    with active_profile_storage_span(settings, operator_scope_ports=operator_scope_ports) as bucket_id:
        if bucket_id is None:
            raise AuthSessionUnavailableError(
                translated_message="application.auth.sessions.errors.no_session",
            )
        provider = build_provider(
            settings,
            baseline.provider_kind,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            browser_session_factory=browser_session_factory,
            certificate_credentials=None,
            operator_scope_ports=operator_scope_ports,
        )
        if not isinstance(provider, _ViewContextProvisioningProvider):
            raise InternalInvariantError("the certificate provider cannot provision a view context")
        return provider.view_context_provisioner()


async def publish_view_session_state(
    settings: Settings,
    *,
    baseline: ViewSessionBaseline,
    view_context: BrowserContextPort,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_scope_ports: OperatorScopePorts,
    profile_decode_context: ProfileDecodeContext,
    effect_guard: Callable[[], AbstractAsyncContextManager[None]],
    on_session_write: Callable[[OperationEffect], Awaitable[None]],
    certificate_credentials: ActiveCertificateCredentials | None = None,
    operation: str = "live-sede-view-close",
) -> ViewSessionPublication:
    """Capture a view's storage state and publish it to custody after provider verification.

    This publishes a login the person made in the view, by hand with any
    provider, and the view's session when it closes. The view context is
    captured first. Publication then requires, in order: the stored digest
    still equals ``baseline``; the capture differs from it; the acquisition
    lock is free; the configured provider authors its own record for the
    capture and proves it with its own persisted-session probe, identity gates
    included, in a browser of its own; the session identity aligns with the
    active profile; and the stored digest is still unchanged under the lock.
    Only then are the staged writes published under ``effect_guard``, between
    the ``UNKNOWN`` and ``UPDATED`` effect reports.

    A refused verification publishes and deletes nothing. A lock held by a
    live acquisition defers to it, as does any stored digest other than the
    baseline. A failure between the two effect reports returns ``UNKNOWN``;
    the journal keeps the ``UNKNOWN`` report as the authority on that write.
    Cancellation in that window propagates with the same report standing.
    """
    captured = await view_context.storage_state()
    with active_profile_storage_span(settings, operator_scope_ports=operator_scope_ports) as bucket_id:
        if bucket_id is None:
            raise AuthSessionUnavailableError(
                translated_message="application.auth.sessions.errors.no_session",
            )
        with auth_mutation_span(
            settings=settings,
            bucket_id=bucket_id,
            operator_scope_ports=operator_scope_ports,
        ):
            assert_auth_recovery_not_in_progress(workflow_state_repository().load())
            return await _publish_view_session_state_locked(
                settings,
                baseline=baseline,
                captured=captured,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                browser_session_factory=browser_session_factory,
                operator_scope_ports=operator_scope_ports,
                profile_decode_context=profile_decode_context,
                effect_guard=effect_guard,
                on_session_write=on_session_write,
                certificate_credentials=certificate_credentials,
                operation=operation,
            )


async def _publish_view_session_state_locked(
    settings: Settings,
    *,
    baseline: ViewSessionBaseline,
    captured: Mapping[str, object],
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_scope_ports: OperatorScopePorts,
    profile_decode_context: ProfileDecodeContext,
    effect_guard: Callable[[], AbstractAsyncContextManager[None]],
    on_session_write: Callable[[OperationEffect], Awaitable[None]],
    certificate_credentials: ActiveCertificateCredentials | None,
    operation: str,
) -> ViewSessionPublication:
    kind = baseline.provider_kind
    store = get_session_store()
    path = storage_state_paths(kind).storage_state
    if store.durable_storage_state_sha256(path) != baseline.storage_state_sha256:
        return _standing(ViewSessionPublicationOutcome.KEPT_NEWER, baseline)
    if store.storage_state_sha256(captured) == baseline.storage_state_sha256:
        return _standing(ViewSessionPublicationOutcome.UNCHANGED, baseline)
    try:
        settings, expected_identity = prepare_clave_auth(
            settings,
            kind,
            operator_scope_ports=operator_scope_ports,
            profile_decode_context=profile_decode_context,
            logs_in=False,
        )
    except (AuthProfileIdentityMismatchError, ClaveCredentialsIncompleteError):
        return _standing(ViewSessionPublicationOutcome.VERIFICATION_FAILED, baseline)
    with ExitStack() as held:
        try:
            held.enter_context(
                acquire_auth_acquisition_lock(
                    settings,
                    kind,
                    ttl_seconds=auth_lock_ttl_seconds(settings, kind),
                    operation=operation,
                )
            )
        except AuthAcquisitionLockedError:
            # A live acquisition publishes what it proves; the view's capture yields to it.
            return _standing(ViewSessionPublicationOutcome.KEPT_NEWER, baseline)
        with store.defer_writes() as staged:
            provider = build_provider(
                settings,
                kind,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                browser_session_factory=browser_session_factory,
                certificate_credentials=certificate_credentials,
                operator_scope_ports=operator_scope_ports,
            )
            refused = await _adopt_view_capture(provider, captured, expected_identity=expected_identity)
            if refused is not None:
                return _standing(refused, baseline)
            return await _publish_staged_view_session(
                staged,
                kind=kind,
                baseline=baseline,
                effect_guard=effect_guard,
                on_session_write=on_session_write,
            )


async def assist_view_login(
    settings: Settings,
    *,
    baseline: ViewSessionBaseline,
    login_session_factory: ViewLoginSessionFactoryPort,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_scope_ports: OperatorScopePorts,
    profile_decode_context: ProfileDecodeContext,
    effect_guard: Callable[[], AbstractAsyncContextManager[None]],
    on_session_write: Callable[[OperationEffect], Awaitable[None]],
    on_login_verified: Callable[[], None],
    operation: str = "live-sede-view-login",
) -> ViewSessionPublication:
    """Run the configured provider's own login inside a signed-out view and publish it at once.

    The login is the canonical fresh acquisition of
    :func:`ensure_authenticated_aeat_session`, under its acquisition lock, with
    ``login_session_factory`` lending it the view's own context: its pages show
    in the person's panel. Its writes stay staged. The caller may cancel it
    until ``on_login_verified`` is called, which happens once the provider has
    verified the login and the session identity matches the active profile;
    a cancelled login publishes and deletes nothing, and leaves its page to
    the person. The staged session is then published under the acquisition
    lock and ``effect_guard``, exactly as :func:`publish_view_session_state`
    publishes, and only while the stored digest still equals ``baseline``.

    A login whose identity does not match the active profile, or whose Cl@ve
    credentials are incomplete, ends ``VERIFICATION_FAILED``. A held lock ends
    ``KEPT_NEWER``. Any other login failure propagates.
    """
    kind = baseline.provider_kind
    if kind not in VIEW_ASSISTED_PROVIDERS:
        raise InternalInvariantError("only certificate and Cl@ve Movil logins run inside the view")
    store = get_session_store()
    with store.defer_writes() as staged:
        try:
            await ensure_authenticated_aeat_session(
                settings,
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                kind=kind,
                fresh=True,
                operation=operation,
                browser_session_factory=login_session_factory,
                operator_scope_ports=operator_scope_ports,
                profile_decode_context=profile_decode_context,
            )
        except (AuthProfileIdentityMismatchError, ClaveCredentialsIncompleteError):
            return _standing(ViewSessionPublicationOutcome.VERIFICATION_FAILED, baseline)
        except AuthAcquisitionLockedError:
            return _standing(ViewSessionPublicationOutcome.KEPT_NEWER, baseline)
        on_login_verified()
        with active_profile_storage_span(settings, operator_scope_ports=operator_scope_ports) as bucket_id:
            if bucket_id is None:
                raise AuthSessionUnavailableError(
                    translated_message="application.auth.sessions.errors.no_session",
                )
            with (
                auth_mutation_span(
                    settings=settings,
                    bucket_id=bucket_id,
                    operator_scope_ports=operator_scope_ports,
                ),
                ExitStack() as held,
            ):
                try:
                    held.enter_context(
                        acquire_auth_acquisition_lock(
                            settings,
                            kind,
                            ttl_seconds=auth_lock_ttl_seconds(settings, kind),
                            operation=operation,
                        )
                    )
                except AuthAcquisitionLockedError:
                    return _standing(ViewSessionPublicationOutcome.KEPT_NEWER, baseline)
                return await _publish_staged_view_session(
                    staged,
                    kind=kind,
                    baseline=baseline,
                    effect_guard=effect_guard,
                    on_session_write=on_session_write,
                )


def _standing(outcome: ViewSessionPublicationOutcome, baseline: ViewSessionBaseline) -> ViewSessionPublication:
    """Return an outcome that leaves custody and the view's baseline as they were."""
    return ViewSessionPublication(outcome=outcome, baseline=baseline)


async def _publish_staged_view_session(
    staged: SessionWriteStage,
    *,
    kind: AuthProviderKind,
    baseline: ViewSessionBaseline,
    effect_guard: Callable[[], AbstractAsyncContextManager[None]],
    on_session_write: Callable[[OperationEffect], Awaitable[None]],
) -> ViewSessionPublication:
    """Publish a view's verified, staged session while custody still holds ``baseline``.

    The caller holds the acquisition lock and the open stage.
    """
    store = get_session_store()
    path = storage_state_paths(kind).storage_state
    if store.durable_storage_state_sha256(path) != baseline.storage_state_sha256:
        return _standing(ViewSessionPublicationOutcome.KEPT_NEWER, baseline)
    async with effect_guard():
        await on_session_write(OperationEffect.UNKNOWN)
        try:
            staged.publish()
            await on_session_write(OperationEffect.UPDATED)
        except Exception as exc:
            _logger.warning(
                "view session publication interrupted failure=%s",
                type(exc).__name__,
                exc_info=True,
            )
            return _standing(ViewSessionPublicationOutcome.UNKNOWN, baseline)
    published = store.durable_storage_state_sha256(path)
    if published is None:
        raise InternalInvariantError("a published view session left no stored storage state")
    return ViewSessionPublication(
        outcome=ViewSessionPublicationOutcome.PUBLISHED,
        baseline=ViewSessionBaseline(provider_kind=kind, storage_state_sha256=published),
    )


async def _probe_stored_view_session(provider: AuthProvider, *, expected_identity: str | None) -> bool:
    """Prove the stored record with the provider's persisted-session probe, never a fresh login."""
    async with provider_lifecycle(provider):
        if not isinstance(provider, PersistedSessionProbeProvider):
            return False
        try:
            session, assertion = await provider.probe_persisted_session(target_url=None)
        except Exception as exc:
            _logger.debug(
                "resume_view_session: provider refused the stored session failure=%s",
                type(exc).__name__,
                exc_info=True,
            )
            return False
    return bool(getattr(assertion, "is_valid", False)) and _identity_aligns(session, expected_identity)


async def _adopt_view_capture(
    provider: AuthProvider,
    captured: Mapping[str, object],
    *,
    expected_identity: str | None,
) -> ViewSessionPublicationOutcome | None:
    """Let the provider author and prove its own record for a view's capture.

    Returns the refusal, or ``None`` once the provider adopted the capture. A
    provider that cannot adopt a capture cannot verify it, so its view state
    is never published; a capture AEAT shows signed in as another taxpayer is
    refused as ``IDENTITY_MISMATCH``.
    """
    async with provider_lifecycle(provider):
        if not isinstance(provider, _ViewCaptureProvider):
            return ViewSessionPublicationOutcome.VERIFICATION_FAILED
        try:
            session = await provider.adopt_view_capture(captured)
        except ViewCaptureIdentityMismatchError:
            _logger.debug("publish_view_session_state: the captured state is signed in as another taxpayer")
            return ViewSessionPublicationOutcome.IDENTITY_MISMATCH
        except Exception as exc:
            _logger.debug(
                "publish_view_session_state: provider refused the captured state failure=%s",
                type(exc).__name__,
                exc_info=True,
            )
            return ViewSessionPublicationOutcome.VERIFICATION_FAILED
    if not _identity_aligns(session, expected_identity):
        return ViewSessionPublicationOutcome.VERIFICATION_FAILED
    return None


def _identity_aligns(session: AeatSession, expected_identity: str | None) -> bool:
    try:
        assert_session_identity_matches_expected(session.identity_nif, expected_identity)
    except AuthProfileIdentityMismatchError:
        return False
    return True

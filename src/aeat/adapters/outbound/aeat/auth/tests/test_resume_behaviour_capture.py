"""Behaviour-capture harness for ``_resume_from_storage_state_locked``.

This module pins the full observable contract of
:meth:`AeatAuthenticator._resume_from_storage_state_locked` before the
function is refactored, so any drift in validation-gate order, refusal
reason codes, exception types, the cleanup call sequence, the rebuilt
:class:`AeatSession` fields, or the ``model_copy`` timestamp update is
caught as a hard failure.

Every seam here is a real in-process implementation of the
:class:`BrowserSessionLike` / :class:`BrowserContextLike` Protocols (the
hexagonal boundary the adapter is designed around) — there are no mocks,
stubs, or monkeypatches. Failures (a rejected live probe, a marker
mismatch, a capture write failure) are injected by feeding the real
control flow inputs that deterministically drive it down each branch.

Paths covered:

* The four ordered validation gates (storage_state hash, idle deadline,
  certificate thumbprint, certificate subject), each asserted by its
  stable redacted ``reason`` code on the raised
  :class:`_PersistedSessionInvalidError`, plus an explicit gate-order
  proof that the earliest-failing gate wins when several trip at once.
* A successful resume: the rebuilt :class:`AeatSession` fields, the
  ``model_copy``-updated ``authenticated_at`` / ``idle_deadline``, and the
  ``_browser_session`` / ``_context`` / ``_active_session`` assignment plus
  storage capture.
* The ``_PersistedSessionInvalidError`` (failed live probe) path: context
  closed, owned browser session closed, persisted state invalidated, error
  re-raised.
* The general-exception path (a context-marker mismatch): ``resume_failed``
  flag drives ``_raise_invalid_persisted_state`` with the ``resume_failed``
  reason code, context closed, owned session closed.
* The ``_capture_storage_state_locked`` failure cleanup path:
  ``_drop_context`` runs, ``_browser_session`` / ``_active_session`` are
  nulled, and the original error re-raises.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from ......core.config import Settings
from .. import (
    AEAT_SESSION_IDLE_TTL,
    AeatAuthenticator,
    AeatLoginAssertionError,
    BrowserSessionLike,
    LoadedCertificate,
    _session_store,
)
from .._authenticator_types import BrowserSessionFactory, _PersistedSessionInvalidError
from ._authenticator_support import (
    _HandshakeVerifier,
    _load_test_session,
    _RecordingBrowserContext,
    _RecordingBrowserSession,
    _seed_persisted_session,
    _store_test_session,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _reason_code(exc: AeatLoginAssertionError) -> str | None:
    context = getattr(exc, "context", None)
    if isinstance(context, dict):
        reason = context.get("reason")
        if isinstance(reason, str):
            return reason
    return None


class _ClosableRecordingBrowserSession(_RecordingBrowserSession):
    """Recording session that also records ``close()`` for owns_session proofs.

    The base :class:`_RecordingBrowserSession` deliberately omits a
    ``close`` coroutine; ``_close_browser_session`` probes for the method
    and no-ops when absent. Owns-session teardown paths must assert the
    close actually fired, so this subclass supplies a recorded coroutine.
    """

    def __init__(self, cert_ok: bool = True) -> None:
        super().__init__(cert_ok=cert_ok)
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class _MarkerMismatchBrowserSession:
    """Real ``BrowserSessionLike`` whose context omits the certificate marker.

    Drives ``_assert_context_marker`` into raising a plain
    :class:`AeatLoginAssertionError` (not ``_PersistedSessionInvalidError``),
    so the general-exception branch of the resume flow runs.
    """

    def __init__(self) -> None:
        self.created: list[_UnmarkedContext] = []
        self.closed = False

    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: dict[str, object] | None = None,
    ) -> _UnmarkedContext:
        del provisioner, storage_state_path, storage_state
        ctx = _UnmarkedContext()
        self.created.append(ctx)
        return ctx

    async def close(self) -> None:
        self.closed = True


class _UnmarkedContext:
    """Context that never tags itself with the certificate marker."""

    def __init__(self) -> None:
        self.closed = False

    async def new_page(self) -> object:  # pragma: no cover - never reached
        raise AssertionError("new_page must not run when the marker check fails")

    async def storage_state(self) -> dict[str, object]:  # pragma: no cover
        return {"cookies": [], "origins": []}

    async def close(self) -> None:
        self.closed = True


class _CaptureFailingContext(_RecordingBrowserContext):
    """Recording context whose ``storage_state()`` fails the capture step.

    The live probe still succeeds (the marker is honoured and ``new_page``
    returns a 200), so the resume flow reaches
    ``_capture_storage_state_locked`` before failing there.
    """

    async def storage_state(self) -> dict[str, object]:
        raise RuntimeError("storage_state capture failed")


class _CaptureFailingBrowserSession:
    """Session that yields a context whose capture step raises."""

    def __init__(self, cert: LoadedCertificate, storage_state: dict[str, object]) -> None:
        self._cert = cert
        self._storage_state = storage_state
        self.created: list[_CaptureFailingContext] = []
        self.closed = False

    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: dict[str, object] | None = None,
    ) -> _CaptureFailingContext:
        del provisioner, storage_state_path, storage_state
        ctx = _CaptureFailingContext(self._cert, storage_state=self._storage_state)
        self.created.append(ctx)
        return ctx

    async def close(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# Validation-gate refusals: reason code + persisted-invalid error type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutate", "expected_reason"),
    [
        ("hash", "storage_hash_mismatch"),
        ("idle", "idle_deadline_expired"),
        ("thumbprint", "certificate_thumbprint_mismatch"),
        ("subject", "certificate_subject_mismatch"),
    ],
    ids=["hash-gate", "idle-gate", "thumbprint-gate", "subject-gate"],
)
async def test_validation_gate_raises_expected_reason(
    tmp_path: Path,
    _settings_factory,
    mutate: str,
    expected_reason: str,
) -> None:
    settings, storage_state_path, _cert = await _seed_persisted_session(tmp_path, _settings_factory)
    metadata = dict(_load_test_session(storage_state_path).metadata)
    if mutate == "hash":
        metadata["storage_state_sha256"] = "0" * 64
    elif mutate == "idle":
        metadata["idle_deadline"] = (datetime.now(UTC) - timedelta(days=400)).isoformat()
    elif mutate == "thumbprint":
        metadata["certificate_thumbprint"] = "f" * 64
    else:
        metadata["certificate_subject"] = "CN=DIFFERENT"
    _store_test_session(storage_state_path, metadata=metadata)

    auth = AeatAuthenticator(settings, handshake_verifier=_HandshakeVerifier())
    browser_session = _RecordingBrowserSession(cert_ok=True)

    with pytest.raises(_PersistedSessionInvalidError) as exc_info:
        await auth.resume_from_storage_state(
            storage_state_path,
            browser_session=cast(BrowserSessionLike, browser_session),
        )

    assert _reason_code(exc_info.value) == expected_reason
    # No browser context is ever built for a metadata-gate refusal.
    assert browser_session.created == []
    assert not _session_store.exists(storage_state_path)


@pytest.mark.asyncio
async def test_validation_gate_order_earliest_wins(
    tmp_path: Path,
    _settings_factory,
) -> None:
    """When every gate would trip, the hash gate (first) must win.

    Proves gate ORDER: the metadata is mutated so the storage-hash,
    idle-deadline, thumbprint, and subject checks would each fail. Only
    the earliest check's reason code may surface.
    """
    settings, storage_state_path, _cert = await _seed_persisted_session(tmp_path, _settings_factory)
    metadata = dict(_load_test_session(storage_state_path).metadata)
    metadata["storage_state_sha256"] = "0" * 64
    metadata["idle_deadline"] = (datetime.now(UTC) - timedelta(days=400)).isoformat()
    metadata["certificate_thumbprint"] = "f" * 64
    metadata["certificate_subject"] = "CN=DIFFERENT"
    _store_test_session(storage_state_path, metadata=metadata)

    auth = AeatAuthenticator(settings, handshake_verifier=_HandshakeVerifier())
    browser_session = _RecordingBrowserSession(cert_ok=True)

    with pytest.raises(_PersistedSessionInvalidError) as exc_info:
        await auth.resume_from_storage_state(
            storage_state_path,
            browser_session=cast(BrowserSessionLike, browser_session),
        )

    assert _reason_code(exc_info.value) == "storage_hash_mismatch"


@pytest.mark.asyncio
async def test_validation_gate_order_idle_before_thumbprint(
    tmp_path: Path,
    _settings_factory,
) -> None:
    """With the hash gate satisfied, the idle gate precedes the thumbprint gate."""
    settings, storage_state_path, _cert = await _seed_persisted_session(tmp_path, _settings_factory)
    metadata = dict(_load_test_session(storage_state_path).metadata)
    # Leave storage_state_sha256 valid so the hash gate passes.
    metadata["idle_deadline"] = (datetime.now(UTC) - timedelta(days=400)).isoformat()
    metadata["certificate_thumbprint"] = "f" * 64
    metadata["certificate_subject"] = "CN=DIFFERENT"
    _store_test_session(storage_state_path, metadata=metadata)

    auth = AeatAuthenticator(settings, handshake_verifier=_HandshakeVerifier())
    browser_session = _RecordingBrowserSession(cert_ok=True)

    with pytest.raises(_PersistedSessionInvalidError) as exc_info:
        await auth.resume_from_storage_state(
            storage_state_path,
            browser_session=cast(BrowserSessionLike, browser_session),
        )

    assert _reason_code(exc_info.value) == "idle_deadline_expired"


# ---------------------------------------------------------------------------
# Successful resume: rebuilt session, model_copy timestamps, state assignment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_resume_rebuilds_session_and_sets_state(
    tmp_path: Path,
    _settings_factory,
) -> None:
    settings, storage_state_path, cert = await _seed_persisted_session(tmp_path, _settings_factory)
    seeded = _load_test_session(storage_state_path)
    seeded_authenticated_at = datetime.fromisoformat(str(seeded.metadata["authenticated_at"]))

    browser_session = _RecordingBrowserSession(cert_ok=True)
    auth = AeatAuthenticator(settings, handshake_verifier=_HandshakeVerifier())

    resumed = await auth.resume_from_storage_state(
        storage_state_path,
        browser_session=cast(BrowserSessionLike, browser_session),
    )

    # Rebuilt AeatSession fields are sourced from the persisted metadata + cert.
    assert resumed.provider_kind == auth.kind
    assert resumed.certificate_thumbprint == cert.sha256_thumbprint
    assert resumed.certificate_subject == cert.subject
    assert resumed.storage_state_path == storage_state_path

    # model_copy advanced both timestamps off the probe attempt time.
    assert resumed.authenticated_at > seeded_authenticated_at
    assert resumed.idle_deadline == resumed.authenticated_at + AEAT_SESSION_IDLE_TTL

    # On success the authenticator adopts the live session/context/state.
    assert auth._active_session == resumed
    assert auth._context is browser_session.created[-1]
    assert auth._browser_session is cast(BrowserSessionLike, browser_session)

    # Storage was re-captured under the resumed session.
    assert _session_store.exists(storage_state_path)


# ---------------------------------------------------------------------------
# _PersistedSessionInvalidError path: close context, close owned session, re-raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_live_probe_closes_context_and_owned_session(
    tmp_path: Path,
    _settings_factory,
) -> None:
    """owns_session True (session resolved via factory): close context + session."""
    settings, storage_state_path, _cert = await _seed_persisted_session(tmp_path, _settings_factory)

    browser_session = _ClosableRecordingBrowserSession(cert_ok=False)
    auth = AeatAuthenticator(
        settings,
        handshake_verifier=_HandshakeVerifier(),
        browser_session_factory=_factory_returning(browser_session),
    )

    with pytest.raises(_PersistedSessionInvalidError) as exc_info:
        # No browser_session argument => owns_session True => session is closed.
        await auth.resume_from_storage_state(storage_state_path)

    # The failed-probe error is the directly-raised _PersistedSessionInvalidError
    # (verification_failed translated_message), NOT the redacted reason-code form;
    # the except handler invalidates state and re-raises this exact instance.
    assert str(exc_info.value) == "persisted AEAT browser session failed live verification"
    assert exc_info.value.translated_message == (
        "adapters.auth.authenticator.errors.persisted_session_verification_failed"
    )
    assert _reason_code(exc_info.value) is None
    assert browser_session.created[-1].closed is True
    assert browser_session.closed is True
    assert not _session_store.exists(storage_state_path)


@pytest.mark.asyncio
async def test_failed_live_probe_with_injected_session_does_not_close_session(
    tmp_path: Path,
    _settings_factory,
) -> None:
    """When the caller injects the browser session, owns_session is False.

    The context is still closed, but the externally-owned session must
    NOT be torn down by resume.
    """
    settings, storage_state_path, _cert = await _seed_persisted_session(tmp_path, _settings_factory)

    browser_session = _ClosableRecordingBrowserSession(cert_ok=False)
    auth = AeatAuthenticator(settings, handshake_verifier=_HandshakeVerifier())

    with pytest.raises(_PersistedSessionInvalidError) as exc_info:
        await auth.resume_from_storage_state(
            storage_state_path,
            browser_session=cast(BrowserSessionLike, browser_session),
        )

    assert str(exc_info.value) == "persisted AEAT browser session failed live verification"
    assert exc_info.value.translated_message == (
        "adapters.auth.authenticator.errors.persisted_session_verification_failed"
    )
    assert browser_session.created[-1].closed is True
    assert browser_session.closed is False
    assert not _session_store.exists(storage_state_path)


# ---------------------------------------------------------------------------
# General-exception path: resume_failed -> _raise_invalid_persisted_state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_general_exception_marks_resume_failed_and_invalidates(
    tmp_path: Path,
    _settings_factory,
) -> None:
    settings, storage_state_path, _cert = await _seed_persisted_session(tmp_path, _settings_factory)

    browser_session = _MarkerMismatchBrowserSession()
    auth = AeatAuthenticator(
        settings,
        handshake_verifier=_HandshakeVerifier(),
        browser_session_factory=_factory_returning(browser_session),
    )

    with pytest.raises(_PersistedSessionInvalidError) as exc_info:
        await auth.resume_from_storage_state(storage_state_path)

    # The general-exception tail re-raises through _raise_invalid_persisted_state
    # carrying the resume_failed reason (distinct from the live-probe reason).
    assert _reason_code(exc_info.value) == "resume_failed"
    assert browser_session.created[-1].closed is True
    assert browser_session.closed is True
    assert not _session_store.exists(storage_state_path)


# ---------------------------------------------------------------------------
# Capture-failure cleanup path: _drop_context + null state + re-raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_capture_failure_drops_context_and_nulls_state(
    tmp_path: Path,
    _settings_factory,
) -> None:
    settings, storage_state_path, cert = await _seed_persisted_session(tmp_path, _settings_factory)
    persisted_storage_state = dict(_load_test_session(storage_state_path).storage_state)

    browser_session = _CaptureFailingBrowserSession(cert, persisted_storage_state)
    auth = AeatAuthenticator(
        settings,
        handshake_verifier=_HandshakeVerifier(),
        browser_session_factory=_factory_returning(browser_session),
    )

    with pytest.raises(RuntimeError, match="storage_state capture failed"):
        await auth.resume_from_storage_state(storage_state_path)

    # Cleanup: context dropped (closed + nulled), owned session closed,
    # active session + browser session nulled. The original error re-raised.
    assert browser_session.created[-1].closed is True
    assert auth._context is None
    assert auth._browser_session is None
    assert auth._active_session is None
    assert browser_session.closed is True


def _factory_returning(session: object) -> BrowserSessionFactory:
    """Return an async browser-session factory yielding ``session``.

    Mirrors the production :class:`BrowserSessionFactory` Protocol shape
    (an async callable taking the resolved :class:`Settings`). Used so the
    resume flow treats the session as authenticator-owned
    (``owns_session`` True), exercising the owned-teardown branches.
    """

    async def _factory(settings: Settings) -> BrowserSessionLike:
        del settings
        return cast(BrowserSessionLike, session)

    return cast(BrowserSessionFactory, _factory)

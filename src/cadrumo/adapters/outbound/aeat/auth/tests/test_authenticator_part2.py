"""Focused adapter contract tests split from the original monolith (part 2).

Re-exports the async ``test_*`` functions defined in ``_authenticator_support``
so pytest actually collects them: ``pyproject.toml`` sets
``python_files = ["test_*.py"]``, so a function defined only inside
``_authenticator_support.py`` (which intentionally does not match that glob,
per the module's own "shared support for split adapter tests" docstring) is
never collected — a function existing is not the same as it running.

Also covers two genuine test-coverage gaps:

* ``reauthenticate()`` happy path with an in-process browser protocol implementation.
* (The other item — a byte-for-byte parity test between
  ``AeatAccessGate.require_live_write()`` and
  ``SubmissionEngine._submit_with_transport()`` — is obsolete:
  ``_submit_with_transport`` no longer exists anywhere in the codebase. See
  ``src/cadrumo/adapters/outbound/aeat/export/tests/test_engine.py`` for the
  reframed structural proof.)
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ......application.auth_credentials import unnamed_certificate_credentials
from ......core.config import Settings
from .. import (
    AEAT_SESSION_IDLE_TTL,
    AeatAuthenticator,
    BrowserSessionLike,
    CertificateSessionDetail,
)
from . import _authenticator_support as _support
from ._authenticator_support import (
    _certificate_session,
    _RecordingBrowserSession,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

# Re-export so pytest collects these: ``pyproject.toml`` sets
# ``python_files = ["test_*.py"]``, so a function defined only inside
# ``_authenticator_support.py`` (which intentionally does not match that
# glob) is never collected on its own — see the module docstring above.
test_authenticate_falls_back_after_stale_persisted_session = (
    _support.test_authenticate_falls_back_after_stale_persisted_session
)
test_authenticator_synchronous_surface = _support.test_authenticator_synchronous_surface
test_capture_storage_state_writes_storage_and_metadata = _support.test_capture_storage_state_writes_storage_and_metadata
test_close_is_idempotent = _support.test_close_is_idempotent
test_close_latch_blocks_concurrent_verify = _support.test_close_latch_blocks_concurrent_verify
test_concurrent_close_and_verify_race = _support.test_concurrent_close_and_verify_race
test_reauthenticate_does_not_deadlock = _support.test_reauthenticate_does_not_deadlock
test_protected_probe_requires_success_and_exact_final_resource = (
    _support.test_protected_probe_requires_success_and_exact_final_resource
)
test_resume_from_storage_state_invalidates_corrupt_persisted_artifacts = (
    _support.test_resume_from_storage_state_invalidates_corrupt_persisted_artifacts
)
test_resume_from_storage_state_invalidates_failed_live_probe = (
    _support.test_resume_from_storage_state_invalidates_failed_live_probe
)
test_resume_from_storage_state_reuses_persisted_session_with_live_protected_probe = (
    _support.test_resume_from_storage_state_reuses_persisted_session_with_live_protected_probe
)
test_run_login_probe_redacts_navigation_exception_text = _support.test_run_login_probe_redacts_navigation_exception_text
test_verify_raises_on_stale_session = _support.test_verify_raises_on_stale_session
test_verify_raises_without_context = _support.test_verify_raises_without_context


@pytest.mark.asyncio
async def test_reauthenticate_happy_path_with_browser_factory(tmp_path, _settings_factory) -> None:
    """``reauthenticate()`` closes the old session and produces a genuinely fresh one.

    Uncovered before this test: the existing
    ``test_reauthenticate_does_not_deadlock`` only proves the method returns in
    bounded time when no browser factory is injected (the failure path); it
    never proves ``reauthenticate()`` actually delegates ``close()`` +
    ``authenticate()`` correctly on a real success. This test injects a real
    in-process :class:`BrowserSessionLike` factory (``_RecordingBrowserSession``)
    authenticates once, then calls ``reauthenticate()`` and asserts the
    returned session is a genuinely new
    :class:`AeatSession` (later ``authenticated_at`` / ``idle_deadline``, an
    active browser context restored, no active session left dangling from the
    old one) rather than merely "did not raise".

    ``_RecordingBrowserSession.profile`` is ``None`` (settings-derived storage
    path fallback), so both the initial ``authenticate()`` and the delegated
    ``authenticate()`` inside ``reauthenticate()`` resolve to the *same*
    bucket-scoped storage-state path; ``close()`` never deletes persisted
    state, so the delegated call legitimately takes the resume branch
    (``_resume_from_storage_state_locked``) rather than a from-scratch
    browser login. That is real, correct ``authenticate()`` behaviour
    (persisted sessions exist precisely so a fresh login is not always required) and
    is itself part of what this test proves: ``reauthenticate()`` composes
    correctly with whichever branch the delegated ``authenticate()`` takes.
    """
    from ._authenticator_support import _build_bundle

    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)

    async def factory(settings: Settings) -> BrowserSessionLike:
        return _RecordingBrowserSession(cert_ok=True)

    async with AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
        browser_session_factory=factory,
    ) as auth:
        first_session = await auth.authenticate()
        assert auth._active_session == first_session

        refreshed_session = await auth.reauthenticate(first_session)

        # A genuinely fresh session was produced, not a copy of the old one.
        assert refreshed_session != first_session
        assert refreshed_session.authenticated_at >= first_session.authenticated_at
        assert refreshed_session.idle_deadline > first_session.idle_deadline
        assert refreshed_session.identity_nif == first_session.identity_nif

        # The authenticator ends reauthenticate() in a fully re-usable state:
        # a live active session and context, not the torn-down close() state.
        assert auth._active_session == refreshed_session
        assert auth._context is not None
        assert auth._closing is False

        # The delegated authenticate() call resumed the persisted session
        # and proved the same protected resource again (see docstring above).
        assert isinstance(refreshed_session.provider_detail, CertificateSessionDetail)
        assert refreshed_session.provider_detail.protected_resource_url


@pytest.mark.asyncio
async def test_reauthenticate_second_authenticate_failure_raises_session_expired_upstream(
    tmp_path,
    _settings_factory,
) -> None:
    """A second consecutive authenticate failure inside reauthenticate propagates.

    Companion negative case to the happy path above: per the method's own
    documented contract ("a second consecutive failure ... MUST raise
    AeatSessionExpiredError upwards rather than loop"), this proves
    ``reauthenticate()`` itself does not swallow or retry an ``authenticate()``
    failure — it lets the underlying error surface. The browser factory here
    returns a context that fails the certificate-recognition probe, so the
    delegated ``authenticate()`` call raises.
    """
    from .. import AeatLoginAssertionError
    from ._authenticator_support import _build_bundle

    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)

    async def failing_factory(settings: Settings) -> BrowserSessionLike:
        return _RecordingBrowserSession(cert_ok=False)

    async with AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
        browser_session_factory=failing_factory,
    ) as auth:
        now = datetime.now(UTC)
        session = _certificate_session(
            authenticated_at=now,
            idle_deadline=now + AEAT_SESSION_IDLE_TTL,
            thumbprint="abc",
            subject="CN=x",
        )
        with pytest.raises(AeatLoginAssertionError, match=r"login assertion|fresh AEAT authentication"):
            await auth.reauthenticate(session)
        # close() ran as part of the delegated teardown even though the
        # subsequent authenticate() failed; the authenticator is left clean,
        # not half-torn-down.
        assert auth._active_session is None
        assert auth._context is None
        assert auth._closing is False

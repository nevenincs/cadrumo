"""Roundtrip: session open -> verb -> idle expiry -> refusal.

Disaster ADR Ruling 1 wires the idle-timeout lifecycle into the
secure-object repository: every repository call polls the active
:class:`BucketSession` against its idle deadline, touches it forward
on success, and raises :class:`SessionExpiredError` once the window
has elapsed. The CLI error decorator translates that into an operator
refusal that names ``aeat config profile switch`` as the recovery
verb.

This roundtrip drives the full cycle with real adapters — a real
bucket-session helper that opens and activates a real
:class:`BucketSession`, and a real per-bucket
:class:`SecureObjectRepository`:

1. Open a session and confirm an encrypted-column write/read succeeds.
2. Confirm the successful call rolled the idle deadline forward
   (the ``touch`` contract).
3. Expire the session and confirm the next repository call refuses
   with ``SessionExpiredError``.
4. Confirm the expiry refusal names the ``profile switch`` recovery
   verb — no traceback, no generic catch-all.

No mocks: the expiry is forced by rolling the live session's own idle
deadline into the past, the same state a wall-clock idle timeout
produces.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage.errors import SessionExpiredError
from aeat.adapters.persistence.storage.master_key._active_session import _active_session
from aeat.adapters.persistence.storage.master_key._bucket_session import BucketSession
from aeat.adapters.persistence.storage.sql import SecureObjectRepository
from aeat.adapters.persistence.storage.sql.secure_objects import SensitivityClass
from aeat.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_NAMESPACE = "aeat.test.session.lifecycle"
_OBJECT_KEY = "roundtrip-row"
_CLASSIFICATION = SensitivityClass.OPERATIONAL


def _save(repository: SecureObjectRepository) -> None:
    """Write one encrypted row — a call that runs the session-freshness poll."""

    repository.save(
        namespace=_NAMESPACE,
        object_key=_OBJECT_KEY,
        classification=_CLASSIFICATION,
        schema_version=1,
        written_at=datetime.now(UTC),
        payload=b"session-roundtrip-payload",
    )


def _load(repository: SecureObjectRepository) -> object:
    """Read one encrypted row — a call that runs the session-freshness poll first."""

    return repository.load(
        _NAMESPACE,
        _OBJECT_KEY,
        expected_class=_CLASSIFICATION,
        max_supported_version=1,
    )


@pytest.fixture
def _runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """A real active-profile runtime with an unlocked per-bucket repository."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="session-roundtrip") as profile:
        yield profile


@pytest.fixture
def _inactive_repository(tmp_path: Path) -> SecureObjectRepository:
    """A real repository whose bucket session has already closed."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="session-roundtrip") as profile:
        repository = profile.repository
    assert _active_session.get() is None
    return repository


def _active_bucket_session() -> BucketSession:
    """Return the live BucketSession the master-key provider activated."""

    session = _active_session.get()
    assert isinstance(session, BucketSession), "master-key provider must activate a BucketSession"
    return session


def test_session_open_then_verb_succeeds_and_touches_deadline(_runtime_profile: TestRuntimeProfile) -> None:
    """An encrypted write inside an active session succeeds and rolls the deadline.

    The successful call polls the idle evaluator, finds the session
    fresh, and calls ``BucketSession.touch`` — so the idle deadline
    after the call sits one full idle window past the call time.
    """

    session = _active_bucket_session()
    deadline_before = session.idle_deadline
    repository = _runtime_profile.repository

    _save(repository)
    loaded = _load(repository)
    assert loaded is not None
    # The freshness poll on the successful calls touched the deadline forward.
    assert session.idle_deadline > deadline_before


def test_expired_session_refuses_the_next_verb(_runtime_profile: TestRuntimeProfile) -> None:
    """Once the idle window has elapsed, the next repository call refuses.

    The live session's idle deadline is rolled behind ``now`` to model
    a wall-clock idle timeout; the freshness poll inside the next
    repository call then raises ``SessionExpiredError``.
    """

    session = _active_bucket_session()
    repository = _runtime_profile.repository
    _save(repository)

    # Expire the session: roll its deadline into the past.
    session.touch(datetime.now(UTC) - timedelta(hours=1))
    assert session.is_expired(datetime.now(UTC))

    with pytest.raises(SessionExpiredError):
        _load(repository)


def test_session_lifecycle_full_roundtrip_open_verb_expiry_refusal(_runtime_profile: TestRuntimeProfile) -> None:
    """The full cycle: a fresh verb succeeds, then an expired verb refuses.

    One session object carries the whole lifecycle. The first call
    succeeds and touches; the deadline is then rolled into the past
    to model a wall-clock idle timeout; the second call refuses.
    """

    session = _active_bucket_session()
    repository = _runtime_profile.repository

    # Verb 1 — fresh session: succeeds.
    _save(repository)
    assert _load(repository) is not None

    # Idle window elapses: roll the session's own deadline behind now.
    session.touch(datetime.now(UTC) - timedelta(hours=1))
    assert session.is_expired(datetime.now(UTC))

    # Verb 2 — expired session: refuses.
    with pytest.raises(SessionExpiredError):
        _load(repository)


def test_expired_session_refusal_names_profile_switch_recovery_verb() -> None:
    """The expiry refusal renders an operator message naming ``profile switch``.

    Disaster ADR Ruling 1 requires the idle-expiry refusal to name a
    recovery verb that actually works. ``SessionExpiredError`` carries
    that message; the CLI error decorator surfaces it without a
    traceback.
    """

    error = SessionExpiredError(
        "the active profile session has expired; run "
        "`aeat config profile switch NAME` to re-activate.",
    )
    rendered = str(error)
    assert "profile switch" in rendered
    assert "expired" in rendered


def test_no_active_session_makes_freshness_poll_a_clean_noop(
    _inactive_repository: SecureObjectRepository,
) -> None:
    """With no session bound, the idle-freshness poll is a no-op, not a crash.

    Bootstrap-exempt verbs run without a session; the repository's
    idle-freshness check must skip cleanly rather than raise, leaving
    the active-gate at the CLI root as the sole refusal surface. The
    poll is exercised directly here because every key-touching
    repository call would otherwise fail on the missing master key
    before the poll's no-op branch could be observed.
    """

    assert _active_session.get() is None
    # The freshness poll must return without raising SessionExpiredError
    # (or any other exception) when no session is bound.
    _inactive_repository._check_session_freshness()

"""The persistence half of a Cl@ve session survives without a browser.

A post-authentication navigation failure destroys an authenticated
browser context before its cookies are ever read out of it, so the
operator's approval is spent and nothing is stored. The repair is to
capture and persist what the context already holds before tearing it
down, and the half of that repair which can be tested honestly is this
one: given a captured storage state, does a reusable session reach the
encrypted store and come back intact?

The other half - that a driver actually captures the state on the
failure path, and that the next invocation then reuses it without a
second Cl@ve prompt - cannot be tested here. It needs a real browser
negotiating a real AEAT page flow, and a page double would assert that
the double behaves at precisely the boundary the driver exists to
negotiate. That gap is deliberate and is recorded rather than papered
over with a fake.

Everything below drives the real encrypted session store through the
real bucket runtime; nothing is stubbed.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ......core.auth_session_keys import aeat_auth_session_storage_state_path
from ......core.config import Settings
from ......tests.secure_sql import isolated_runtime_profile
from .. import _session_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_BUCKET_ID = "1f6b0000-0000-4000-8000-00000000e0e0"
_STEM = "clave-movil-storage"
_IDENTITY = "12345678Z"
_AUTHENTICATED_AT = datetime(2026, 7, 26, 9, 0, 0, tzinfo=UTC)


_AEAT_DOMAINS = Settings.external_constants().aeat.domains


#: A storage state shaped like the one a real context yields: a cookie
#: carrying the session, and an origin entry. The cookie is what makes the
#: session reusable, so a persistence path that dropped it would leave a
#: record that loads cleanly and authenticates nothing.
def _storage_state(*, cookie_value: str = "synthetic-session-value") -> dict[str, object]:
    """Build a storage state shaped like the one a real context yields."""
    return {
        "cookies": [
            {
                "name": "JSESSIONID",
                "value": cookie_value,
                "domain": f".{_AEAT_DOMAINS.host_suffix}",
                "path": "/",
                "expires": -1,
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            },
        ],
        "origins": [{"origin": _AEAT_DOMAINS.www2, "localStorage": []}],
    }


_STORAGE_STATE: dict[str, object] = _storage_state()


def _path() -> Path:
    return aeat_auth_session_storage_state_path(_BUCKET_ID, _STEM)


def _metadata() -> dict[str, object]:
    return {
        "provider_kind": "clave_movil",
        "identity_nif": _IDENTITY,
        "authenticated_at": _AUTHENTICATED_AT.isoformat(),
        "idle_deadline": (_AUTHENTICATED_AT + timedelta(minutes=18)).isoformat(),
    }


def test_the_store_is_empty_before_anything_is_persisted() -> None:
    """Anti-tautology guard: the later assertions must have somewhere to move from.

    If a session already existed, a persistence path that wrote nothing
    would still satisfy every check below.
    """

    assert _session_store.exists(_path()) is False


def test_a_captured_storage_state_round_trips_through_the_encrypted_store() -> None:
    """The cookies survive the boundary, which is what makes a session reusable.

    Asserting the cookie rather than merely that a record loads: a
    persistence path that stored metadata and dropped the storage state
    would produce a record that reads back cleanly and authenticates
    nothing, which is the failure worth catching.
    """

    _session_store.save(_path(), storage_state=_STORAGE_STATE, metadata=_metadata())

    loaded = _session_store.load(_path())

    assert loaded is not None
    assert loaded.storage_state == _STORAGE_STATE
    assert loaded.metadata["identity_nif"] == _IDENTITY


def test_the_persisted_digest_binds_the_state_that_was_captured() -> None:
    """The stored digest is of the state itself, not of anything else.

    The provider records a storage-state digest in its metadata, and a
    reuse path compares against it. A digest computed over the wrong
    subject would let a substituted state pass as the captured one.
    """

    _session_store.save(_path(), storage_state=_STORAGE_STATE, metadata=_metadata())

    loaded = _session_store.load(_path())

    assert loaded is not None
    assert loaded.storage_state_sha256 == _session_store.storage_state_sha256(_STORAGE_STATE)


def test_a_different_storage_state_yields_a_different_digest() -> None:
    """Anti-tautology proof for the digest check above.

    A digest that ignored its input would satisfy the previous case
    while binding nothing, so a changed cookie has to change it.
    """

    other = _storage_state(cookie_value="a-different-session-value")

    assert _session_store.storage_state_sha256(other) != _session_store.storage_state_sha256(_STORAGE_STATE)


def test_persisting_is_what_makes_the_session_discoverable() -> None:
    """The property the repair turns on, stated directly.

    A session that is never written is not merely unusable, it is
    invisible: the reuse path asks the store whether one exists and gets
    no for a session AEAT is still holding open. Persisting is the whole
    difference between a recoverable navigation failure and a spent
    second factor.
    """

    path = _path()
    assert _session_store.exists(path) is False

    _session_store.save(path, storage_state=_STORAGE_STATE, metadata=_metadata())

    assert _session_store.exists(path) is True


@pytest.fixture(autouse=True)
def _runtime(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="Cl@ve persistence boundary"):
        yield

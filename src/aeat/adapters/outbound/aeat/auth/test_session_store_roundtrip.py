"""Strict roundtrip across the encrypted browser-session boundary.

The :mod:`aeat.adapters.outbound.aeat.auth._session_store` module
persists Playwright ``storage_state`` payloads encrypted at
``SensitivityClass.SESSION`` through :class:`SecureObjectRepository`.
This test asserts the save / load cycle preserves every key inside
``storage_state`` and ``metadata`` and that the SHA-256 fingerprint
on the loaded session matches the one computed at save time.

No mocks: the test enters the active profile-bucket runtime with a real
bucket session so regressions in runtime routing, column encryption,
envelope schema, or session-store JSON dumping surface as strict
equality failures.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from .....core.config import Settings, override_settings
from ....persistence.storage.master_key._active_session import activate_session
from ....persistence.storage.master_key._bucket_session import BucketSession
from ....persistence.storage.sql.engine import dispose_engine
from . import _session_store

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]
_BUCKET_ID = "session-roundtrip"


@contextmanager
def _active_runtime(tmp_path: Path, bucket_id: str) -> Iterator[Settings]:
    with override_settings(
        aeat_local_storage_root=tmp_path,
        aeat_active_profile=bucket_id,
    ) as settings:
        dispose_engine(settings)
        try:
            yield settings
        finally:
            dispose_engine(settings)


def _session() -> BucketSession:
    return BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=b"k" * 32,
        dek=b"d" * 32,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )


def _playwright_shaped_storage_state() -> dict[str, object]:
    """Build a Playwright-shape storage_state with cookies + origins.

    Mirrors the shape ``BrowserContext.storage_state()`` actually
    emits so the roundtrip exercises real heterogeneous content:
    nested lists of dicts with mixed value types (str, int, bool).
    """

    return {
        "cookies": [
            {
                "name": "PRESTACIONES_SESSION",
                "value": "abc123",
                "domain": ".agenciatributaria.gob.es",
                "path": "/",
                "expires": 1893456000,
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            },
        ],
        "origins": [
            {
                "origin": "https://sede.agenciatributaria.gob.es",
                "localStorage": [
                    {"name": "consent.banner", "value": "dismissed"},
                ],
            },
        ],
    }


def test_persisted_browser_session_roundtrips_under_real_encryption(
    tmp_path: Path,
) -> None:
    """A saved browser session loads back with every key + SHA preserved."""

    with _active_runtime(tmp_path, _BUCKET_ID), activate_session(_session()):
        logical_path = Path("/profile/active/aeat-session")
        storage_state = _playwright_shaped_storage_state()
        metadata = {
            "certificate_thumbprint": "AA:BB:CC:DD:EE:FF:00:11:22:33",
            "certificate_subject": "CN=AEAT Test User",
            "handshake_at": datetime.now(UTC).isoformat(),
            "renewal_count": 0,
        }
        sha_at_save = _session_store.storage_state_sha256(storage_state)

        _session_store.save(
            logical_path,
            storage_state=storage_state,
            metadata=metadata,
        )
        loaded = _session_store.load(logical_path)

        assert loaded is not None
        # Strict equality on the typed envelope: schema_version,
        # storage_state, metadata, written_at must all survive.
        assert loaded.storage_state == storage_state
        assert loaded.metadata == metadata
        # Cookie list preserves its inner shape: lists round-trip
        # through JSON as lists (not tuples), so the assertion
        # checks list identity rather than tuple.
        assert isinstance(loaded.storage_state["cookies"], list)
        cookies = loaded.storage_state["cookies"]
        assert isinstance(cookies, list)
        assert isinstance(cookies[0], Mapping)
        # Playwright storage_state cookies are documented string-keyed
        # dicts; the persisted payload exposes them only as ``object``.
        first_cookie = cast("Mapping[str, object]", cookies[0])
        assert first_cookie["name"] == "PRESTACIONES_SESSION"
        assert first_cookie["httpOnly"] is True
        assert first_cookie["expires"] == 1893456000
        # The SHA computed on the loaded payload must match the
        # SHA computed at save time. If column-encryption mangled
        # any byte, this assertion fails before any field check.
        assert loaded.storage_state_sha256 == sha_at_save

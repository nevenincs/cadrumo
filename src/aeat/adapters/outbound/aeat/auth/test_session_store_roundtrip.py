"""Strict roundtrip across the encrypted browser-session boundary.

The :mod:`aeat.adapters.outbound.aeat.auth._session_store` module
persists Playwright ``storage_state`` payloads encrypted at
``SensitivityClass.SESSION`` through :class:`SecureObjectRepository`.
This test asserts the save / load cycle preserves every key inside
``storage_state`` and ``metadata`` and that the SHA-256 fingerprint
on the loaded session matches the one computed at save time.

No mocks: the test stands up a real SQLite engine, the real
:class:`EphemeralMasterKeyProvider`, and the real repository row
class so any regression in the column-encryption hook, envelope
schema, or session-store JSON dump surfaces as a strict equality
failure.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....core.config import Settings
from ....persistence.storage import EphemeralMasterKeyProvider
from ....persistence.storage.sql import SecureObjectRepository
from ....persistence.storage.sql._orm import Base
from ....persistence.storage.sql.engine import create_engine_from_settings
from . import _session_store

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


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

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "session-roundtrip.db"
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

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
            assert cookies[0]["name"] == "PRESTACIONES_SESSION"
            assert cookies[0]["httpOnly"] is True
            assert cookies[0]["expires"] == 1893456000
            # The SHA computed on the loaded payload must match the
            # SHA computed at save time. If column-encryption mangled
            # any byte, this assertion fails before any field check.
            assert loaded.storage_state_sha256 == sha_at_save
        finally:
            engine.dispose()

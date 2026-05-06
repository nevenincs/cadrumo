"""Tests for encrypted SQL byte-object persistence."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....core.classification import SensitivityClass
from .....core.config import Settings
from .. import EphemeralMasterKeyProvider, override_master_key_provider
from ._orm import Base
from .engine import create_engine_from_settings
from .secure_objects import SecureObjectRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def test_secure_object_payload_is_encrypted_in_database(tmp_path: Path) -> None:
    """Sensitive payload bytes round-trip without plaintext landing in SQLite."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "secure.db"
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
    Base.metadata.create_all(engine)
    try:
        repo = SecureObjectRepository(engine=engine)
        payload = b"SECURE_OBJECT_CANARY_tax_financial_payload"
        natural_key = "CSV1234-sensitive-natural-key"
        repo.save(
            namespace="aeat.test",
            object_key=natural_key,
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=payload,
        )

        loaded = repo.load(
            "aeat.test",
            natural_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=1,
        )
        assert loaded is not None
        assert loaded.payload == payload
        assert payload not in db_path.read_bytes()
        assert natural_key.encode("utf-8") not in db_path.read_bytes()

        with sqlite3.connect(db_path) as con:
            stored_key, stored = con.execute("SELECT object_key, payload FROM secure_objects").fetchone()
        assert isinstance(stored_key, bytes)
        assert len(stored_key) == 32
        assert natural_key.encode("utf-8") not in stored_key
        assert isinstance(stored, bytes)
        assert payload not in stored
    finally:
        engine.dispose()
        override_master_key_provider(None)

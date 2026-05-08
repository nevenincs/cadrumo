"""Tests for encrypted SQL byte-object persistence."""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....core.classification import SensitivityClass
from .....core.config import Settings
from .. import EphemeralMasterKeyProvider, override_master_key_provider
from ._orm import Base
from .engine import create_engine_from_settings
from .secure_objects import (
    SecureObjectRecord,
    SecureObjectRepository,
    SecureObjectUnreadable,
)

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


def _seed_under_key(
    *,
    db_path: Path,
    provider: EphemeralMasterKeyProvider,
    namespace: str,
    natural_key: str,
    payload: bytes,
) -> None:
    """Seed one secure-object row through the public repository under ``provider``."""
    override_master_key_provider(provider)
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine).save(
            namespace=namespace,
            object_key=natural_key,
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=payload,
        )
    finally:
        engine.dispose()


def test_list_records_skips_rows_sealed_under_a_prior_master_key(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A row written under master key K1 must not crash a list_records call under K2.

    The architectural defect this guards against: ``list_records`` used to
    materialise every row through the SQLAlchemy column processor in one
    pass, so a single ``InvalidTag`` (caused by a row written under a
    rotated master key) aborted the entire iteration. The fault-isolated
    iterator must skip the unreadable row and let the readable subset
    flow through, while emitting a structured warning.
    """
    db_path = tmp_path / "rotated.db"
    key_old = EphemeralMasterKeyProvider()
    key_new = EphemeralMasterKeyProvider()
    namespace = "aeat.test.rotation"

    # Seed a row under the OLD key, leaving the ciphertext at rest.
    _seed_under_key(
        db_path=db_path,
        provider=key_old,
        namespace=namespace,
        natural_key="row-under-old-key",
        payload=b"plaintext-from-old-generation",
    )

    # Reopen under the NEW key and add a row that ought to be readable.
    override_master_key_provider(key_new)
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
    Base.metadata.create_all(engine)
    try:
        repo = SecureObjectRepository(engine=engine)
        repo.save(
            namespace=namespace,
            object_key="row-under-new-key",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"plaintext-from-current-generation",
        )

        with caplog.at_level(logging.WARNING, logger="aeat.adapters.persistence.storage.sql.secure_objects"):
            yielded = list(
                repo.list_records(
                    namespace,
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=1,
                )
            )

        assert len(yielded) == 1
        assert yielded[0].payload == b"plaintext-from-current-generation"
        assert any("skipped 1 unreadable row" in rec.message for rec in caplog.records), (
            f"expected one structured warning summarising the skip count; got {[r.message for r in caplog.records]}"
        )
    finally:
        engine.dispose()
        override_master_key_provider(None)


def test_iter_records_with_failures_yields_typed_outcomes_for_each_row(
    tmp_path: Path,
) -> None:
    """The fault-isolated iterator must yield one item per stored row.

    Two rows seeded under a rotated master key plus one row written
    under the current key must produce a triple of outcomes: two
    :class:`SecureObjectUnreadable` and one :class:`SecureObjectRecord`,
    in stable storage order. No exception escapes.
    """
    db_path = tmp_path / "mixed.db"
    key_old = EphemeralMasterKeyProvider()
    key_new = EphemeralMasterKeyProvider()
    namespace = "aeat.test.mixed"

    for natural_key, payload in (
        ("row-1-old", b"old-1-plaintext"),
        ("row-2-old", b"old-2-plaintext"),
    ):
        _seed_under_key(
            db_path=db_path,
            provider=key_old,
            namespace=namespace,
            natural_key=natural_key,
            payload=payload,
        )

    override_master_key_provider(key_new)
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine).save(
            namespace=namespace,
            object_key="row-3-new",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"new-3-plaintext",
        )

        items = list(
            SecureObjectRepository(engine=engine).iter_records_with_failures(
                namespace,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=1,
            )
        )

        assert len(items) == 3, f"expected one outcome per row; got {items}"
        unreadable = [item for item in items if isinstance(item, SecureObjectUnreadable)]
        loaded = [item for item in items if isinstance(item, SecureObjectRecord)]
        assert len(unreadable) == 2
        assert len(loaded) == 1
        assert loaded[0].payload == b"new-3-plaintext"
        for ghost in unreadable:
            assert ghost.namespace == namespace
            assert ghost.row_id > 0
            assert "tag verification failed" in ghost.reason.lower() or "decrypt" in ghost.reason.lower()
    finally:
        engine.dispose()
        override_master_key_provider(None)


def test_iter_records_with_failures_returns_empty_on_empty_namespace(
    tmp_path: Path,
) -> None:
    """A namespace with no rows yields an empty iterator without raising."""
    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "empty.db"
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
    Base.metadata.create_all(engine)
    try:
        items = list(
            SecureObjectRepository(engine=engine).iter_records_with_failures(
                "aeat.test.empty",
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=1,
            )
        )
        assert items == []
    finally:
        engine.dispose()
        override_master_key_provider(None)


def test_list_records_only_emits_warning_when_unreadable_rows_exist(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No warning fires on a clean namespace; the warning is gated on real failures."""
    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "clean.db"
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
    Base.metadata.create_all(engine)
    namespace = "aeat.test.clean"
    try:
        repo = SecureObjectRepository(engine=engine)
        repo.save(
            namespace=namespace,
            object_key="row-clean",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"clean-plaintext",
        )

        with caplog.at_level(logging.WARNING, logger="aeat.adapters.persistence.storage.sql.secure_objects"):
            yielded = list(
                repo.list_records(
                    namespace,
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=1,
                )
            )

        assert len(yielded) == 1
        assert all("unreadable" not in rec.message for rec in caplog.records)
    finally:
        engine.dispose()
        override_master_key_provider(None)

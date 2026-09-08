"""Tests for the hashed-lookup TypeDecorator.

The tests run against a real in-memory SQLAlchemy session bound to
a deliberately-isolated declarative base so we never touch the live
``cadrumo.adapters.persistence.storage._orm`` schema. The master key is supplied by an
:class:`EphemeralMasterKeyProvider` whose ``__enter__`` activates a
:class:`BucketSession` for the duration of the test.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Annotated, cast

import pytest
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from ......tests.master_key import EphemeralMasterKeyProvider
from ...errors import StorageValidationError
from ..encrypted_columns import HashedLookup

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


class _TestBase(DeclarativeBase):
    """Declarative base local to this test module — never touches the live schema."""


_intpk = Annotated[int, mapped_column(primary_key=True, autoincrement=True)]
_lookup_key = Annotated[bytes | None, mapped_column(HashedLookup, nullable=True, index=True)]


class _CryptoRow(_TestBase):
    """One mapper class exercising the hashed lookup type."""

    __tablename__ = "encrypted_column_smoke"

    id: Mapped[_intpk]
    lookup_key: Mapped[_lookup_key]


@pytest.fixture(autouse=True)
def _patch_master_key(fixed_master_key: bytes) -> Iterator[None]:
    """Inject a deterministic master key for every test in this module."""
    with EphemeralMasterKeyProvider(key=fixed_master_key):
        yield


@pytest.fixture
def engine() -> Iterator[Engine]:
    """Yield a clean in-memory SQLite engine bound to the test schema."""
    eng = create_engine("sqlite:///:memory:", future=True)
    _TestBase.metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as sess:
        yield sess


class TestHashedLookup:
    """The deterministic HMAC keeps equality semantics without leaking plaintext."""

    def test_same_plaintext_same_digest(self, session: Session) -> None:
        digest_a = HashedLookup.compute("operator-secret-key")
        digest_b = HashedLookup.compute("operator-secret-key")
        assert digest_a == digest_b
        assert len(digest_a) == 32

    def test_different_plaintexts_different_digests(self) -> None:
        a = HashedLookup.compute("alpha")
        b = HashedLookup.compute("beta")
        assert a != b

    def test_short_plaintext_digest_does_not_emit_runtime_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(
            logging.WARNING,
            logger="cadrumo.adapters.persistence.storage.crypto.encrypted_columns",
        )

        digest = HashedLookup.compute("alpha")

        assert len(digest) == 32
        assert not [
            record
            for record in caplog.records
            if record.name == "cadrumo.adapters.persistence.storage.crypto.encrypted_columns"
        ]

    def test_round_trip_via_sqlalchemy(self, session: Session) -> None:
        row = _CryptoRow(lookup_key="natural-key-1")
        session.add(row)
        session.commit()
        session.expire_all()
        loaded = session.execute(select(_CryptoRow)).scalar_one()
        # The stored representation is the digest, not the plaintext.
        assert loaded.lookup_key == HashedLookup.compute("natural-key-1")

    def test_query_by_natural_key(self, session: Session) -> None:
        session.add_all(
            [
                _CryptoRow(lookup_key="alpha"),
                _CryptoRow(lookup_key="beta"),
                _CryptoRow(lookup_key="gamma"),
            ],
        )
        session.commit()
        # The decorator digests the bound parameter, so consumers can
        # query with the natural-key plaintext rather than precomputing
        # the digest themselves.
        match = session.execute(
            select(_CryptoRow).where(_CryptoRow.lookup_key == "beta"),
        ).scalar_one()
        assert match.lookup_key == HashedLookup.compute("beta")

    def test_digest_changes_with_master_key(self) -> None:
        digest_a = HashedLookup.compute("payload")
        # Switch to a different master key; the digest must change.
        with EphemeralMasterKeyProvider():
            digest_b = HashedLookup.compute("payload")
        assert digest_a != digest_b

    def test_invalid_plaintext_type_carries_storage_validation_locale_key(self) -> None:
        with pytest.raises(StorageValidationError) as excinfo:
            HashedLookup.compute(cast(str, b"not-str"))
        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"


class TestNullSafety:
    """The decorator's bind/result handlers return None for None inputs."""

    def test_string_none(self, session: Session) -> None:
        session.add(_CryptoRow())
        session.commit()
        session.expire_all()
        loaded = session.execute(select(_CryptoRow)).scalar_one()
        assert loaded.lookup_key is None

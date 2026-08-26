"""Real encrypted-SQL regression for the profile bare-model persistence kernel."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from .....adapters.persistence.storage import PROFILE_ASSETS_LEDGER_NAMESPACE
from .....core import ABSENT_SECURE_OBJECT_REVISION_ID
from .....domain.contribuyente.assets import AssetClass, AssetRecord, AssetsLedgerDocument
from .....tests.secure_sql import isolated_runtime_profile, read_db_at_rest_bytes
from .._secure_model_document import ProfileBareModelSecurePersistence

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _is_secure_object_select(statement: str) -> bool:
    """Return whether one cursor statement reads the encrypted singleton table."""
    normalized = " ".join(statement.split()).upper()
    return normalized.startswith("SELECT") and " FROM SECURE_OBJECTS " in f" {normalized} "


@contextmanager
def _secure_object_select_log(engine: Engine) -> Iterator[list[str]]:
    """Observe live encrypted-SQL singleton reads without replacing a repository."""
    selects: list[str] = []

    def _record(
        _conn: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if _is_secure_object_select(statement):
            selects.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        yield selects
    finally:
        event.remove(engine, "before_cursor_execute", _record)


def _document(identifier: str) -> AssetsLedgerDocument:
    """Build a non-default bare singleton payload for one observation test."""
    return AssetsLedgerDocument(
        assets=(
            AssetRecord(
                identifier=identifier,
                description=f"KERNEL-SECRET-{identifier}",
                asset_class=AssetClass.ELECTRONICA_INFORMATICA,
                acquisition_date=date(2025, 1, 1),
                cost_basis=Decimal("100.00"),
            ),
        ),
    )


def test_kernel_roundtrips_a_strict_document_as_encrypted_registry_governed_bytes(tmp_path: Path) -> None:
    """The shared kernel never creates a plaintext model or an ungoverned row."""
    document = _document("kernel-canary")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="a0e10fc6-03c5-4290-832a-fcb4c7654fe4") as profile:
        persistence = ProfileBareModelSecurePersistence(
            objects=profile.repository,
            definition=PROFILE_ASSETS_LEDGER_NAMESPACE,
            model_type=AssetsLedgerDocument,
            empty_document=AssetsLedgerDocument,
        )

        write = persistence.to_secure_object_write(document)
        persistence.save(document)

        at_rest = read_db_at_rest_bytes(profile.paths.database_file)
        assert persistence.load() == document

    assert write.namespace == PROFILE_ASSETS_LEDGER_NAMESPACE.namespace
    assert write.classification is PROFILE_ASSETS_LEDGER_NAMESPACE.sensitivity
    assert write.schema_version == PROFILE_ASSETS_LEDGER_NAMESPACE.schema_version
    assert b"KERNEL-SECRET-ASSET" not in at_rest
    assert b"kernel-canary" not in at_rest


def test_load_revisioned_returns_one_bare_secure_object_record_across_an_interleaving(
    tmp_path: Path,
) -> None:
    """One live SQL SELECT cannot pair a first payload with a later revision."""
    first = _document("first")
    second = _document("second")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="ae1c1f6a-dde4-4dda-a3d5-4ef005b70129") as profile:
        persistence = ProfileBareModelSecurePersistence(
            objects=profile.repository,
            definition=PROFILE_ASSETS_LEDGER_NAMESPACE,
            model_type=AssetsLedgerDocument,
            empty_document=AssetsLedgerDocument,
        )
        persistence.save(first)
        expected_revision_id = profile.repository.load(
            PROFILE_ASSETS_LEDGER_NAMESPACE.namespace,
            PROFILE_ASSETS_LEDGER_NAMESPACE.require_default_object_key(),
            expected_class=PROFILE_ASSETS_LEDGER_NAMESPACE.sensitivity,
            max_supported_version=PROFILE_ASSETS_LEDGER_NAMESPACE.schema_version,
        )
        assert expected_revision_id is not None

        writer = ProfileBareModelSecurePersistence(
            objects=profile.repository,
            definition=PROFILE_ASSETS_LEDGER_NAMESPACE,
            model_type=AssetsLedgerDocument,
            empty_document=AssetsLedgerDocument,
        )
        selects: list[str] = []
        fired = False
        writing = False

        def _interleave_after_singleton_select(
            _conn: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            nonlocal fired, writing
            if not _is_secure_object_select(statement) or writing:
                return
            selects.append(statement)
            if fired:
                return
            fired = True
            writing = True
            try:
                writer.save(second)
            finally:
                writing = False

        engine = profile.repository.engine
        event.listen(engine, "after_cursor_execute", _interleave_after_singleton_select)
        try:
            observed, revision_id = persistence.load_revisioned()
        finally:
            event.remove(engine, "after_cursor_execute", _interleave_after_singleton_select)

    assert fired
    assert len(selects) == 1
    assert observed == first
    assert revision_id == expected_revision_id.revision_id


def test_load_revisioned_observes_an_absent_bare_singleton_with_one_select(
    tmp_path: Path,
) -> None:
    """The absent singleton outcome also comes from exactly one encrypted-SQL read."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="04ff919d-3023-4ea3-b177-1b4e9fca0f40") as profile:
        persistence = ProfileBareModelSecurePersistence(
            objects=profile.repository,
            definition=PROFILE_ASSETS_LEDGER_NAMESPACE,
            model_type=AssetsLedgerDocument,
            empty_document=AssetsLedgerDocument,
        )
        with _secure_object_select_log(profile.repository.engine) as selects:
            observed, revision_id = persistence.load_revisioned()

    assert len(selects) == 1
    assert observed == AssetsLedgerDocument()
    assert revision_id == ABSENT_SECURE_OBJECT_REVISION_ID

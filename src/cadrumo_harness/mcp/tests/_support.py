"""Harness-local integration support with no repository test-package dependency.

The profile-persistence composition these tests enter is NOT here: it is the
one shipped definition in ``cadrumo.entrypoints.adapter_composition``, which
the tests import directly. A harness-local copy is what this module exists to
avoid for test PACKAGE dependencies, and it was never a reason to restate
product wiring -- the copy that used to live here had already drifted from
the set the shipped frontend binds."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.sql.engine import dispose_engine
from cadrumo.adapters.persistence.storage.storage_path_definitions import BUCKETS_DIRNAME, KEYSTORE_DIRNAME
from cadrumo.core.config import load_settings, override_settings
from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import STORAGE_TAXONOMY


@contextmanager
def temporary_env(**values: str) -> Generator[None]:
    """Temporarily set environment variables and restore their prior state."""
    previous = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, old_value in previous.items():
            if old_value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = old_value


def _reap_profile_session_keys(storage_root: Path) -> None:
    """Best-effort cleanup for session receipts created by a harness test."""
    bucket_ids: set[str] = set()
    for parent in (storage_root / BUCKETS_DIRNAME, storage_root / KEYSTORE_DIRNAME):
        try:
            entries = scan_directory(parent, select=DirectoryEntryKind.DIRECTORIES, require_root=True)
        except OSError:
            continue
        bucket_ids.update(entry.name for entry in entries)
    for bucket_id in bucket_ids:
        try:
            delete_profile_session(storage_root=storage_root, profile_id=UUID(bucket_id))
        except (CadrumoError, ValueError):
            continue


@contextmanager
def isolated_profile_storage_root(*, tmp_path: Path) -> Generator[Path]:
    """Run harness profile-bootstrap tests against an isolated real storage root."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    storage_root = tmp_path / "cadrumo-storage"
    passphrase = load_settings().cadrumo_dev_test_database_password
    secret_location = STORAGE_TAXONOMY[StorageCategory.SECRETS]
    if secret_location.settings_field is None:
        raise RuntimeError("secret storage must expose an overrideable settings field")
    with override_settings(
        cadrumo_local_storage_root=storage_root,
        cadrumo_active_profile=None,
        cadrumo_secret_passphrase=passphrase,
        cadrumo_profile_kdf_measure_calibration=False,
        **{secret_location.settings_field: tmp_path / secret_location.relative_path()},
    ) as settings:
        dispose_engine(settings)
        try:
            yield storage_root
        finally:
            _reap_profile_session_keys(storage_root)
            dispose_engine(settings)


__all__ = ["isolated_profile_storage_root", "temporary_env"]

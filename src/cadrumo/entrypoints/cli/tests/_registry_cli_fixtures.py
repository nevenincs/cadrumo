"""Pytest fixtures for registry CLI tests.

The ``"secrets"`` literal in the CLI env below is not an arbitrary injected
value: it must agree with what :func:`~tests.secure_sql.isolated_runtime_profile`
already minted the master key under, since that fixture derives
``cadrumo_secret_store_dir`` from the real taxonomy accessor
(``storage_overrides(tmp_path, StorageCategory.SECRETS)`` -> ``tmp_path /
"secrets"``). The CLI subprocesses this env drives must independently compute
the same location to unlock the profile the fixture already created; renaming
it to a fictional segment breaks that handoff. The blob-store and audit-dir
overrides carry no equivalent handoff constraint -- nothing else in this
fixture derives or re-reads those locations -- so they are named
``"probe-blobs"`` / ``"probe-audit"`` precisely to keep them out of the
taxonomy vocabulary rather than pinned as if they were.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest

from ....adapters.persistence.storage.master_key import BucketSession, activate_session
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core.config import override_settings
from ....tests.secure_sql import dev_test_database_password, isolated_runtime_profile
from ....tests.user_profile import register_minimal_profile
from ._registry_cli_support import _BUCKET_ID, _clear_cli_env, _set_cli_env

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"secrets"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring."""

_SESSION_OPENED_AT = datetime(2099, 5, 28, 15, 55, tzinfo=UTC)


@pytest.fixture(scope="module", autouse=True)
def _isolated_registry_cli_backend(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    tmp_path = tmp_path_factory.mktemp("registry-cli")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        _set_cli_env(
            {
                "CADRUMO_LOCAL_STORAGE_ROOT": str(runtime.storage_root),
                "CADRUMO_ACTIVE_PROFILE": runtime.bucket_id,
                "CADRUMO_SECRET_STORE_BACKEND": "auto",
                "CADRUMO_SECRET_STORE_DIR": str(tmp_path / "secrets"),
                "CADRUMO_BLOB_STORE_DIR": str(tmp_path / "probe-blobs"),
                "CADRUMO_LIVE_STATE_DIR": str(tmp_path / "probe-live-state"),
                "CADRUMO_SECRET_PASSPHRASE": dev_test_database_password(runtime.settings),
                "CADRUMO_OUTPUT_LANGUAGE": "en",
            },
        )
        yield
    _clear_cli_env()


@pytest.fixture(autouse=True)
def _isolated_secure_backend(tmp_path: Path) -> Iterator[None]:
    """Point encrypted SQL runtime at a per-test active bucket."""

    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_BUCKET_ID) as settings,
        activate_session(_session()),
    ):
        dispose_engine(settings)
        # A bucket exists only once its profile capsule is published: opening an
        # engine against a bare session now refuses rather than materialising a
        # directory for a profile that was never registered.
        register_minimal_profile(profile_id=_BUCKET_ID)
        try:
            yield
        finally:
            dispose_engine(settings)


def _session() -> BucketSession:
    return BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=b"k" * 32,
        dek=b"d" * 32,
        idle_minutes=15,
        opened_at=_SESSION_OPENED_AT,
    )

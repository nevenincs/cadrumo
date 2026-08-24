"""Real-behavior regression pin for the locale-catalogue flat-map cache.

No mocks, stubs, or monkeypatches: exercises the real filesystem under an
isolated per-test storage root (``override_settings(cadrumo_local_storage_root=...)``),
the real ``sha256``/pydantic validation path, and the real ``tr()`` render
pipeline. Two hazards are pinned:

* a source-digest mismatch (the YAML changed) is a cache miss, not a wrong
  answer -- absent and stale collapse to one code path; and
* a payload-digest mismatch (the cached JSON itself was truncated or
  tampered, even though its source digest still matches) is ALSO a cache
  miss -- the second, independent integrity check the source-key match alone
  cannot provide.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

import pytest

from ...config import override_settings
from ...hashing import sha256_hex
from .. import _catalogue_cache as cc

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@contextmanager
def _env_var(name: str, value: str):
    """Set an environment variable for the scope, restoring its prior state on exit.

    A local context manager rather than the pytest ``monkeypatch`` fixture,
    per this module's own no-monkeypatch discipline.
    """
    previous = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def test_write_then_read_round_trips_the_flat_map(tmp_path: Path) -> None:
    """A freshly written cache is read back byte-for-byte identical."""
    with override_settings(cadrumo_local_storage_root=tmp_path):
        flat: dict[str, str | None] = {"cli.root.app_help": "Ayuda", "cli.missing": None}
        digest = sha256_hex(b"source bytes v1")

        cc.write_catalogue_cache("es", source_digest=digest, flat=flat)
        cached = cc.read_catalogue_cache("es", source_digest=digest)

        assert cached == flat


def test_absent_cache_is_a_clean_miss(tmp_path: Path) -> None:
    """No cache file at all returns None, never an error."""
    with override_settings(cadrumo_local_storage_root=tmp_path):
        digest = sha256_hex(b"anything")
        assert cc.read_catalogue_cache("es", source_digest=digest) is None


def test_source_digest_mismatch_is_a_miss_not_a_wrong_answer(tmp_path: Path) -> None:
    """A cache written for an older source is never served against a newer one.

    This is the "stale" case: the source changed, so the current digest no
    longer matches the one embedded in the cache. Absent and stale are the
    same code path by construction (the digest is part of the lookup key).
    """
    with override_settings(cadrumo_local_storage_root=tmp_path):
        old_digest = sha256_hex(b"source bytes v1")
        new_digest = sha256_hex(b"source bytes v2 -- different")
        flat: dict[str, str | None] = {"cli.root.app_help": "Old value"}

        cc.write_catalogue_cache("es", source_digest=old_digest, flat=flat)

        assert cc.read_catalogue_cache("es", source_digest=new_digest) is None
        # The stale file is deleted, not left behind to be misread later.
        assert not cc.catalogue_cache_path("es").exists()


def test_corrupt_json_is_a_clean_miss_and_self_heals(tmp_path: Path) -> None:
    """Invalid JSON at the cache path is ignored, deleted, and never raised."""
    with override_settings(cadrumo_local_storage_root=tmp_path):
        path = cc.catalogue_cache_path("es")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not valid json at all", encoding="utf-8")

        digest = sha256_hex(b"whatever")
        assert cc.read_catalogue_cache("es", source_digest=digest) is None
        assert not path.exists()


def test_truncated_payload_under_a_matching_source_digest_is_rejected(tmp_path: Path) -> None:
    """A structurally-valid cache whose ``flat`` was truncated is NOT served.

    This is the case a source-digest check alone cannot catch: schema_version,
    locale, and source_digest all still match (the file's KEY is valid), but
    the payload itself was truncated after being written -- the failure mode
    of a crash, a killed process, or two writers racing on the same path. The
    embedded payload_digest is the second, independent check that catches it.
    """
    with override_settings(cadrumo_local_storage_root=tmp_path):
        digest = sha256_hex(b"source bytes")
        full_flat: dict[str, str | None] = {f"cli.key.{i}": f"value {i}" for i in range(200)}

        cc.write_catalogue_cache("es", source_digest=digest, flat=full_flat)

        # Simulate a payload truncated after being written under a valid key:
        # keep schema_version/locale/source_digest intact, shrink flat, and
        # deliberately leave payload_digest as the stale value it was written
        # with (a real truncation would not know to recompute it either).
        path = cc.catalogue_cache_path("es")
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert on_disk["source_digest"] == digest
        truncated_keys = list(full_flat)[:10]
        on_disk["flat"] = {k: full_flat[k] for k in truncated_keys}
        path.write_text(json.dumps(on_disk), encoding="utf-8")

        result = cc.read_catalogue_cache("es", source_digest=digest)

        assert result is None, "a truncated payload under a valid source key must never be served"
        assert not path.exists(), "the corrupt cache must be deleted, not left for a future misread"


def test_tampered_value_under_a_matching_source_digest_is_rejected(tmp_path: Path) -> None:
    """A cache whose value was altered in place (same keys, wrong content) is rejected.

    Distinct from truncation: the key set is unchanged but one value was
    swapped for a poisoned string. The payload digest catches this the same
    way -- any alteration of ``flat`` changes its content hash.
    """
    with override_settings(cadrumo_local_storage_root=tmp_path):
        digest = sha256_hex(b"source bytes")
        flat: dict[str, str | None] = {"cli.root.app_help": "Valor correcto"}
        cc.write_catalogue_cache("es", source_digest=digest, flat=flat)

        path = cc.catalogue_cache_path("es")
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        on_disk["flat"]["cli.root.app_help"] = "WRONG STALE VALUE THAT MUST NEVER BE SERVED"
        path.write_text(json.dumps(on_disk), encoding="utf-8")

        result = cc.read_catalogue_cache("es", source_digest=digest)

        assert result is None, "a tampered value under a valid source key must never be served"


def test_end_to_end_tr_self_heals_across_all_three_corruption_modes(tmp_path: Path) -> None:
    """The real ``tr()`` pipeline never serves a stale, truncated, or tampered answer.

    Exercises the production entry point (not the cache module directly):
    warms the real packaged catalogue through ``tr()``, corrupts the on-disk
    cache three different ways, and confirms every one self-heals to the
    correct rendered value rather than raising or serving a wrong string.
    """
    from ...i18n import tr
    from .. import _render

    # _packaged_locale_map is lru_cache'd per process, so a second in-process
    # tr() call would return the memoised dict without ever touching disk
    # again -- clear it between corruption attempts so each assertion
    # genuinely re-exercises the disk-read/self-heal path, not the memo.
    def _reread_from_disk() -> str:
        _render._packaged_locale_map.cache_clear()
        return tr("cli.root.app_help", locale="es")

    try:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            first = _reread_from_disk()
            path = cc.catalogue_cache_path("es")
            digest = sha256_hex(b"test-source")
            cc.write_catalogue_cache("es", source_digest=digest, flat={"cli.root.app_help": first})
            assert path.is_file(), "on-disk cache must exist"

            # Corrupt JSON.
            path.write_text("not json", encoding="utf-8")
            assert _reread_from_disk() == first

            # Mismatched source digest (simulate a stale cache from an old source).
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "flat-catalogue-v1",
                        "locale": "es",
                        "source_digest": "0" * 64,
                        "payload_digest": "0" * 64,
                        "flat": {"cli.root.app_help": "WRONG STALE VALUE THAT MUST NEVER BE SERVED"},
                    },
                ),
                encoding="utf-8",
            )
            assert _reread_from_disk() == first

            # Truncated payload under a valid key (the realistic crash/race shape:
            # schema_version/locale/source_digest all still match, only flat and
            # its embedded payload_digest are out of sync).
            on_disk = json.loads(path.read_text(encoding="utf-8"))
            on_disk["flat"] = {"cli.root.app_help": "WRONG STALE VALUE THAT MUST NEVER BE SERVED"}
            path.write_text(json.dumps(on_disk), encoding="utf-8")
            assert _reread_from_disk() == first
    finally:
        # Leave the shared module-level lru_cache clean: it must not carry a
        # memo scoped to this test's now-torn-down tmp_path into a later test
        # in the same worker process.
        _render._packaged_locale_map.cache_clear()


def test_tr_survives_a_storage_root_settings_cannot_construct_over(
    tmp_path: Path,
) -> None:
    """``tr()`` must never fail because the cache's location cannot be resolved.

    Regression pin: the cache's location is resolved through
    ``storage_path()``, which constructs a full ``Settings()`` -- a
    dependency the original (pre-cache) ``tr()`` never had, since it only
    ever read a packaged resource via ``importlib.resources``. ``Settings()``
    construction can raise for reasons that have nothing to do with
    translation (here: a real retired-product-state ``aeat.db`` under the
    active storage root, which ``core._config_state_root.refuse_former_product_database``
    correctly refuses). Because ``tr()`` is called from a MODULE-LEVEL
    statement in ``entrypoints/cli/__init__.py`` (``help=tr(...)``), before
    the CLI's own command-dispatch error boundary is active, an unguarded
    exception here would crash the whole process, including plain
    ``--help`` -- confirmed live via
    ``entrypoints/cli/tests/test_root_help_shape.py``'s subprocess-level
    fixtures. This is the fast, direct-call counterpart to that proof.

    Uses the ``CADRUMO_LOCAL_STORAGE_ROOT`` env var directly (via the local
    ``_env_var`` context manager) + ``_constructed_settings.cache_clear()``
    rather than ``override_settings`` -- the latter constructs a
    ``Settings`` at its own ``__enter__`` (to validate the override), which
    would raise before this test ever reaches its assertion. The env var is
    exactly what the real CLI subprocess fixture sets.
    """
    import sqlite3

    from ..._config_state_root import FormerProductStateError
    from ...config import Settings, _constructed_settings
    from ...i18n import tr
    from .. import _render

    former_root = tmp_path / "former-product-state"
    former_root.mkdir()
    with sqlite3.connect(former_root / "aeat.db"):
        pass

    with _env_var("CADRUMO_LOCAL_STORAGE_ROOT", str(former_root)):
        _constructed_settings.cache_clear()
        _render._packaged_locale_map.cache_clear()
        try:
            # Confirm the fixture is real: constructing Settings() directly
            # against this root does raise, so the test proves tr() survives a
            # genuine failure, not an unreachable one.
            with pytest.raises(FormerProductStateError):
                Settings()

            rendered = tr("cli.root.app_help", locale="es")
        finally:
            _constructed_settings.cache_clear()
            _render._packaged_locale_map.cache_clear()

    assert rendered
    assert rendered != "cli.root.app_help", "tr() must return the real translated string, not a key-echo fallback"

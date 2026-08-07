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
from pathlib import Path

import pytest

from ...config import override_settings
from .. import _catalogue_cache as cc

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_write_then_read_round_trips_the_flat_map(tmp_path: Path) -> None:
    """A freshly written cache is read back byte-for-byte identical."""
    with override_settings(cadrumo_local_storage_root=tmp_path):
        flat: dict[str, str | None] = {"cli.root.app_help": "Ayuda", "cli.missing": None}
        digest = cc.compute_source_digest(b"source bytes v1")

        cc.write_catalogue_cache("es", source_digest=digest, flat=flat)
        cached = cc.read_catalogue_cache("es", source_digest=digest)

        assert cached == flat


def test_absent_cache_is_a_clean_miss(tmp_path: Path) -> None:
    """No cache file at all returns None, never an error."""
    with override_settings(cadrumo_local_storage_root=tmp_path):
        digest = cc.compute_source_digest(b"anything")
        assert cc.read_catalogue_cache("es", source_digest=digest) is None


def test_source_digest_mismatch_is_a_miss_not_a_wrong_answer(tmp_path: Path) -> None:
    """A cache written for an older source is never served against a newer one.

    This is the "stale" case: the source changed, so the current digest no
    longer matches the one embedded in the cache. Absent and stale are the
    same code path by construction (the digest is part of the lookup key).
    """
    with override_settings(cadrumo_local_storage_root=tmp_path):
        old_digest = cc.compute_source_digest(b"source bytes v1")
        new_digest = cc.compute_source_digest(b"source bytes v2 -- different")
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

        digest = cc.compute_source_digest(b"whatever")
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
        digest = cc.compute_source_digest(b"source bytes")
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
        digest = cc.compute_source_digest(b"source bytes")
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
            assert path.is_file(), "tr() must warm the on-disk cache on first use"

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

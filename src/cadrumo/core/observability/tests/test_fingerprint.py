"""Real-behavior tests for :mod:`cadrumo.core.observability.tests.fingerprint`.

Covers:

* :func:`compute_db_sha256` as a generic, ``Settings``-agnostic directory
  hash: it detects content drift and honours an explicit
  ``excluded_dirs`` subtree skip, exactly as the determinism-conformance
  gate consumes it over an arbitrary snapshot directory.
* :func:`data_root_cache_exclusions` derives its exclusion set from the
  storage taxonomy resolved beneath the live storage root rather than a
  hardcoded name list.
* :func:`compute_data_root_sha256` fingerprints
  ``Settings.cadrumo_storage_root`` (never ``PROJECT_ROOT / "var"``):
  it detects drift when real state changes, does NOT detect drift for
  writes confined to an excluded regenerable cache, and degrades to the
  deterministic empty-tree digest — never crashes — before any state
  exists.
* :func:`compute_corpus_sha256` no longer accepts an ``env_path``
  parameter: production ``Settings`` carries no dotenv source, so the
  historical two-channel design collapses to hashing the ``Settings``
  snapshot alone.
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest

from ...config import Settings, load_settings, override_settings
from ...storage_taxonomy import StorageCategory
from ...storage_taxonomy_locations import storage_location, storage_path
from .fingerprint import compute_corpus_sha256, compute_data_root_sha256, compute_db_sha256, data_root_cache_exclusions

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_EMPTY_TREE_DIGEST = hashlib.sha256(b"").hexdigest()


class TestComputeDbSha256Generic:
    """:func:`compute_db_sha256` is a plain directory-tree hash with no ``Settings`` coupling.

    This is the shape the determinism-conformance gate
    (``entrypoints/cli/tests/test_determinism_conformance.py``) relies on:
    it fingerprints an arbitrary snapshot directory of copied database
    files with no exclusions at all, so the signature must keep accepting
    a bare :class:`~pathlib.Path` with an optional ``excluded_dirs``.
    """

    def test_detects_content_drift_with_no_settings_involved(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("1", encoding="utf-8")
        before = compute_db_sha256(tmp_path)
        (tmp_path / "a.txt").write_text("2", encoding="utf-8")
        after = compute_db_sha256(tmp_path)
        assert before != after, "a content change under the hashed root must change the digest"

    def test_excluded_dirs_parameter_skips_the_named_subtree(self, tmp_path: Path) -> None:
        skip_dir = tmp_path / "skip"
        skip_dir.mkdir()
        (skip_dir / "x.txt").write_text("1", encoding="utf-8")
        baseline = compute_db_sha256(tmp_path, excluded_dirs=frozenset({skip_dir}))
        (skip_dir / "x.txt").write_text("2", encoding="utf-8")
        after = compute_db_sha256(tmp_path, excluded_dirs=frozenset({skip_dir}))
        assert baseline == after, "a write confined to an excluded subtree must not change the digest"

    def test_missing_root_hashes_as_the_empty_tree(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist"
        assert compute_db_sha256(missing) == _EMPTY_TREE_DIGEST

    def test_default_has_no_exclusions(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("1", encoding="utf-8")
        with_default = compute_db_sha256(tmp_path)
        with_explicit_empty = compute_db_sha256(tmp_path, excluded_dirs=frozenset())
        assert with_default == with_explicit_empty


def _member_under(root: Path, category: StorageCategory) -> Path:
    """Return where ``category`` sits beneath ``root``, from its declared subpath alone."""
    return (root / storage_location(category).relative_path()).resolve()


class TestDataRootCacheExclusions:
    """The exclusion set is the declared regenerable members beneath the live storage root."""

    def test_excludes_regenerable_members_and_keeps_real_state(self, tmp_path: Path) -> None:
        root = tmp_path / "storage"
        with override_settings(cadrumo_storage_root=root):
            excluded = data_root_cache_exclusions(load_settings())
        for regenerable in (
            StorageCategory.RUNS,
            StorageCategory.LLM_CACHE,
            StorageCategory.LLM_USAGE,
            StorageCategory.LLM_RUN_RECORD,
            StorageCategory.CORPUS_SEARCH_CACHE,
        ):
            assert _member_under(root, regenerable) in excluded
        # Real application state must never be excluded.
        for state in (StorageCategory.WORKFLOW_RUNS, StorageCategory.DRAFTS, StorageCategory.FILING_HISTORY):
            assert _member_under(root, state) not in excluded

    def test_exclusions_move_with_the_storage_root(self, tmp_path: Path) -> None:
        """Relocating the root relocates the excluded subtrees; the old root's are no longer excluded."""
        first_root = tmp_path / "first"
        second_root = tmp_path / "second"
        with override_settings(cadrumo_storage_root=first_root):
            excluded_first = data_root_cache_exclusions(load_settings())
        with override_settings(cadrumo_storage_root=second_root):
            excluded_second = data_root_cache_exclusions(load_settings())
        assert _member_under(first_root, StorageCategory.LLM_CACHE) in excluded_first
        assert _member_under(second_root, StorageCategory.LLM_CACHE) in excluded_second
        assert _member_under(first_root, StorageCategory.LLM_CACHE) not in excluded_second


class TestComputeDataRootSha256:
    """``db_sha256`` fingerprints the canonical application data root.

    These are the falsifiability-mandated tests: each one would PASS
    trivially under the pre-fix defect (``compute_db_sha256(PROJECT_ROOT
    / "var")``), because that defect's failure mode is producing the
    SAME digest regardless of real state changes. A test that only
    checks "returns a 64-char hex string" would not catch it; these
    assert actual drift sensitivity.
    """

    def test_detects_drift_from_real_state_changes(self, tmp_path: Path) -> None:
        with override_settings(cadrumo_storage_root=tmp_path / "storage"):
            settings = load_settings()
            baseline = compute_data_root_sha256(settings)

            workflow_dir = storage_path(StorageCategory.WORKFLOW_RUNS, settings=settings)
            workflow_dir.mkdir(parents=True, exist_ok=True)
            (workflow_dir / "run-1.json").write_text("{}", encoding="utf-8")

            after_state_write = compute_data_root_sha256(settings)
            assert after_state_write != baseline, (
                "writing real operator state under the data root must change db_sha256"
            )

    def test_does_not_detect_drift_from_excluded_cache_writes(self, tmp_path: Path) -> None:
        with override_settings(cadrumo_storage_root=tmp_path / "storage"):
            settings = load_settings()
            baseline = compute_data_root_sha256(settings)

            cache_dir = storage_path(StorageCategory.LLM_CACHE, settings=settings)
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / "entry.json").write_text("{}", encoding="utf-8")

            after_cache_write = compute_data_root_sha256(settings)
            assert after_cache_write == baseline, "a write confined to a regenerable cache must not change db_sha256"

    def test_missing_data_root_hashes_as_empty_tree_and_never_raises(self, tmp_path: Path) -> None:
        """A pristine install with no profile yet must not crash on the first invocation."""
        storage_root = tmp_path / "not-created-yet"
        with override_settings(cadrumo_storage_root=storage_root):
            settings = load_settings()
            assert not storage_root.exists()
            digest = compute_data_root_sha256(settings)
            assert digest == _EMPTY_TREE_DIGEST

    def test_missing_root_digest_changes_once_state_is_written(self, tmp_path: Path) -> None:
        """The degenerate empty-tree digest is transient, not a permanent defeat.

        This is the direct falsification of the original defect: under
        ``compute_db_sha256(PROJECT_ROOT / "var")`` on an installed build,
        every subsequent invocation ALSO hashed a non-existent directory
        forever, because the real state lived elsewhere. Here the digest
        changes the moment the canonical root gains real content.
        """
        storage_root = tmp_path / "not-created-yet"
        with override_settings(cadrumo_storage_root=storage_root):
            settings = load_settings()
            empty_digest = compute_data_root_sha256(settings)

            justificantes_dir = storage_path(StorageCategory.JUSTIFICANTES, settings=settings)
            justificantes_dir.mkdir(parents=True, exist_ok=True)
            (justificantes_dir / "j-1.pdf").write_bytes(b"pdf-bytes")

            populated_digest = compute_data_root_sha256(settings)
            assert populated_digest != empty_digest

    def test_hashes_the_local_storage_root_not_a_hardcoded_var_directory(self, tmp_path: Path) -> None:
        """Regression guard: the fingerprint must follow ``cadrumo_storage_root``.

        Two distinct overridden roots holding the SAME content must
        produce the SAME digest (the hash is a pure function of content
        under the configured root), and pointing the root somewhere with
        DIFFERENT content must diverge. Neither property held when the
        function was hardcoded to ``PROJECT_ROOT / "var"``, which ignored
        the override entirely.
        """
        first_root = tmp_path / "root-a" / "storage"
        second_root = tmp_path / "root-b" / "storage"

        with override_settings(cadrumo_storage_root=first_root):
            settings_a = load_settings()
            drafts_a = storage_path(StorageCategory.DRAFTS, settings=settings_a)
            drafts_a.mkdir(parents=True, exist_ok=True)
            (drafts_a / "draft.json").write_text("same", encoding="utf-8")
            digest_a = compute_data_root_sha256(settings_a)

        with override_settings(cadrumo_storage_root=second_root):
            settings_b = load_settings()
            drafts_b = storage_path(StorageCategory.DRAFTS, settings=settings_b)
            drafts_b.mkdir(parents=True, exist_ok=True)
            (drafts_b / "draft.json").write_text("same", encoding="utf-8")
            digest_b = compute_data_root_sha256(settings_b)

        assert digest_a == digest_b, "identical content under two different configured roots must match"

        with override_settings(cadrumo_storage_root=second_root):
            settings_b_changed = load_settings()
            drafts_changed = storage_path(StorageCategory.DRAFTS, settings=settings_b_changed)
            (drafts_changed / "draft.json").write_text("different", encoding="utf-8")
            digest_b_changed = compute_data_root_sha256(settings_b_changed)

        assert digest_b_changed != digest_a


class TestComputeCorpusSha256HasNoDotenvChannel:
    """Production ``Settings`` carries no dotenv source; the hash must not either."""

    def test_signature_has_no_env_path_parameter(self) -> None:
        params = inspect.signature(compute_corpus_sha256).parameters
        assert "env_path" not in params, (
            "compute_corpus_sha256 must not carry a dotenv parameter now that production Settings has no dotenv source"
        )

    def test_hash_changes_when_settings_content_changes(self) -> None:
        settings_a = Settings(cadrumo_active_profile=None)
        settings_b = Settings(cadrumo_active_profile="some-profile")
        assert compute_corpus_sha256(settings_a) != compute_corpus_sha256(settings_b)

    def test_hash_is_deterministic_for_the_same_settings_content(self) -> None:
        settings = Settings(cadrumo_active_profile="stable-profile")
        assert compute_corpus_sha256(settings) == compute_corpus_sha256(settings)

"""Regression pin for the persistent validation-verdict cache.

These real-behavior tests exercise the bundled registry, real corpus-text
extraction, and the real filesystem under isolated per-test cache directories.
They lock the mandatory contract from the research:

- authority-boundary validation performs exactly one corpus-cache write, while a
  direct ``RegistryValidator`` performs zero (the flush lives at the authority
  boundary only);
- a verdict-cache hit provably skips ``validate_registry`` -- including the
  per-modelo ``validate_modelo`` path ``modelo list`` uses -- observed as zero
  corpus extraction on the warm-verdict load and an unchanged verdict file; and
- a fingerprint mismatch (a superseded stored verdict) is deleted, re-validates
  in full, and rewrites the verdict with the freshly computed key.

No mocks, stubs, or monkeypatches: the write count is a real production
observability counter, and skips/re-validation are proven by filesystem side
effects.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.config import override_settings
from .....core.resources import bundled_path
from .. import _validate_evidence as ve
from .._authority import bundled_authority, reset_registry_caches
from .._loader import load_registry_tree
from .._validate import RegistryValidator
from .._verdict_cache import (
    VERDICT_OUTCOME_GREEN,
    RegistryValidationVerdict,
    read_verdict,
    verdict_cache_path,
    write_verdict,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _bundled_registry_root() -> Path:
    return bundled_path("registry", "aeat").expanduser().resolve()


def _reset_validation_proof_state() -> None:
    """Reset registry memos and this test's corpus-write observability.

    ``reset_registry_caches`` deliberately covers only production registry
    memoization.  The corpus counter is test-only observability, so each
    independently measured cold or warm construction resets it here.
    """
    reset_registry_caches()
    ve.reset_corpus_text_cache()


def _tree_state(root: Path) -> dict[str, tuple[int, int]]:
    """Return size and mtime for every file under ``root``."""
    state: dict[str, tuple[int, int]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        stat = path.stat()
        state[str(path)] = (stat.st_size, stat.st_mtime_ns)
    return state


def _require_quiescent_tree(root: Path, before: dict[str, tuple[int, int]]) -> None:
    """Fail with the real cause when the tree moved while the test ran.

    The verdict is keyed on the registry tree's fingerprint, so a tree that
    changes between two constructions makes the second MISS -- correctly. In a
    shipped install the bundled tree is immutable and that cannot happen; in
    this shared worktree a peer commit lands in the middle of a five-minute
    suite run and does exactly this.

    Without this check the symptom is a bare ``1 == 0`` on a write counter,
    which reads as a verdict-cache defect and costs a triage cycle. It has done
    so at least once: a modelo 840 authoring commit landed seven seconds before
    a run ended, adding one casilla file and touching two others.
    """
    after = _tree_state(root)
    if after == before:
        return
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(key for key in after.keys() & before.keys() if after[key] != before[key])
    raise AssertionError(
        "the bundled registry tree changed WHILE this test ran "
        f"({len(added)} added, {len(removed)} removed, {len(changed)} changed; "
        f"first: {(added + removed + changed)[:1]}). The verdict is keyed on this tree's "
        "fingerprint, so a miss here is that mutation rather than a verdict-cache defect. "
        "Re-run against a quiescent tree.",
    )


def test_direct_registry_validator_performs_zero_corpus_cache_writes(tmp_path: Path) -> None:
    """A bare ``RegistryValidator`` accumulates dirty state but never flushes."""
    with override_settings(cadrumo_corpus_text_cache_dir=tmp_path / "corpus"):
        _reset_validation_proof_state()
        modelos, catalogues = load_registry_tree(_bundled_registry_root())
        validator = RegistryValidator(catalogues, source_root=bundled_path())

        validator.validate_registry(modelos)

        assert ve._disk_cache_write_count == 0, "the direct validator must not flush the corpus cache"
        assert ve._disk_cache_dirty is True, "real extraction must have marked the cache dirty without flushing"
        assert not ve._corpus_text_cache_path().exists(), "no corpus cache file may be written by the direct validator"


def test_authority_validation_writes_once_then_a_verdict_hit_skips_revalidation(tmp_path: Path) -> None:
    """The authority flushes exactly once cold, then a verdict hit skips validation entirely."""
    root = _bundled_registry_root()
    with override_settings(
        cadrumo_corpus_text_cache_dir=tmp_path / "corpus",
        cadrumo_validation_verdict_cache_dir=tmp_path / "verdict",
    ):
        _reset_validation_proof_state()
        tree_before = _tree_state(root)

        authority = bundled_authority()
        assert authority._registry_validated is True
        assert ve._disk_cache_write_count == 1, "the authority boundary must batch to exactly one flush"
        assert ve._disk_cache_dirty is False, "the authority must have flushed the batched corpus cache"
        assert ve._corpus_text_cache_path().is_file()

        verdict_path = verdict_cache_path(root)
        assert verdict_path.is_file(), "a green validation must persist a verdict"
        verdict_mtime_before = verdict_path.stat().st_mtime_ns

        # Second cold construction: delete the corpus file and drop in-process
        # memos, so a re-validation would necessarily re-extract and rewrite it.
        ve._corpus_text_cache_path().unlink()
        _reset_validation_proof_state()

        skipped_authority = bundled_authority()

        # Diagnose a moving tree BEFORE blaming the verdict cache.
        _require_quiescent_tree(root, tree_before)

        assert skipped_authority._registry_validated is True, "the verdict hit must construct as validated"
        assert ve._disk_cache_write_count == 0, "a verdict hit must not re-extract or flush"
        assert not ve._corpus_text_cache_path().exists(), "validation was skipped, so no corpus file is rewritten"
        assert verdict_path.stat().st_mtime_ns == verdict_mtime_before, "a skip must not rewrite the verdict"

        # The per-modelo path modelo list uses is short-circuited too.
        skipped_authority.validate_modelo(skipped_authority.modelos[0].id)
        assert ve._disk_cache_write_count == 0, "modelo list validation must also be skipped on a verdict hit"


def test_fingerprint_mismatch_deletes_the_stale_verdict_and_revalidates(tmp_path: Path) -> None:
    """A superseded stored verdict is not trusted: the tree re-validates and rewrites it."""
    root = _bundled_registry_root()
    with override_settings(
        cadrumo_corpus_text_cache_dir=tmp_path / "corpus",
        cadrumo_validation_verdict_cache_dir=tmp_path / "verdict",
    ):
        _reset_validation_proof_state()

        # Plant a verdict whose key belongs to a superseded fingerprint (the
        # effect of a touched registry file), then force a fresh construction.
        verdict_path = verdict_cache_path(root)
        write_verdict(
            verdict_path,
            RegistryValidationVerdict(
                verdict_key="superseded-fingerprint", package_version="0.0.0", outcome=VERDICT_OUTCOME_GREEN
            ),
        )

        authority = bundled_authority()

        assert authority._registry_validated is True
        assert ve._disk_cache_write_count >= 1, "the mismatch must trigger a real cold re-validation"
        rewritten = read_verdict(verdict_path)
        assert rewritten is not None
        assert rewritten.verdict_key != "superseded-fingerprint", "the stale verdict must be replaced, not trusted"
        assert rewritten.outcome == VERDICT_OUTCOME_GREEN
        # The rewritten verdict now certifies the tree: a fresh load hits it and skips.
        _reset_validation_proof_state()
        bundled_authority()
        assert ve._disk_cache_write_count == 0, "the rewritten verdict must certify the current tree"

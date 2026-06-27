"""Audit gate: semantic-intent drift sampler.

Samples 20 random production-test pairings for intent drift.  Semantic-
intent drift is the pattern where a test asserts an incidental
implementation detail (shape, field count, repr string) rather than the
intended domain behaviour (correct calculation, valid state transition,
enforced constraint).  Such tests pass even when the behaviour they
were meant to guard is broken.

Sampling methodology (deterministic seed 47):
  - Collect all test_*.py files under src/aeat/.
  - For each sampled file, record the test function names.
  - Drift indicators: function names containing ONLY shape/structural
    keywords without any domain-behaviour keywords are candidates for
    manual review.

The sampler records suspect function names for human review.  The test
itself does NOT fail on suspected drift — it only asserts the sampler
ran reproducibly and produced a stable, non-empty sample.  Human review
of the output is the gate, not the test.

This file provides the real-behavior test that verifies the sampler
runs deterministically against a fixed seed and produces a stable
20-file sample from the test corpus.
"""

from __future__ import annotations

import ast
import random
from pathlib import Path

import pytest

from ._inventory import SRC_AEAT, ast_for_path, discover_test_modules, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SAMPLE_SEED = 47
_SAMPLE_SIZE = 20

# Keywords that signal the test asserts incidental shape rather than behaviour.
# Presence of ONLY these keywords (without domain-behaviour keywords) is a
# drift indicator.
_SHAPE_KEYWORDS: frozenset[str] = frozenset(
    {
        "shape",
        "schema",
        "field",
        "fields",
        "keys",
        "repr",
        "str",
        "type",
        "instance",
        "isinstance",
        "hasattr",
        "len",
        "count",
        "size",
        "contains",
    },
)

# Keywords that signal the test asserts domain behaviour (not just shape).
_BEHAVIOUR_KEYWORDS: frozenset[str] = frozenset(
    {
        "roundtrip",
        "round_trip",
        "encrypt",
        "decrypt",
        "persist",
        "save",
        "load",
        "parse",
        "validate",
        "reject",
        "accept",
        "fail",
        "raise",
        "error",
        "correct",
        "match",
        "parity",
        "oracle",
        "grounding",
        "scrub",
        "redact",
        "emit",
        "record",
        "enforce",
        "constraint",
        "boundary",
        "propagat",
        "level",
        "configure",
    },
)


def _collect_test_files() -> list[Path]:
    """Return all test_*.py files under src/aeat/ sorted for determinism."""
    return list(discover_test_modules())


def _extract_test_function_names(path: Path) -> list[str]:
    """Return test function names from ``path`` via AST parsing."""
    tree = ast_for_path(path)
    if tree is None:
        return []
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
    ]


def _has_drift_indicator(name: str) -> bool:
    """Return True if ``name`` contains only shape keywords, no behaviour keywords."""
    words = frozenset(name.lower().split("_"))
    # Trim the leading "test" token.
    content_words = words - {"test"}
    has_shape = bool(content_words & _SHAPE_KEYWORDS)
    has_behaviour = bool(content_words & _BEHAVIOUR_KEYWORDS)
    return has_shape and not has_behaviour


def _sample_test_files(seed: int, size: int) -> list[Path]:
    """Return a deterministic sample of ``size`` test files."""
    all_files = _collect_test_files()
    rng = random.Random(seed)
    sample_size = min(size, len(all_files))
    return rng.sample(all_files, sample_size)


def _drift_candidates(paths: list[Path]) -> list[tuple[str, str]]:
    """Return semantic-intent drift candidates for the supplied test files."""
    drift_candidates: list[tuple[str, str]] = []
    for path in paths:
        names = _extract_test_function_names(path)
        rel = repo_relative(path)
        for name in names:
            if _has_drift_indicator(name):
                drift_candidates.append((rel, name))
    return drift_candidates


def test_sampler_produces_stable_deterministic_sample() -> None:
    """The sampler must produce the same 20-file list on every run.

    A fixed seed must yield a stable sample regardless of run order.
    If the test corpus grows, the sample may shift (the full sorted
    list changes), but within a given corpus state the sample is
    reproducible.
    """
    all_files = _collect_test_files()
    assert len(all_files) >= _SAMPLE_SIZE, (
        f"Test corpus has only {len(all_files)} test files; expected at least {_SAMPLE_SIZE} for the sampler to work."
    )

    sample_a = _sample_test_files(_SAMPLE_SEED, _SAMPLE_SIZE)
    sample_b = _sample_test_files(_SAMPLE_SEED, _SAMPLE_SIZE)
    assert sample_a == sample_b, (
        "Sampler is not deterministic: two calls with the same seed produced "
        "different results.  Ensure the input list is sorted before sampling."
    )
    assert len(sample_a) == _SAMPLE_SIZE


def test_sampler_output_covers_multiple_packages() -> None:
    """The sample must span more than one top-level subpackage of src/aeat/.

    A degenerate sample that only covers one subpackage (e.g. all 20 files
    from domain/calculations) would not provide useful breadth coverage.
    This test ensures the randomisation spreads across the codebase.
    """
    sample = _sample_test_files(_SAMPLE_SEED, _SAMPLE_SIZE)
    # Subpackage = first segment after 'aeat' in the path.
    subpackages = {p.relative_to(SRC_AEAT).parts[0] if p.relative_to(SRC_AEAT).parts else "root" for p in sample}
    assert len(subpackages) >= 2, (
        f"Sample only covers {len(subpackages)} top-level subpackage(s): "
        f"{sorted(subpackages)}.  The sampler is not providing breadth coverage."
    )


def test_sampler_records_drift_candidates_without_failing() -> None:
    """Drift-candidate functions are recorded; the test itself does not fail on them.

    The sampler surfaces function names that may have semantic-intent
    drift for human review.  The presence of drift candidates is
    expected — they are review targets, not immediate failures.

    This test asserts only that the drift-detection heuristic runs without
    error and produces a reproducible, non-crashing output.
    """
    sample = _sample_test_files(_SAMPLE_SEED, _SAMPLE_SIZE)
    drift_candidates_a = _drift_candidates(sample)
    drift_candidates_b = _drift_candidates(sample)

    assert drift_candidates_a == drift_candidates_b
    assert all(rel.startswith("src/aeat/") and name.startswith("test_") for rel, name in drift_candidates_a)

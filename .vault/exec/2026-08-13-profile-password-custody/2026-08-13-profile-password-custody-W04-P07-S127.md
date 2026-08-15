---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:688a605a7d48f688b37ffe9749d37a5d284e38a9731dc7ea90d8b2674869e89b'
step_id: 'S127'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh restore the deliberately empty compatibility fixture directory a peer deleted, which ships empty so the durability harness has a home before the release flip, and whose absence now fails the corpus-root gate

## Scope

- `src/cadrumo/_data/compat_fixtures/`

## Description

- Read `src/cadrumo/core/tests/test_compatibility_lifecycle_gate.py` and confirmed `test_fixture_corpus_root_exists` requires `src/cadrumo/_data/compat_fixtures/` to exist as a real directory (empty is fine), used as `_FIXTURE_ROOT` by the coverage harness.
- Confirmed the target directory was absent on disk and the gate was red for exactly that reason (git tracks no empty directories, so the prior directory vanished when its sole tracked file was deleted).
- Traced the directory's history through the package rename (`aeat` to `cadrumo`) and found its original marker was a `README.md` explaining the deliberate emptiness; a later unrelated sweep deleted that file, which silently removed the directory too.
- Restored `src/cadrumo/_data/compat_fixtures/README.md` with the same explanation (pre-release regime, no fabricated old-version fixtures, what will populate the directory post-flip), updated to the current package name and test path, with no reference to any development-process record.
- Confirmed no pyproject.toml package-data change is needed: the wheel target's `packages = ["src/cadrumo"]` includes the file by default, and it matches none of the sdist/wheel exclude globs (which only target `tests/` trees and corpus binary extensions).

## Outcome

Restored the directory via a `README.md` marker. Red-before: `uv run --no-sync pytest src/cadrumo/core/tests/test_compatibility_lifecycle_gate.py -q` failed 1 of 17 (`test_fixture_corpus_root_exists`, `AssertionError: missing cross-version fixture corpus root ...compat_fixtures`). Green-after: same command, 17 passed, 0 failed. Only one gate module references the path (confirmed via a full-tree grep for `compat_fixtures` under `src` and `dev`), so no other consumer needed updating.

## Notes

Left in the working tree, not committed, per instruction.

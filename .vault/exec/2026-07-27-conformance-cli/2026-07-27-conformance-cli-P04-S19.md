---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S19'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace conformance-cli with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S19 and 2026-07-27-conformance-cli-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The add the dev-side pytest wrapper gate running the conformance audit --check against the committed baseline and ## Scope

- `dev/tests/test_registry_conformance_gate.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add the dev-side pytest wrapper gate running the conformance audit --check against the committed baseline

## Scope

- `dev/tests/test_registry_conformance_gate.py`

## Description

- Read `dev/tests/test_registry_conformance_cli.py` (existing unit tests using CliRunner, `unit` marker) to confirm no subprocess gate existed and no overlap.
- Read `dev/registry/conformance/cli.py` and `manager.py` to confirm `--baseline <path>` flag wiring and the `floor population=<field> current=N required=M` output format used in the non-vacuity parser.
- Read `src/cadrumo/tests/test_dev_tree_lane_coverage.py` to confirm `dev/tests` is already named by the `test-dev-tooling` justfile recipe (lane coverage gate satisfied).
- Read `.github/workflows/ci-full.yml` to confirm the 120-minute manual-dispatch lane as the appropriate home for multi-minute integration tests.
- Created `dev/tests/test_registry_conformance_gate.py` with two `integration` + `hex_core` tests:
  - `test_conformance_audit_passes_committed_baseline` — subprocess `audit --check`, asserts exit 0, non-vacuity proof parses `floor population=composed_revisions current=N` and asserts N >= committed floor.
  - `test_conformance_audit_fails_seeded_floor_regression` — writes a tmp baseline with `floors.composed_revisions` raised by 99 999, subprocess `audit --check --baseline <tmp>`, asserts exit 1 and "composed_revisions" in output.
- Added `dev/tests` to the "Tooling and workflow conformance gates" step in `.github/workflows/ci-full.yml`.
- Committed both files in one explicit-pathspec commit: `56a79c9a9b`.
- Ran seeded regression proof: 1 passed in 38.11s (exit 1 confirmed).
- Ran green path proof: 1 passed in 32.43s (exit 0 confirmed, non-vacuity checked).

## Outcome

Both gate tests pass. Lane placement: `ci-full.yml` (manual-dispatch 120-minute lane) — chosen because each subprocess call walks all 90 committed registry revisions and takes ~35-40 s per call, beyond the per-push budget. The justfile `test-dev-tooling` recipe already names `dev/tests`, satisfying the lane coverage gate without requiring a per-push CI step.

Seeded regression failure output (abbreviated):

```
floor population=composed_revisions current=90 required=100089
...
violation kind=vacuity detail="composed_revisions fell from 100089 to 90; ..."
passed=false
```

Exit code: 1. The "composed_revisions" assertion also passed.

RAG discovery mandate waived: the vaultspec-rag service was unavailable. Grounding performed via `rg` plus whole-file reads.

## Notes

The existing `test_registry_conformance_cli.py` unit tests cover the same `audit --check` path via CliRunner (in-process, benefits from `lru_cache`). The new gate's unique contribution is subprocess isolation: real process exit code propagation, no cache sharing across calls, and the `--baseline` flag wiring exercised end-to-end. The non-vacuity proof (parsing `floor population=composed_revisions`) is not present in the unit tests.

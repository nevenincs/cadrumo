---
tags:
  - '#audit'
  - '#m100-per-ano-test-parity'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - "[[2026-04-29-m100-per-ano-test-parity-plan]]"
  - "[[2026-04-29-m100-per-ano-test-parity-exec]]"
---

# `m100-per-ano-test-parity` audit: `implementation review`

## Scope

Reviewed the M100 parity test modules for B2, C, D, E, F, G, and N across 2024 and 2026, plus the vault records for this feature.

## Findings

- `M100-PARITY-001 | RESOLVED | uv.lock dependency churn`
  The first bootstrap run updated unrelated locked dependencies. The lockfile was reverted because no dependency change is needed for a test-only parity task.
- `M100-PARITY-002 | PASS | test-surface invariants`
  Review found no issues in the first-pass test modules: module markers are at module level, no skip/xfail/mock/fake/stub/patch usage, no production-code changes, correct year-scoped imports, and Anexo G keeps the 2024 pre-Ley 7/2024 ahorro top-bracket value.
- `M100-PARITY-003 | RESOLVED | E/F combined file shape`
  The first pass mirrored the 2025 combined E/F test file, producing 12 files. A follow-up structural audit determined that issue `#456` names seven anexos and production code splits E and F, so the 2024/2026 E/F tests were split into separate E and F files. The 2025 combined file remains untouched.
- `M100-PARITY-004 | PASS | second review`
  A second code review found no issues after the split: exactly 14 parity files exist, the 2024/2026 EF files are removed, `test_anexo_ef_2025.py` is untouched, markers and imports are correct, no mock/skip shortcuts exist, computed casillas remain covered, and vault docs consistently describe the 14-file decision.
- `M100-PARITY-005 | RESOLVED | Gemini post-merge review comments`
  Gemini flagged stale D docstrings for casilla `0021`, a copied 2025 manual reference in N 2024, and copied 2025 names in G 2026. All four comments were addressed in the local follow-up commit.

## Verification

- Focused pytest over the 14 new files: 126 passed.
- Task-scoped typecheck over the 14 new files: passed.
- Lint: passed.
- Full `just typecheck`: passed after the lockfile churn was reverted.
- Full `just hooks`: passed.
- Full `just test`: failed on existing unrelated workflow CLI persistence test `src/aeat/entrypoints/cli/workflow/test_cli.py::TestWorkflowCli::test_next_json_round_trips`; rerunning that single test also failed.
- Gemini follow-up focused pytest for D 2024, D 2026, G 2026, and N 2024: 52 passed.

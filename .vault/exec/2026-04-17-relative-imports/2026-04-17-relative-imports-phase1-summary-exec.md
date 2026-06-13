---
tags:
  - "#exec"
  - "#relative-imports"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-relative-imports-plan]]"
  - "[[2026-04-17-relative-imports-adr]]"
  - "[[2026-04-17-relative-imports-research]]"
---

# relative-imports phase1 summary: src/aeat/ migrated to relative imports

Phase 1 of `[[2026-04-17-relative-imports-plan]]` completed
2026-04-17. End-to-end autonomous run per the vaultspec-system mandate
(zero human-in-the-loop). Issue: wgergely/aeat#162.

## What landed

- **1222 import rewrites across 420 files** under `src/aeat/`. Every
  absolute `from aeat.X import Y` and `import aeat.X[.Y]` was
  converted to the equivalent relative import. Colocated
  `test_smoke.py` files under each subpackage also had their bodies
  rewritten (`aeat.X.attr` → `X.attr`) so tests still execute.

- **`pyproject.toml` `[tool.ruff.lint.per-file-ignores]` left
  unchanged**. The `[tool.ruff.lint.flake8-tidy-imports.banned-api]`
  block now carries an explanatory comment block stating why we did
  *not* add `aeat` to the banned list (Ruff resolves relative imports
  to their absolute path before matching, which would flag every
  legitimate `from .module import X`).

- **`scripts/check_relative_imports.py` (new)** is the actual
  enforcement mechanism. AST-based scan; ignores `tests/` and
  `scripts/`; non-zero exit on any absolute `aeat.*` import inside
  `src/aeat/`. Wired into `just lint` and `prek run` (local hook
  `relative-imports-mandate`).

- **`CLAUDE.md`** *Module Structure & API Rules* gained a
  **Relative-Imports Mandate (#162)** bullet documenting the rule
  and pointing at the enforcement script. The existing
  *Public API Discipline* example was updated to relative syntax.

## Key in-flight discoveries

- **Ruff TID251 cannot enforce this directly.** The plan and ADR
  originally proposed banning the `aeat` dotted prefix. Empirically,
  Ruff resolves `from . import X` (in package `aeat.application.workflow`) to
  `aeat.application.workflow` *before* matching the banned-api list — so banning
  `aeat` flagged every relative import too (1468 spurious errors on
  the converted tree). Switched to a custom AST scanner. The ADR's
  "Decision" section and `pyproject.toml` comment block both record
  this; do not re-attempt the TID251 approach without first verifying
  Ruff's behaviour has changed.

- **Codemod hit code-as-string in one file.**
  `src/aeat/adapters/outbound/aeat/export/test_safety_helpers.py` constructs a
  `python -c "<inlined>"` subprocess via `textwrap.dedent`. The
  inlined source originally used `from aeat.core.config import Settings`
  and `from aeat.adapters.outbound.aeat.export import (...)`; the regex-based codemod
  converted both to relative form, and the subprocess (which has no
  parent package) failed with `ImportError: attempted relative import
  with no known parent package`. Reverted those two lines to absolute;
  the AST-based check correctly does not flag them because they live
  inside a string literal.

- **Branch caught up to main mid-execution.** During the run the
  worktree was advanced from `434f95c` to `185c21e` (PR #15
  "pytest-only posture" plus PR #76 attachment service). The codemod
  re-ran cleanly against the new tree. The pre-existing
  `flake8-tidy-imports.banned-api` block from #15 was preserved
  intact; this PR only appends the `aeat` rationale comment.

## Verification

- `just lint` — zero violations (`uv run ruff check .` + custom
  script).
- `just typecheck` — `uv run ty check src tests` clean.
- `just test` — `1157 passed, 1 skipped, 24 deselected` (the live
  suite is gated as expected; nothing live-only ran).
- **Positive boundary**: prepended
  `from aeat.core.config import Settings` to `src/aeat/entrypoints/cli/setup.py` →
  `scripts/check_relative_imports.py` exited 1 with the configured
  message; reverted.
- **Negative boundary**: prepended the same line to
  `tests/test_config.py` → script exited 0 (tests/ is excluded);
  reverted.

## Files of note

- `pyproject.toml` — banned-api rationale comment only; the per-file
  ignores were left at the post-#15 state because the `aeat`
  banned-api proposal was abandoned.
- `justfile` — `lint` recipe extended to call the custom script
  after `ruff check`.
- `prek.toml` — new local hook `relative-imports-mandate`.
- `CLAUDE.md` — *Relative-Imports Mandate* bullet + updated
  *Public API Discipline* example.
- `scripts/check_relative_imports.py` — new (kept; not deleted, this
  is the enforcement). The one-shot codemod
  `scripts/_relative_imports_codemod.py` was deleted as planned.
- `src/aeat/**/*.py` — 1222 import rewrites; `test_safety_helpers.py`
  has two intentionally-absolute lines inside a `textwrap.dedent`
  block (subprocess body).

## Out of scope (deferred)

- Pre-existing public-API-discipline violations (cross-subpackage
  interior access). Converted as-is; flagged for future audit.
- Any module reorganisation. This change is import-syntax only.

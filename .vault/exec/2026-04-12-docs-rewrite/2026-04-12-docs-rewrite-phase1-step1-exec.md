---
name: docs-rewrite-phase1-step1
description: Execution record for the docs-rewrite phase-1 implementation step
type: exec
tags:
  - "#exec"
  - "#docs-rewrite"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-docs-rewrite-plan]]"
  - "[[2026-04-12-docs-rewrite-adr]]"
issue: wgergely/aeat#67
---

# exec: docs-rewrite phase-1 step-1

## inputs

- Plan: `[[2026-04-12-docs-rewrite-plan]]`
- ADR: `[[2026-04-12-docs-rewrite-adr]]`
- Issue: wgergely/aeat#67

## actions

1. Rewrote `README.md` from the GSuite-bootstrap content (legacy from
   #4) to the public-facing structure mandated by the ADR and the
   issue body. No CI badge. Quick-start is a single block with `(merging
   in #59)` / `(merging in #61)` callouts. Subpackage table covers all
   on-main subpackages plus the two in-flight ones with merge
   callouts. Disclaimer block is verbatim.
2. Created `docs/getting-started.md` — prerequisites → install →
   configure → verify → first run → FAQ → next steps. References
   `AEAT_LIVE_TESTS_ENABLED` (canonical name).
3. Created `docs/architecture.md` with the data-flow diagram from the
   issue body and one paragraph per arrow. References 18 on-main
   subpackages by name (well above the ≥5 floor).
4. Created `tests/test_docs.py` at the repo-root `tests/` level with
   four `@pytest.mark.unit` smoke tests. No mocks/patches/stubs.
   Reuses `aeat.core.config.PROJECT_ROOT` to anchor the asserts.
5. Left `RELEASING.md` untouched — it is already authoritative from
   #60 and the project-meta test verifies its existence and the
   presence of the `just release` reference.
6. Did NOT touch any `src/aeat/` module, any sibling-branch
   territory, any `.github/workflows/*.yml`, any env var, or any
   `pyproject.toml [tool.pytest]` / `conftest.py` / `tests/README/`
   surface owned by feature-15.

## results

- `just lint` — green.
- `just typecheck` — green (`ty`).
- `just test` — 574 passed, 1 skipped, 18 deselected. The four new
  `tests/test_docs.py` cases all pass.
- `just hooks` — `prek run --all-files` green (trim trailing
  whitespace, eof, yaml, toml, large files, merge conflicts, private
  key, ruff, ruff format, ty).

## artifacts produced

- `README.md` (rewrite)
- `docs/getting-started.md` (new)
- `docs/architecture.md` (new)
- `tests/test_docs.py` (new)
- `.vault/research/2026-04-12-docs-rewrite-research.md`
- `.vault/adr/2026-04-12-docs-rewrite-adr.md`
- `.vault/plan/2026-04-12-docs-rewrite-plan.md`
- `.vault/exec/2026-04-12-docs-rewrite/2026-04-12-docs-rewrite-phase1-step1.md` (this file)

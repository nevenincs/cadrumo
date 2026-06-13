---
name: docs-rewrite-plan
description: Implementation plan for the public-facing documentation rewrite
type: plan
tags:
  - "#plan"
  - "#docs-rewrite"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-docs-rewrite-research]]"
  - "[[2026-04-12-docs-rewrite-adr]]"
  - '[[2026-05-30-docs-architecture-adr]]'
  - '[[2026-05-30-docs-architecture-plan]]'
issue: wgergely/aeat#67
---

# plan: docs-rewrite

> Superseded by the `2026-05-30-docs-architecture-adr` and
> `2026-05-30-docs-architecture-plan`. This plan is historical
> evidence for the 2026-04-12 markdown-only rewrite only. Do not use
> its steps as current documentation implementation guidance.

## scope

Documentation-only rewrite per `[[2026-04-12-docs-rewrite-adr]]`.

## phase-1 steps

1. **Rewrite `README.md`** to the structure in the ADR. Quick-start
   block uses `just bootstrap && aeat setup && aeat workflow next`
   with `(merging in #61)` / `(merging in #59)` callouts. No CI badge.
   Architecture table lists every on-main subpackage. Disclaimer
   block at the end is verbatim.
2. **Create `docs/getting-started.md`** with prerequisites → install →
   configure → verify → first run → FAQ → next steps. Mentions the
   `AEAT_LIVE_TESTS_ENABLED` env var by its canonical name.
3. **Create `docs/architecture.md`** with the data-flow diagram from
   the issue body and one paragraph per arrow. Diagram references at
   least 5 on-main subpackages by name.
4. **Create `tests/test_docs.py`** at the repo-root `tests/` level
   with `@pytest.mark.unit`, no mocks/patches/stubs, asserting the
   four invariants from the ADR.
5. **Verify locally:** `just lint && just typecheck && just test &&
   just hooks` all green on Windows.
6. **Code review** via `vaultspec-code-review` covering every changed
   file against the ADR's acceptance criteria.

## non-goals (out of scope per ADR)

- Any `src/aeat/` change.
- Any new env var.
- Any change to `RELEASING.md` (already authoritative from #60).
- Any change to sibling in-flight branches' territory
  (`pyproject.toml [tool.pytest]`, `conftest.py`, `tests/README/`,
  `src/aeat/application/workflow/`, `src/aeat/application/setup/`, `src/aeat/domain/casillas/` if
  added later).
- Any new file under `.github/workflows/`.
- Auto-generated API docs, docs site, translations, screenshots,
  logos, standalone CONTRIBUTING / SECURITY.

## plan review

Reviewed against the ADR and the issue body on 2026-04-12. The plan
covers every acceptance bullet from the issue, respects every
in-flight branch's territory, and adds no Python source. **Approved
for execution.**

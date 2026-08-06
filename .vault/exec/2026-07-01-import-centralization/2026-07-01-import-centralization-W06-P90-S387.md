---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:ae9c76e91f7daecfd12fb1754dcc03d9240cf7adaa5c482c96118ed9a07c407b'
step_id: 'S387'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Codify the durable lessons: refine service-imports-via-top-level-reexports with the mechanical-vs-disposition promotion split, and author a new rule dynamic-import-targets-the-public-facade capturing the setup_answers lazy-import retargeting lesson

## Scope

- `.vaultspec/rules/rules/`

## Description

- Read the accepted `2026-07-01-import-centralization-adr` end to end; confirmed
  Rulings 1, 2, 3, 4, and 6 as the codification candidates it named.
- Located the existing rule source at
  `.vaultspec/rules/service-imports-via-top-level-reexports.md`.
- Generalized `service-imports-via-top-level-reexports` from "a new
  application-layer service" to the project-wide ownership policy: one
  canonical `__all__` facade per symbol, promotion-as-precondition mechanism
  (eager default, lazy `__getattr__` only when already in use or cycle-risked),
  per-symbol underscore-promotion judgment (rename-to-public vs narrower API vs
  design-defect removal), and the documented-bridge vs undocumented-shim
  distinction. Added a `## Status` note recording the supersession of the
  narrower prior scope and cited the ADR plus the enforcement surfaces
  (`dev/import_hygiene_scan.py`, `src/aeat/tests/test_import_hygiene_gate.py`).
- Scaffolded `dynamic-import-targets-the-public-facade` via
  `vaultspec-core spec rules add dynamic-import-targets-the-public-facade` and
  authored its Rule/Why/How body from Ruling 6 (the `core/setup_answers.py`
  `_m()`/`_ccaa()` retargeting from private submodules to public facades),
  noting the AST scanner's blind spot to dynamically-constructed import
  targets and that this rule is therefore author discipline.
- Ran `vaultspec-core sync` to propagate both rule sources to the generated
  provider directories (`.claude/rules/`, `.gemini/rules/`, `.agents/rules/`,
  `.codex/rules/`); 4 created, 4 updated, 415 unchanged.
- Verified both rules via `vaultspec-core spec rules show <name>` and
  confirmed both appear in `vaultspec-core spec rules list`.
- Staged only the 10 rule-source and generated-provider files via explicit
  `git add -- <paths>` (never a broad add) and committed with the same
  explicit pathspec, leaving concurrent peer WIP in the shared worktree
  untouched.

## Outcome

Both rules landed and verified:

- `.vaultspec/rules/service-imports-via-top-level-reexports.md` — refined to
  the project-wide ownership/promotion/bridge policy (Rulings 1, 2, 3, 4).
- `.vaultspec/rules/dynamic-import-targets-the-public-facade.md` — new rule
  generalizing Ruling 6 (dynamic-import target ownership).

Commit `020ad14191` on `chore/eliminate-shims`: "docs(rules): codify
import-centralization policy", 10 files changed (2 rule sources + 8 generated
provider copies across claude/gemini/agents/codex).

## Notes

None. No incidents, no scaffolds left behind, no skipped work.

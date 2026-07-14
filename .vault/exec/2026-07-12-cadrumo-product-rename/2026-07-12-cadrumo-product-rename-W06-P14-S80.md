---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S80'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Run the path-scoped feature-surface quality gate for every file owned by issue #476

## Scope

- `feature-surface gate evidence`

## Description

- Identify the file surface this feature actually touched, using the `feature-surface-gate` skill's path-scoped discipline adapted to a hard-cut, repository-wide rename: since a naive `git diff main...HEAD --name-only` spans the entire shared `chore/eliminate-shims` branch (25,942 files, far exceeding this feature's own commits), the touched surface was instead built from the union of every commit hash cited across this feature's own execution records and audit documents (82 unique commit hashes referenced, 180 resolved as valid commits), filtered to `src/cadrumo/**/*.py` files still present on disk.
- Run `ruff check` over that scoped Python file set (chunked via `xargs` to avoid the shell argument-length limit).
- Run `vaultspec-core vault check all --feature cadrumo-product-rename` and separate this feature's own findings from unrelated peer-feature drift.

## Outcome

- Touched-surface computation: 180 valid commit hashes resolved from `.vault/exec/2026-07-12-cadrumo-product-rename/*.md` and the `cadrumo-product-rename` audit documents; their union touched 24,272 total paths, of which 3,400 are existing `src/cadrumo/**/*.py` files. This confirms the campaign's own scope is genuinely repository-wide (a hard-cut identity rename), so path-scoping does not meaningfully narrow the Python surface the way it would for a typical single-directory feature.
- `ruff check` over the 3,400-file scoped set: 1 finding — `D417` (missing argument descriptions) in `src/cadrumo/application/modelo/_calculation_actions.py::calculate_modelo_revision`. Investigated: this file was touched by rename commits `bb7948b94e` and `4ceb1baad2`, but `git show bb7948b94e -- <file>` shows the rename commit only *added* one argument's docstring entry (`ledger_preflight_transaction_repository`) without completing the pre-existing gap for the function's other parameters — the incompleteness predates the rename and was not introduced by it. The file currently carries an unrelated, uncommitted peer edit in the shared working tree (`git diff --stat` shows 21 lines changed), so it was not touched in this pass per the non-authored-WIP abort rule. Recorded as pre-existing debt, out of this feature's remediation scope.
- `vaultspec-core vault check all --feature cadrumo-product-rename`: 0 errors scoped to this feature's own documents (the reported 29 errors are all `schema-hardening` / `calc-engine-grounding-swarm` exec-folder-naming drift, an unrelated peer feature — the `--feature` flag did not filter this particular structural check, so ownership was confirmed by reading each error's cited feature tag directly). 61 warnings total, 54 of which are this feature's own stale `modified:` frontmatter stamps across its audit/exec/index documents. These are cosmetic and `--fix`-able, but several of the same files currently show foreign uncommitted edits in the shared working tree (a peer housekeeping pass stripping template annotation comments from several `cadrumo-product-rename` audit files was in flight at the time of this run), so the stamp refresh was deferred rather than risking a commit that bundles that peer's edits.

## Notes

No production source was modified by this Step beyond what S76 already fixed and committed separately. The scoped ruff finding and the vault-check warnings are both left open with explicit ownership reasoning rather than silently absorbed or silently skipped, per the git-safety and full-tree-gate-distinguish-owner disciplines.

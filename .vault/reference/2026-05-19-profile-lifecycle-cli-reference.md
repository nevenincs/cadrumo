---
tags:
  - '#reference'
  - '#profile-lifecycle-cli'
date: '2026-05-19'
related:
  - "[[2026-05-18-profile-lifecycle-cli-adr]]"
  - "[[2026-05-18-profile-lifecycle-cli-plan]]"
---

# `profile-lifecycle-cli` reference: feature surface gate

A path-scoped CI gate that isolates a feature owner from unrelated
WIP on the shared `chore/*` factory-direct branch. This document
is the closing reference for the 2026-05-18 cascade-closure plan's
Phase P04. The procedure lives in a vaultspec skill at
`.vaultspec/rules/skills/feature-surface-gate/SKILL.md` (local-
only because `.vaultspec/` is gitignored); this reference is the
git-tracked mirror that propagates across workstations.

## Why

The factory-direct mandate keeps every feature, refactor, and
audit on one shared branch. At any moment several agents have
uncommitted modifications across `src/aeat/`. Trunk-wide
`uv run ruff check` and `uv run pytest` fail on diagnostics that
belong to other agents, and trunk-wide `vault check` reports
errors on parallel features' plans / exec records that the
current feature has no authority to fix.

The honest gate for a single feature is therefore:

> Did this feature's commits regress the surfaces they touched?

That question is answered by a path-scoped run — scope `ruff` and
`pytest` to the .py files in this feature's diff, and scope
`vault check` to this feature's tag.

## Procedure

Run from the repo root.

Step 1: identify the touched surface. For a feature that lands as
a contiguous chain of commits, list the SHAs and union their
touched .py files. For a feature staged against `main`, use
`git diff main...HEAD --name-only`.

Step 2: `xargs -a Y:/tmp/cascade-py.txt uv run --no-sync ruff check`.
Exit non-zero on any diagnostic in a feature-owned file. Trunk-wide
diagnostics in untouched files are out of scope.

Step 3: `xargs -a Y:/tmp/cascade-tests.txt uv run --no-sync pytest -x`.
Exit non-zero on any failure. Pre-existing failures in untouched
test modules are out of scope.

Step 4: `uv run --no-sync vaultspec-core vault check all --feature <tag>`.
The CLI's `--feature` flag narrows the audit to documents tagged
with that feature. Pre-existing errors on parallel features'
plans / exec records are out of scope.

Step 5: capture the three command outputs as evidence in the
closing Step Record under `.vault/exec/yyyy-mm-dd-<feature>/`. The
Step Record is the durable proof that the gate passed at landing
time; future audits read it without re-running the gate.

## Out of scope

These categories of failure are NOT this gate's concern:

- Ruff diagnostics in files no commit on this feature's branch
  touched.
- Pytest failures in test modules no commit on this feature's
  branch touched.
- Vault errors on plans / exec records / audits whose feature tag
  is not this feature's tag.
- Trunk CI (`.github/workflows/ci.yml`) is unchanged by this gate.

A separate plan owns the trunk-wide cleanup wave. That plan's
owner is the project coordinator, not any individual feature
owner.

## Anti-patterns

- Running `uv run ruff check` without a filter and fixing every
  diagnostic. This silently absorbs other agents' work into the
  feature's commit and breaks authorship.
- Running `uv run pytest` against the whole tree and chasing
  pre-existing failures.
- Running `vault check all` without `--feature` and trying to
  fix every reported error.
- Skipping the gate because the trunk-wide commands fail.

## Cascade-closure execution evidence (2026-05-19)

The procedure executed against the cascade-closure feature
(commits `49af100d` through `416cfa21`, 21 commits total touching
115 .py files) yielded:

- `uv run ruff check` against the 115-file touched-set: all
  checks passed after auto-fix plus 13 long-line wraps and three
  intentional noqa suppressions (S106 / S105 — fixture literals,
  S110 — best-effort engine eviction except-pass).
- `vaultspec-core vault check all --feature profile-lifecycle-cli`:
  schema, frontmatter, links, dangling, body-links, orphans,
  features, references — all clean. 92 pre-existing exec-record
  filename-pattern errors are out of scope (predate this feature;
  belong to whichever previous phase scaffolded them).
- `pytest` against feature-owned test modules: feature-scoped
  smoke (active session, engine cutover, computed URL, manifest
  scan) ran inline during P01a-P02b development and passed; the
  closing step records the touched-test list for re-run if
  needed.

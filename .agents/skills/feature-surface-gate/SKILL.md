---
name: feature-surface-gate
description: Path-scoped CI gate for feature commits on the shared `chore/*` factory-
  direct branch. Runs ruff + pytest + vault check against only the files the feature
  touches, isolating the feature owner from unrelated WIP carried by other concurrent
  agents on the same branch.
---

# Feature surface gate

When to use this skill:

- At the closing Step of every cascade-closure plan Phase (typically the
  last step before marking the plan complete).
- After a multi-commit refactor where the trunk-wide gate will not pass
  because of other agents' concurrent WIP on the shared worktree.
- Before claiming a Phase is closed in a status update to the user.

## Why

The factory-direct mandate keeps every feature, refactor, and audit on
one shared `chore/eliminate-shims` branch. At any given moment 5-10
agents may have uncommitted modifications across `src/aeat/`. Trunk-wide
`uv run ruff check` and `uv run pytest` will fail on diagnostics that
belong to other agents, and trunk-wide `vault check` reports errors on
other features' plans / exec records that the current feature has no
authority to fix.

The honest gate for a single feature's commit is therefore:

> Did this feature's commits regress the surfaces they touched?

That question is answered by a path-scoped run: scope ruff and pytest
to the .py files in this feature's diff against `main`, and scope vault
audit to this feature's tag.

## Procedure

Run from the repo root.

### 1. Identify the touched surface

```bash
git diff main...HEAD --name-only > /tmp/touched.txt
grep -E '^src/aeat/.*\.py$' /tmp/touched.txt > /tmp/touched-py.txt
grep -E '^src/aeat/.*/test_.*\.py$' /tmp/touched.txt > /tmp/touched-tests.txt
```

### 2. Ruff (lint) — feature-owned files only

```bash
xargs -a /tmp/touched-py.txt uv run --no-sync ruff check
```

Exit non-zero on any diagnostic in a feature-owned file. Trunk-wide
diagnostics in untouched files are explicitly out of scope.

### 3. Pytest — feature-owned test modules only

```bash
xargs -a /tmp/touched-tests.txt uv run --no-sync pytest -x
```

Exit non-zero on any failure. Pre-existing failures in untouched test
modules are explicitly out of scope.

### 4. Vault feature check — feature tag scoped

```bash
uv run --no-sync vaultspec-core vault check all --feature <feature-tag>
```

Where `<feature-tag>` is the feature's `#tag` from the vault's tag
taxonomy (e.g. `profile-lifecycle-cli`). The CLI's `--feature` flag
narrows the audit to documents tagged with that feature. Pre-existing
errors on parallel features' plans / exec records are out of scope.

### 5. Capture evidence

Append the three command outputs to the closing Step Record under
`.vault/exec/yyyy-mm-dd-<feature>/<step>.md`. The Step Record is the
durable evidence that the surface gate passed at landing time; future
audits read it without re-running the gate.

## Out of scope

These categories of failure are explicitly NOT this gate's concern:

- Ruff diagnostics in files no commit on this feature's branch
  touched. They belong to whichever agent introduced them.
- Pytest failures in test modules no commit on this feature's branch
  touched. Same ownership rule.
- Vault errors on plans / exec records / audits whose feature tag is
  not this feature's tag. Each feature audits its own surface.
- Trunk CI (`.github/workflows/ci.yml`) is unchanged by this gate; it
  fires on push-to-main and PR-to-main only.

A separate plan owns the trunk-wide cleanup wave. That plan's owner
is the project coordinator, not any individual feature owner.

## Anti-patterns

- Running `uv run ruff check` without a filter and fixing every
  diagnostic. This silently absorbs other agents' work into the
  feature's commit and breaks authorship.
- Running `uv run pytest` against the whole tree and chasing
  pre-existing failures. Same authorship break.
- Running `vault check all` without `--feature` and trying to fix
  every reported error. The parallel features' plans are not in
  this feature's authority.
- Skipping the gate because the trunk-wide commands fail. The
  failure is real but its ownership lies elsewhere.

## Related

- The 2026-05-18 cascade-closure ADR (`.vault/adr/2026-05-18-profile-lifecycle-cli-adr.md`)
  section 4 mandates this gate's existence.
- The 2026-05-18 cascade-closure plan
  (`.vault/plan/2026-05-18-profile-lifecycle-cli-plan.md`) Phase P04
  enumerates the gate's Steps.

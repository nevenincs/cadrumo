---
tags:
  - '#research'
  - '#gate-integrity-adjudication'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:9d88f42cbf272f53a6e8dc0bf391528b0ccd941898730c3010b8c07ad0d5a079'
related:
  - "[[2026-09-02-gate-integrity-adjudication-research]]"
  - "[[2026-09-14-gate-integrity-adjudication-pre-commit-hook-runtime-reference]]"
---

# `gate-integrity-adjudication` research: `Pre-commit hook reconsideration`

This research asks whether fast automatic Ruff and ty repair can become an
installed, non-failing `prek` pre-commit hook without stash/restore in a
concurrently edited worktree. The constraints do not intersect in
`prek@0.5.1`: staged hook execution isolates unstaged changes, and `prek`
fails whenever hooks modify files even if their own exit status is zero. The
evidence favors a path-scoped explicit repair action outside commit time; an
ADR must settle whether to reaffirm that boundary or fund a separate
index-only Git-hook design that is not `prek`.

## Findings

### Standard `prek` cannot provide non-failing automatic repair

The runner owns two outcomes child flags cannot override. It saves and restores
unstaged content while presenting the staged snapshot, and it marks a priority
group failed when a hook changes files despite exiting zero. The installed CLI
exposes no no-stash mode. `--exit-zero` on Ruff or ty affects diagnostics only.
The governing behavior is recorded at
`2026-09-02-gate-integrity-adjudication-commit-time-mechanical-gates-adr:31-43`;
the independent modification rule is in the official `prek` reference.

### Verify-only installed hooks retain the data-loss mechanism

Removing autofixers removes direct writes by hook commands but does not remove
`prek`'s save/restore window. That conflicts with
`.codex/rules/aeat-no-destructive-git.md:10-18` and
`.codex/rules/aeat-worktree-safety.md:7-13`. The current `prek.toml:5-8`
claim that verify-only hooks never stash is stale.

### The fast repair sequence is lint fix, type fix, then format

Ruff applies safe lint fixes with `ruff check --fix`; ty exposes
`ty check --fix`; and Ruff formatting mutates in place. Both the repository
repair owner and Ruff documentation put formatting last because earlier fixes
can create formatting work: `dev/quality/fixes.py:35-42` and
https://docs.astral.sh/ruff/formatter/. The candidate order is therefore
`ruff check --fix`, `ty check --fix`, then `ruff format`.

Ruff and ty accept `--exit-zero`, while ty preserves exit 2 for configuration
or I/O failure and 101 for internal failure. The ADR must distinguish residual
diagnostics, which may be advisory, from an operational failure that means no
repair was performed.

### Direct ty repair is narrower than the authoritative type verdict

The repository gate combines ty, pyrefly, and BasedPyright:
`prek.toml:61-71` and `dev/quality/types.py:173-278`. A fast
`ty check --fix PATH...` action can be a mechanical aid but cannot claim that
the paths pass the project type contract. Its fix output needs a synthetic
fixture audit before being classified as safe automatic repair; this research
did not mutate the shared tree to discover that behavior.

### Hook eligibility requires caller-owned paths and a measured ceiling

Whole-tree mutation would rewrite concurrent contributors' files. A fast
repair surface must receive explicit caller-owned paths, reject paths outside
the worktree, select only Python files, and never change Git state. Existing
measurements show about two seconds for a change-scoped mechanical check while
whole-tree gates take roughly four to forty seconds:
`2026-09-02-gate-integrity-adjudication-research:106-117`.

An initial ceiling of no network/install work, warm p95 at most two seconds,
and runtime proportional to passed files is an opinion pending a benchmark
corpus. The ADR needs a numeric budget; “fast” cannot keep later whole-tree
checks out of commit time.

### Local project tools avoid a second implementation

`prek.toml:49-58` runs remote Ruff 0.15.12 while `uv.lock:3510-3511` locks Ruff
0.16.5. A repair surface should use project-locked tools through
`uv run --no-sync`, avoiding verdict drift and hook-time downloads. This
follows `2026-09-11-justfile-design-adr:70-73`.

### One near-term loop and one new subsystem remain

An installed mutating `prek` hook is eliminated by the no-stash and
non-failing constraints. Verify-only `prek` retains stash/restore. A raw Git
hook that rewrites the worktree can leave fixes outside the staged snapshot;
automatically staging them can absorb unstaged hunks.

An index-only native Git hook could materialize the staged snapshot in an
isolated temporary directory and update only the invoking worktree's index. It
would not be `prek` and must prove partial staging, index locks, temporary-tree
type resolution, post-commit worktree coherence, interruption recovery, and
bounded performance. No prototype or concurrency proof was performed here.

The evidence favors an explicit path-fed repair command or editor action
outside commit time, followed by a read-only path-fed preflight. Installing any
hook would instead require superseding the accepted ADR.

## Sources

- `2026-09-02-gate-integrity-adjudication-commit-time-mechanical-gates-adr:31-109`
- `2026-09-02-gate-integrity-adjudication-research:106-117`
- `2026-09-11-justfile-design-adr:70-73`
- `.codex/rules/aeat-no-destructive-git.md:10-18`
- `.codex/rules/aeat-worktree-safety.md:7-13`
- `prek.toml:3-18`
- `prek.toml:49-71`
- `dev/quality/fixes.py:35-42`
- `dev/quality/types.py:173-278`
- `uv.lock:2612-2613`
- `uv.lock:3510-3511`
- `uv.lock:4364-4365`
- https://prek.j178.dev/reference/configuration/
- https://docs.astral.sh/ruff/linter/
- https://docs.astral.sh/ruff/formatter/
- https://docs.astral.sh/ty/reference/cli/
- https://docs.astral.sh/ty/reference/exit-codes/

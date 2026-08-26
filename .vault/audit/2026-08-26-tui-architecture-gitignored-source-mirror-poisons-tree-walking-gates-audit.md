---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:3a0635b09b09685cffbb252895e1b38a9f7dd73cc9e95f70719a321f95a92ae7'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `gitignored source mirror poisons tree-walking gates`

## Scope

A hazard class, recorded after it produced two independent gate failures in one
day from unrelated campaigns. Read-only apart from the two fixes already landed.

## Findings

### The mirror is live, large, and inside a scanned tree

`dev/benchmarks/cli/.baseline-source-snapshot/` is a complete copy of the source
tree: 795 MB, 5,461 Python files, gitignored at `dev/benchmarks/cli/.gitignore`
and untracked. Its mtime shows it was regenerated during this session, so it is
an actively maintained benchmark artefact, not abandoned residue.

Every stale copy inside it is indistinguishable, to a path-walking scan, from a
real source file.

### It has already broken two unrelated gates

The registry facade family census ingested it: 278,894 of 628,481 consumer
entries, 44 per cent of the artefact, were paths inside the mirror, across 75 of
78 rows. Fixed by restricting evidence to `git ls-files`.

`test_workspace_model_docs_and_active_tree_reach_the_public_module_fixed_point`
rglobbed `dev/`, found the mirror's stale copy of that same test file, and
counted it as a remnant. The gate therefore failed on any checkout carrying the
benchmark snapshot, and passed elsewhere. Fixed the same way
(`src/cadrumo/application/modelo/tests/test_workspace_models.py`).

Two campaigns, two gates, one cause, neither aware of the other.

### The exposed surface is wider than the two known cases

Enumerating tracked scanners that both walk a tree and reference `dev`, fifteen
further candidates exist, among them `dev/audit/vacuity_screen.py`,
`dev/ci/lane_reachability.py`, `dev/quality/fixture_census.py`,
`dev/packaging/release_cohort.py` and several `test_command_spec_*` lane gates.
Not audited individually here: a scan restricted to `src/` is unaffected, and
which of the fifteen genuinely reach into `dev/` needs reading each one.

The failure mode is quiet in the dangerous direction. A gate that counts
remnants over-reports and goes red, which gets noticed. A gate computing a
census, a budget or a coverage ratio silently absorbs 5,461 phantom files and
still produces a plausible number.

### Ad-hoc investigation is affected too

A `grep -rn "def scan_directory"` during this pass returned the mirror's copy as
its first hit. Anyone searching the tree by path rather than by tracked status
can read a stale definition and believe it is the live one.

## Recommendations

- Prefer `git ls-files` over `rglob` in any gate whose subject is "the source
  tree". Tracked status is the property these gates actually mean; path
  reachability only approximates it, and the approximation is wrong here by
  5,461 files.
- Audit the fifteen candidate scanners for real exposure, and treat any that
  computes a ratio or budget as higher priority than one that lists remnants,
  because the former fails without going red.
- Consider whether the benchmark snapshot must live inside the repository at
  all. Relocating it outside the working tree removes the hazard for every
  present and future scanner at once, rather than one gate at a time. That is a
  question for the benchmark's owner, not a unilateral change: it is 795 MB of
  live working data.

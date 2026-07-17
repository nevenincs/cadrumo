---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
step_id: 'S22'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Clean stale scratch and runtime-s directories after confirming no active-agent ownership, and document the scratch naming schema

## Scope

- `scratch`

## Description

- Enumerate `scratch/` and every `.runtime-sNN-*` top-level directory with
  file counts, sizes, and newest-file modification times.
- Cross-check each item's mtime against a seven-day cutoff (2026-07-06) and
  its content against the stale-pattern inventory named in the plan brief
  (a stale registry cache pickle, old campaign logs, CLI help dumps, and
  scratch scripts referencing the retired `src/aeat` / `aeat.*` path).
- Delete only items satisfying both the age gate and a stale-pattern match:
  24 files/directories under `scratch/` (five help-dump files plus the
  32-file `cli-help/` directory, seven campaign log files, the 17.9 MB
  `registry_cache.pkl`, ten dead-`aeat`-import scripts, five generated
  fixture-output directories those scripts wrote, and one zero-byte
  traceback dump).
- Retain everything else — `scratch/__pycache__/` (inside the 7-day window),
  `scratch/modelo-216-registry-wip/` (looks like genuine unlanded registry
  authoring work, not debris), and all seventeen `.runtime-sNN-*` directories
  (every one has a newest-file mtime inside the 7-day window despite
  step-numbered names suggesting an earlier campaign) — and record each as an
  explicit ambiguous/too-recent finding in the audit record rather than
  silently skipping it.
- Author `2026-07-13-data-output-standardization-scratch-runtime-cleanup-audit.md`
  documenting the full deletion inventory, the retained-item rationale, and
  the mandated `scratch/<yyyy-mm-dd>-<owner-or-session>-<label>/` naming
  schema (recorded per the operator's no-codification directive rather than
  as a new vaultspec project rule).

## Outcome

- Confirmed both `scratch/` and every `.runtime-sNN-*` directory are entirely
  untracked by git (`git ls-files` returns nothing for either root), so every
  deletion was a plain filesystem removal with no git operation involved.
- `scratch/` now holds only the two retained ambiguous entries
  (`__pycache__/`, `modelo-216-registry-wip/`); the audit record enumerates
  the full before/after state and flags a follow-up sweep after 2026-07-20
  for the `.runtime-sNN-*` directories once they clear the age gate.

## Notes

Landed the audit record and this exec record via a private-index
`git commit-tree` plus compare-and-swap `git update-ref` on the shared branch
ref rather than a normal staged commit, per the shared-index contention
documented in `W04.P07.S21`'s exec record and reported to `team-lead`.

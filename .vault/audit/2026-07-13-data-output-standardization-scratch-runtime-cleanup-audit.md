---
tags:
  - '#audit'
  - '#data-output-standardization-scratch-runtime-cleanup'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# `data-output-standardization-scratch-runtime-cleanup` audit: `scratch and runtime cleanup`

## Scope

Executes plan step `W04.P07.S22` of the data-output-standardization campaign
(ADR ruling R5). Enumerates the contents of the repo-root `scratch/` directory
and the ad-hoc `.runtime-sNN-*` directories with sizes and modification times,
deletes only items whose newest-file mtime is older than seven days AND that
match one of the stale patterns already documented in the six-axis discovery
research (a stale registry cache pickle, old campaign logs, CLI help dumps,
and stale one-off scripts/dumps referencing the retired `aeat.*` import path),
and lists everything else as ambiguous or too recent to judge, deferring
deletion. Records the mandated scratch naming schema per the ADR since
codification of new project rules is retired per operator directive; this
audit record and the ADR are the sole documentation of the convention. Both
`scratch/` and every `.runtime-sNN-*` directory are confirmed entirely
untracked by git (`git ls-files` returns nothing for either), so every
deletion below is a plain filesystem removal, never a git operation.

## Findings

### scratch-stale-help-dumps | low | five CLI `--help` capture files from 2026-06-08, superseded by the live CLI

`scratch/auth_help.txt`, `evidence_help.txt`, `ledger_help.txt`,
`modelo_work_calculate_help.txt`, and `profile_create_help.txt`, plus the
32-file `scratch/cli-help/` directory (newest file 2026-06-09), are one-off
captures of `--help` output from an ad-hoc CLI documentation pass. All predate
the seven-day cutoff (2026-07-06) by roughly five weeks. Deleted.

### scratch-stale-campaign-logs | low | six docs-conformance run logs and one hintfix-test log from 2026-06-09

`scratch/docs-conformance-baseline.log`, `wavea.log`, `wavea2.log`,
`waveb.log`, `waveb2.log`, `waveb3.log`, and `hintfix-tests.log` are captured
stdout from an earlier docs-conformance and hintfix campaign, all dated
2026-06-09. Deleted.

### scratch-stale-registry-cache | low | 17.9 MB `registry_cache.pkl` from 2026-06-09, named explicitly in the research inventory

`scratch/registry_cache.pkl` matches the stale-pattern inventory verbatim.
The production registry disk cache now lives under the settings-derived cache
root per Wave W01 of this same campaign; this scratch copy is a leftover
debug artefact with no consumer. Deleted.

### scratch-stale-dead-aeat-imports | low | eight one-off scripts importing or referencing the retired `src/aeat` / `aeat.*` path

`scratch/heal_snapshot.py` and `profile_test.py` reference `src/aeat/...`
path literals; `run_and_trace.py` and `test_conformance_check.py` invoke
pytest against `src/aeat/...` test paths; `measure_diagnostics.py`,
`profile_registry_load.py`, `profile_typo_twins.py`, `test_pickle.py`,
`trace_diagnostics.py`, and `trace_validation.py` import `from aeat.*`
directly. The package root moved to `src/cadrumo/` well before this audit, so
every one of these scripts is dead on arrival if re-run today. Their
generated output directories (`scratch/test_tmp/`, `tmp_diagnostics/`,
`tmp_diagnostics_measure/`, `tmp_diagnostics_trace/`,
`tmp_diagnostics_unique/`, each holding a stale `aeat-storage/buckets/...`
fixture tree, and the zero-byte `traceback.txt` the trace script wrote) are
debris from the same dead scripts. All ten scripts plus their five output
directories and the traceback dump are deleted.

### scratch-ambiguous-retained | low | two `scratch/` entries retained pending owner confirmation

`scratch/__pycache__/` (six `.pyc` files, newest 2026-07-09, four days before
this audit) is orphaned bytecode for three of the now-deleted scripts, but its
newest-file mtime is inside the seven-day window, so the mandated age gate
does not clear it for auto-deletion; it is harmless leftover bytecode and can
be swept on a later pass once it ages past the cutoff, or deleted immediately
by an operator who judges orphaned `.pyc` files a zero-risk exception.
`scratch/modelo-216-registry-wip/` (three registry TOML fragments — a
`manifest.toml`, a `revision.toml`, and a `completeness-manifest.toml` for a
Modelo 216 revision, newest file 2026-07-01) reads as genuine in-progress
registry-authoring work rather than debris; it is outside the seven-day
window by age alone but is explicitly NOT deleted because its content looks
like unlanded contribution, not a stale dump. Flagged for the owning agent or
operator to either land it under the registry authoring tree or explicitly
mark it disposable.

### runtime-s-dirs-too-recent-to-judge | medium | every `.runtime-sNN-*` directory is inside the seven-day window despite step-numbered names suggesting an old campaign

Seventeen `.runtime-sNN-*` directories exist at the repo root
(`.runtime-s62-locale` through `.runtime-s67-scaffold`, plus
`.runtime-s102-personas`). Their step-number naming (`s62`..`s67`, `s102`)
suggests they were seeded during an earlier, already-closed campaign wave, but
every one of them has a newest-file mtime from either 2026-07-13 (the
sixteen `s62`-`s67` directories, most within the last few hours of this
audit) or 2026-07-10 (`s102-personas`, three days prior) — none older than
the seven-day cutoff. Each holds only a small `logs/cadrumo.log` (plus, for
`s102-personas`, a small bucket/db tree), consistent with an isolated CLI
test-fixture root being freshly re-created by a currently-running or
recently-run test suite that reuses the historical directory-name convention
rather than a genuinely stale leftover. None are deleted under the mandated
age gate. This is exactly the ad-hoc convention Wave W04 retires: the
`.gitignore` `.runtime-*/` pattern (`W04.P07.S20`) stops any future instance
from landing tracked, but the existing directories themselves need a repeat
pass after they age past seven days, or explicit confirmation from whichever
process is regenerating them that they are safe to remove sooner.

## Recommendations

- Re-run this same age-and-pattern-gated sweep after 2026-07-20 (seven days
  from this audit) to catch the `.runtime-sNN-*` directories once they clear
  the cutoff, assuming no active process is still writing to them.
- Route future one-off diagnostic scripts through `scratch/<yyyy-mm-dd>-<owner-
  or-session>-<label>/` (the mandated schema below) so a future cleanup pass
  can judge staleness from the directory name alone rather than opening every
  file to check for dead imports.
- Confirm with the owning agent whether `scratch/modelo-216-registry-wip/`
  should be landed under the registry authoring tree or is safe to delete;
  do not delete it unilaterally.

## Scratch naming schema (ADR ruling R5)

Every new scratch directory or loose scratch file created by an agent or
operator MUST use the stem `scratch/<yyyy-mm-dd>-<owner-or-session>-<label>/`
for directories, and the same stem (with an appropriate extension) for loose
files, e.g. `scratch/2026-07-13-exec-w04-p07-registry-cache-probe.py` or
`scratch/2026-07-13-exec-w04-p07-help-dump/`. `<owner-or-session>` names the
authoring agent role or session identifier (not a bare initial or a vague
label), and `<label>` is a concise kebab-case description of the artefact's
purpose. This makes every future cleanup pass able to judge an item's age and
owner directly from its path, without needing to open the file and inspect
its imports or content, and makes attribution of orphaned scratch debris to a
specific campaign or session possible after the fact. `scratch/` itself
remains the sole mandated dev/agent scratch location at the repo root; no
other root-level directory or ad-hoc naming convention (including the retired
`.runtime-sNN-*` shape) is sanctioned for new work. Per the operator's
no-codification directive (2026-07-13), this convention is recorded here and
in the ADR body, not as a new vaultspec project rule.

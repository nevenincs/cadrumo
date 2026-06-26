---
tags:
  - '#audit'
  - '#crossperiod-filing-deadlock'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - '[[2026-06-19-m100-dependent-modelo-applicability-adr]]'
  - '[[2026-06-19-crossperiod-filing-deadlock-adr]]'
  - '[[2026-06-19-crossperiod-filing-deadlock-research]]'
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace crossperiod-filing-deadlock with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `crossperiod-filing-deadlock` audit: `stash recovery + C3 drift remediation audit`

## Scope

A manual `git stash` operation in the shared multi-agent worktree left an unresolved
3-stage index conflict in the cross-period clean-state surface and stranded ~131 files of
multiple agents' in-flight work. This audit covers (a) the conflict resolution, (b) the
coordinator-directed bulk recovery of the stashed work, and (c) a post-landing self-audit
of the C3 (Modelo 100 salaried reachability) feature for drift.

## Findings

### CRITICAL — none unresolved

The stash conflict in `_cross_period_clean_state.py` and `_verification_actions.py` was
reconstructed to HEAD's correct C3+M202 merge via a clean 3-way merge from the three index
stages (both suppression passes preserved); 0 markers, 0 unmerged. The merged result is
byte-identical to HEAD, confirming HEAD already held the correct merge and the stash carried
stale content.

### HIGH — bulk recovery gated on collect-only, not tests (`5d432cffd`)

The 131-file recovery landed multiple agents' INCOMPLETE features (303 REDEME, ledger,
deadline, actividades) in one chore commit under the directive "lose no code". Gate was
structural (16,142 tests collect clean), not green-suite. Risk: a point-in-time half-state
is pinned to history and attributed to one SHA; per-feature final shapes remain each owner's
to land. The 185 parallel-suite failures were verified to be the documented loader-cache race
(`aeat-local-execution`) — every cluster passes sequentially.

### HIGH — author-created regulated registry bindings, now grounding-verified

Four `renta-2024-ledger-expense-0186/0192/0199/0203-deductible` bindings were authored to
unblock the registry load (the stash's actividades construct referenced them). Subsequently
verified against the bundled LIRPF corpus: art-28/art-30 define net rendimiento as ingresos
menos gastos deducibles; `source_refs`/`required_text` match the established 2024 income
binding. Grounded, but should still be owner-reviewed against the actividades feature intent.

### HIGH — C3 threading coverage gap (FIXED)

`taxpayer_files_economic_activity` was threaded into verify+file but NOT export
(`_export.py`) nor the CLI verification preview — so a salaried filer's EXPORT (the
reachability finish line) was still blocked by 130/131. Fixed across all six production
callers (`e9515a2bc`, `67339e0d1`); the helper was promoted to the public
`derive_taxpayer_files_economic_activity` re-export.

### MEDIUM — first-filer M100 self-carry not covered for salaried filers

A first-time salaried filer is still blocked by the M100->M100 prior-year self-carry; the
first-filer suppression keys on `activity_start_date` (an economic-activity signal a salaried
employee lacks). Needs a field-semantics decision (ADR + operator input). Documented, not
shipped.

### LOW — size-budget ratchets mask growth; marker rewordings drop slug traceability

~15 SPLIT-CANDIDATE budgets were ratcheted for concurrent peer growth (accepted interim, but
the splits remain owed). Marker-gate rewordings stripped `-adr` from slug references in peer
test docstrings, so those references no longer match the ADR filenames.

## Recommendations

- Each owner of a recovered feature (303 REDEME, ledger, deadline, actividades) re-runs and
  finishes their feature's tests on top of `5d432cffd`; treat that commit as a recovery
  baseline, not a final landing.
- The actividades feature owner reviews the four author-created 2024 expense bindings against
  their intended grounding.
- Author an ADR for the first-filer self-carry (generalise the no-prior-obligation signal
  beyond `activity_start_date`, or add a "first IRPF filing year" profile axis) before
  implementing — never reuse `activity_start_date` for salaried filers by overload.
- Owners split the SPLIT-CANDIDATE modules rather than ratchet further.

## Codification candidates

The load-bearing lesson (never overwrite proven-live peer WIP; land own changes via the
apply-cached HEAD-anchored own-only drive) is already codified as
`uncommitted-wip-is-not-orphaned`; the C3 registry-classification lesson is codified as
`cross-period-suppression-grounded-in-registry-classification`. No new candidate from this
audit.

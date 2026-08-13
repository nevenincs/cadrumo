---
tags:
  - '#audit'
  - '#aeat-design-relayout-boundary'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:fa8cd9055a960cb5e74d5cc36a26b570aa8c87af759750c4b141f35ec859d79d'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
  - "[[2026-08-07-aeat-design-relayout-boundary-adr]]"
  - "[[2026-08-07-aeat-design-relayout-boundary-sub-year-epoch-adr]]"
  - "[[2026-08-13-aeat-design-relayout-boundary-audit]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
---

# `aeat-design-relayout-boundary` audit: `Blocked Wave carry-forward: the three modelo authoring Waves remain open, not superseded, pending the sibling generator`

## Scope

The 2026-08-13 campaign-closure audit already sketches the blocked state in its
closing section. This document is the fuller carry-forward that section asked
for: a per-Wave breakdown of exactly which rows are blocked, the exact sibling
rows this campaign waits on re-verified at the time of writing rather than
copied from an earlier observation, and an explicit statement of what the
standing goal still asks for that the blocked state excludes. Every fact below
was independently re-verified against HEAD; none was copied from a prior
report, and two things that were expected to reproduce did not, recorded as
found rather than silently corrected to match the expectation.

## Findings

### export-fragment-trees-absent-at-head | high | every export fragment tree for Modelo 303, Modelo 200 and Modelo 390 is empty at HEAD, not merely un-split, and the deletion is committed history rather than in-flight work

`git ls-files` over `src/cadrumo/_data/registry/aeat/modelos/303/revisions/*/export/*`,
the equivalent `export_layouts/*` pattern for Modelo 390, and the equivalent
`export/*` pattern for Modelo 200, each return zero tracked files. This count
excludes the Spanish-noun false positive the dispatch flagged: registry
fragments named for the tax concept `exportacion` (`0003-intracom-export-base`,
`exportaciones-exentas`) and a `support_removal_decisions` fragment titled
`0001-export-layout-support-removal.toml` are construct and casilla content,
not export layout files, and none matched the glob above regardless. A disk
listing confirms the same result more directly: every one of Modelo 303's six
revision directories (`2009-y-siguientes`, `2023`, `2024-desde-09-y-3t`,
`2024-hasta-08-y-2t`, `2025`, `2026-y-siguientes`) carries an `export/`
directory containing only `.` and `..`, zero files. Modelo 390's single
revision (`2010-y-siguientes`) carries an `export_layouts/` directory in the
same empty state. Modelo 200's single revision (`2024-y-siguientes`) carries no
export directory at all; it has a `records/` directory instead, which holds
pre-split registry sections (`bindings.toml`, `constructs.part-*.toml`,
`formulas.toml`, `parameters.toml`, `relations.toml` and siblings) rather than
export layout content — a second false-positive risk the dispatch did not
anticipate, worth flagging so a later reader does not mistake `records/` for
the export tree. `git log --diff-filter=D` over the Modelo 303
`2009-y-siguientes` export path returns commit `df49c5206a` ("Registry work:
303") as the deletion, and `git status --short` over all three modelos'
registry subtrees is clean — the emptiness is committed at HEAD, performed by
the sibling `2026-08-10-aeat-export-fragment-generator-authority-plan`
campaign, not left over from in-flight work in this worktree.

Notably, the deletion reached every Modelo 303 revision directory including
the still-unsplit `2009-y-siguientes` shell, not only the five split shells
this plan's `W02.P04` rows describe. The manual fragment trees were removed
tree-wide ahead of the generator that is meant to replace them, so at the
moment of writing none of the three modelos can produce any export output at
all, split or unsplit.

### dev-registry-mappings-absent | high | no semantic map exists anywhere in the tree for any modelo

`dev/registry/mappings` does not exist (`ls` reports "No such file or
directory"). A targeted search for `modelo_390` or `modelo-390` inside `dev/`
matches only test and audit-run artifacts (`dev/registry/tests/test_workbook_parity.py`,
`dev/audit/.runs/summary.json`), never mapping content. No semantic map or
render profile has been authored for Modelo 303, Modelo 390 or Modelo 200 at
the time of writing.

### wave-w02-modelo-303-fully-blocked | high | all 18 Steps across Modelo 303's three Phases are open

`W02.P04` (authoring the five successor revisions) carries nine rows —
`S15` through `S20`, plus `S64` and `S67` — all open. `W02.P05` (the
window-edge revision and the retirement of the spanning historical revision)
carries two rows, `S22` and `S23`, both open. `W02.P06` (the atomic landing
commit and the emitted-byte boundary proofs) carries seven rows, `S24` through
`S30`, all open. None of these eighteen rows can produce a real parsed export
fragment tree today, because the generator that is supposed to produce one does
not yet exist and the governing ADR forbids the hand-transcribed alternative
(see the `hand-transcription-forbidden` finding below).

### wave-w03-modelo-390-fully-blocked | high | all 10 Steps across Modelo 390's two Phases are open

`W03.P07` (authoring the four in-window revisions plus the refusal edge below
them) carries five rows, `S31`, `S33` through `S36`, all open. `W03.P08` (the
atomic landing commit and the emitted-byte boundary proofs, including the
regression for the already-proved live mis-write at filing year 2023) carries
five rows, `S37` through `S41`, all open. Same blocking cause as Modelo 303:
no generator, no semantic map, and no sanctioned hand-authored substitute.

### wave-w04-modelo-200-mostly-blocked | high | 5 of Modelo 200's 6 Steps are open; the one closed row is a decision, not an authoring row, and does not relieve the block

`W04.P09` carries `S42`, `S43`, `S45`, `S46` and `S76`, all open, plus `S44`,
closed. `S44` records a decision not to retire the `2024-y-siguientes`
revision directory on re-keying-cost grounds; it does no export authoring and
its closure does not advance or relieve the export-tree block. `S42` itself
states its own blocking condition in its row text: it is "HELD behind the
export-fragment generator" because "no tooling turns a bundled diseno into an
export fragment tree" — the same fact this document independently re-confirms
above. `S43` narrows the existing revision to ejercicio 2025 onward only in the
same commit as `S42`'s successor revision, so it cannot land first without
reproducing the ejercicio-2024 outage commit `867b1fe7e7` fixed. `S45` and
`S46` are the landing commit and byte-level proof and depend on both.

### sibling-blocking-chain-current-state | high | the sibling plan's blocking rows re-verified at HEAD; several have closed since they were last observed, none of the still-open map-authoring rows have

Reading `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md`
at HEAD rather than trusting a prior list: `W04.P07.S54` (differentiated-sector
source taxonomy) and `W04.P07.S66` (DANA primary authorities) are now CLOSED —
both were open in a prior observation and have since landed. `W04.P07.S65`,
which the prior observation named as a blocking prerequisite, is RETIRED (the
plan's own header marks it `<!-- RETIRED: S19, S26, S65 -->`) and re-carried
without loss as six replacement rows, `S72` through `S77`, all still open,
covering the DP30302 semantic field matrix, the annual Orden authority
extension, the simplified-regime mechanism-collapse ruling, the activity-
identity discriminator, the typed per-activity value-arrival result, and the
ordered deletions those replace. The five per-epoch Modelo 303 map-authoring
rows, `S67` through `S71` (2023, 2024-early, 2024-late, 2025 and 2026
respectively), remain open, and each row's own text states it "cannot close
before `S63` lands." `S63` itself (closing the DP30302 declaration deficit)
remains open. The plan's own serialization sequence in its Parallelization
section orders the remaining work `S72 -> S73 -> S74 -> S75 -> S76 -> S77 ->
S63 -> S67 -> S68 -> S69 -> S70 -> S71 -> S52 -> S20 -> S16 -> S21 -> S22 ->
S23 -> S24 -> S17 -> S34 -> S18 -> S25 -> S27 -> S28 -> S29`, and every one of
those rows is open at HEAD. `S20` (generate and validate the five Modelo 303
trees), `S21` (Modelo 390 trees) and `S22` (Modelo 200 bootstrap) sit at
positions 8, 16 and 17 of that remaining sequence respectively, each behind
every row that precedes it. Net effect versus the prior observation: real
progress landed (S54, S66, and everything up through S64 in the Phase are now
closed), but the map-authoring rows this campaign's Waves actually wait on —
S67 through S71, and S63 beneath them — are exactly as open as before, now
gated behind six newly-open rows (S72-S77) rather than the single retired S65.

### modelo-390-semantic-map-prerequisite-still-missing | medium | no sibling row authors a Modelo 390 semantic map or render profile, unlike the five Modelo 303 rows; this still reproduces

A prior review found no sibling row authoring a Modelo 390 semantic map,
unlike the five explicit per-epoch Modelo 303 rows (`S67`-`S71`). Re-checked
against HEAD by searching the sibling plan body for every `390` occurrence: the
only Modelo 390 row in Wave 4 is `W04.P07.S21`, "Generate and validate complete
Modelo 390 revision trees and provenance manifests" — a generation row with no
preceding map-authoring row analogous to `S67`-`S71`. The two other `390`
occurrences in the document are unrelated Modelo 303 rows referencing the
"exonerado-390" annual-summary casillas (`S47`, `S56`). This gap still
reproduces exactly as previously found: `S21` appears to be missing its
authoring prerequisite, and unless a Modelo 390 map-authoring row is added
before `S21` is attempted, `S21` cannot proceed on the same fail-closed terms
`S67`-`S71` enforce for Modelo 303 (join a reviewed semantic map keyed by exact
parser anchors against the parsed source, never against an unreviewed or
absent map). This is recorded here as an observation for the sibling plan's
owner, not as an action of this campaign — this plan does not own or edit the
sibling's rows.

### hand-transcription-forbidden-no-workaround | medium | the governing generator-authority ADR forbids exactly the workaround that would otherwise unblock these Waves sooner

`2026-08-10-aeat-export-fragment-generator-authority-adr` rules, in its
Constraints: "Neighbouring fragment trees are neither inputs nor correctness
oracles. Legacy trees are explicitly unverified bootstrap evidence and may not
supply profile rules or defaults," and: "Generated replacements are a hard
cutover: superseded manual fragment trees, single-file/direct-revision
compatibility loaders, derivative record-design fallbacks, and print-only
unmeasured paths are deleted. No legacy fallback, migration support, or silent
green result remains." Every wire fact absent from the exact workbook anchor
must resolve through "one exhaustive per-design render profile, bound to the
exact source SHA-256" — never inferred from type and width, never copied from
a neighbouring tree. This plan's own `W04.P09.S42` row states the same
constraint in its own words: the Modelo 200 successor revision "cannot proceed
until a generator exists because no tooling turns a bundled diseno into an
export fragment tree and the governing ADR forbids hand-transcription." No
authoring row in `W02`, `W03` or `W04` may be closed by hand-authoring a
fragment tree to route around the sibling campaign; doing so would violate the
governing ADR directly, and no such attempt was made or is recommended here.

### standing-goal-not-discharged-by-the-blocked-state | high | the blocked state achieves "no wrong-offset filing year" only by writing no filing year at all, which is not the outcome the standing goal requires

This plan's stated standing goal is that no filing year is written at wrong
offsets, for Modelo 303, Modelo 390 and Modelo 200 across the reachable
prescripcion window. The `export-fragment-trees-absent-at-head` finding above
means that goal now holds in the narrowest possible sense for all three
modelos: with the export trees empty, no filing year is written at ANY
offset, correct or wrong, so nothing currently violates the letter of "no
filing year is written at wrong offsets." That is not the delivered outcome
the standing goal exists to produce. The goal is not satisfied by the mere
absence of wrong bytes; it requires the presence of correct bytes, produced by
a parsed, non-hand-transcribed export fragment tree, for every in-window
filing year on all three modelos. Until the sibling campaign's generator and
at least the Modelo 303 per-epoch semantic maps (`S67`-`S71`), the DP30302
declaration closure (`S63` and its `S72`-`S77` prerequisites), and the Modelo
390 map-authoring row this document flags as still-missing all land, this
campaign's `W02`, `W03` and `W04` cannot produce a single real export for any
of the three modelos. This blocked state is not a narrower substitute
completion criterion for this campaign; it is the campaign correctly declining
to close `W02`, `W03` and `W04` while the standing goal remains unmet for
every filing year those Waves were built to serve. Being unable to build the
export trees today does not discharge that obligation, and no plan Step's
checked state has been changed by this document.

## Recommendations

- Do not read `S65`'s retirement in the sibling plan as scope reduction: it was
  re-carried without loss as `S72` through `S77`, and none of the six has
  closed yet. A later reader reconciling this campaign's blocked state against
  the sibling plan should track all six, not the retired `S65` alone.
- Flag to the sibling plan's owner, as this document already does, that
  `W04.P07.S21` (Modelo 390 tree generation) has no preceding map-authoring row
  analogous to `S67`-`S71`; a follow-on row in that plan should add one before
  `S21` is attempted, or `S21` will need to be blocked again for the same
  reason once its Modelo 303 prerequisites clear.
- Continue to track `2026-08-10-aeat-export-fragment-generator-authority-plan`
  as the hard precondition for resuming `W02`, `W03` and `W04` in this plan.
  Re-run the verification commands this document used — `git ls-files` over
  each modelo's export path, and a fresh read of the sibling plan's checkbox
  state — before assuming the block has lifted; do not copy this document's
  counts forward as still current without re-deriving them.

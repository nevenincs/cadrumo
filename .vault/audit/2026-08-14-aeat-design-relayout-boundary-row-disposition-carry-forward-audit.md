---
tags:
  - '#audit'
  - '#aeat-design-relayout-boundary'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:c1805cbfc321e802b7fa78fcdf5d7afe133b8d69e650ec4c0387fed73eafe0e3'
related:
  - '[[2026-08-08-aeat-design-relayout-boundary-plan]]'
  - '[[2026-08-10-aeat-export-fragment-generator-authority-plan]]'
  - '[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]'
  - '[[2026-08-07-aeat-design-relayout-boundary-adr]]'
  - '[[2026-08-07-aeat-design-relayout-boundary-sub-year-epoch-adr]]'
---

# `aeat-design-relayout-boundary` audit: `row disposition and carry-forward close`

## Scope

This audit adjudicates every open row of the `aeat-design-relayout-boundary` plan
against the tree at HEAD on 2026-08-14, and records the carry-forward that the
campaign-close discipline requires. That discipline forbids marking a plan Step
complete without either a matching execution record or a close audit recording the
deferred carry-forward, precisely so that delivered-as-specified, delivered-narrower
and recorded-but-not-implemented cannot wear the same checkbox. Ten of the rows closed
below were delivered by OTHER campaigns rather than by this plan's own execution
records, and the plan's own status verb names all ten as `exec-missing`. This document
is the record that makes those closures honest; without it they would be bare
checkboxes with no provenance.

The plan carried 47 open rows before this pass, with 33 closed and `S21` and `S32`
already retired. After it, 14 rows remain open, 43 are closed and 24 are retired
across a 57-row document. No source code was touched and nothing was committed.

## Findings

### completed-by-other-campaigns | medium | Ten rows carry a deliverable present at HEAD that this plan did not itself produce

Ten rows were marked complete because their deliverable is verifiably present in the
tree, in every case produced by a campaign other than this one. `W03.P07.S31`, `S33`
and `S34` demanded Modelo 390 revisions for filing years 2022, 2023 and 2024; all
three revision directories exist and each carries both a real `valid_from` and a real
`valid_to`, bounding it to its own filing year. They were delivered by commit
`f9f3f77704`, "feat(registry): split Modelo 390 annual epochs", authored under the
export-fragment generator campaign's own row numbering rather than under this plan.
`W03.P07.S36` demanded the retirement of the spanning Modelo 390
`2010-y-siguientes` revision; that directory is absent from the tree. `W05.P10.S50`,
`S51` and `S52` demanded per-revision completeness manifests; manifests are present in
all six Modelo 303 revision directories, all four Modelo 390 directories and the
single Modelo 200 directory. `W05.P10.S53` demanded the mandatory Spanish casilla
label leaves for each new Modelo 303 revision id; the Spanish catalogue carries 207
casillas for `2023`, 207 for `2024-hasta-08-y-2t`, 207 for `2024-desde-09-y-3t`, 205
for `2025` and 206 for `2026-y-siguientes`. `W02.P04.S67` demanded a ruling on the two
modulos-engine formula ids embedding a bare year; no `modelo-303-2023-modulos`
occurrence remains anywhere under the Modelo 303 revisions, nor in any source file of
the tree, so the id was re-derived and the row's concern no longer has a subject.

### completed-narrower-than-specified | high | Three of those ten rows are closed on half of what their text demands

`W03.P07.S31`, `S33` and `S34` each demand not only the revision but "its own export
fragment tree parsed from the bundled design". The revision half is delivered and
bounded. The export-fragment half is NOT: `git ls-files` over the export paths of
Modelo 303, Modelo 390 and Modelo 200 returns zero files for all three modelos, so
every export tree in this campaign's scope is empty at HEAD. These three rows are
therefore closed as delivered-narrower, not delivered-as-specified, and this paragraph
is the record of what their checkbox excludes. What the standing goal still asks for
that these closures do not deliver is a parsed export fragment tree for Modelo 390
filing years 2022, 2023 and 2024, and that work is owned by row `W04.P07.S21` of the
export-fragment generator authority plan, which generates and validates the complete
Modelo 390 revision trees. It is carried forward, not abandoned.

### superseded-open-ended-requirement | medium | One row demands an open-ended Modelo 390 revision that a later accepted record forbids

`W03.P07.S35` demanded an OPEN-ENDED Modelo 390 revision "covering filing year 2025
onward". That requirement is overridden by the accepted registry temporal coverage
authority-grade record of 2026-08-14, which rules that superseded revisions become
bounded epochs while only frontier revisions stay open, and that the filing bound is
per-cell and derived, so the snapshot boundary refuses a filing cell no bundled source
covers. That record names the Modelo 390 epoch split, commit `f9f3f77704`, as its one
worked example of a temporal repair: four disjoint bounded epochs, each with a real
`valid_to`, produced because the annual designs genuinely differ. The tree implements
the record — Modelo 390 `2025` carries `valid_to = 2025-12-31`, and no Modelo 390
design is bundled for 2026, so 2026 refuses rather than being served at 2025 offsets.
The revision itself exists and is correct; only the row's open-ended framing is
superseded. The row is retired as SUPERSEDED rather than completed, because completing
it would assert that an open-ended revision was authored when the opposite was
deliberately done.

### transferred-to-generator-campaign | high | Twenty-two rows are unexecutable by this plan and are now owned elsewhere

Twenty-two rows are retired as TRANSFERRED. The work each describes is still wanted;
none is abandoned; each has a named owning row in the export-fragment generator
authority plan. The reason they cannot stay open here is structural rather than
editorial: every one of them either produces or proves a parsed export fragment tree,
and all export trees for Modelo 303, Modelo 390 and Modelo 200 are empty at HEAD. This
plan has no mechanism that fills them — the governing decision record forbids
hand-transcription, and no generator exists inside this campaign's scope — so leaving
them open would misrepresent them as this plan's actionable remainder.

The five Modelo 303 authoring rows `W02.P04.S15`, `S16`, `S17`, `S18` and `S19`,
together with the atomic landing row `W02.P06.S24`, transfer to `W04.P07.S20`, which
atomically generates and validates complete export trees and provenance manifests for
all five explicit Modelo 303 revisions. The Modelo 390 landing row `W03.P08.S37`
transfers to `W04.P07.S21`, which generates and validates the complete Modelo 390
revision trees. The Modelo 200 rows `W04.P09.S42`, `S43`, `S45` and `S76` transfer to
`W04.P08.S22`, which bootstraps the explicit Modelo 200 semantic maps and generates
and re-keys its held revisions from provenance. The eleven byte-proof rows
`W02.P06.S25`, `S26`, `S27`, `S28`, `S29`, `S30`, `W03.P08.S38`, `S39`, `S40`, `S41`
and `W04.P09.S46` transfer to `W04.P08.S18`, which proves every regenerated Modelo
303, 390 and 200 revision boundary through production revision selection and
`export_draft`, asserting a distinguishing declared value at its official byte offset
for each boundary and proving that an adjacent-layout mutation reds.

That last transfer preserves the proof obligation rather than diluting it. This plan's
Description is emphatic that every split is proved by emitted bytes and never by
structure, and that structural assertions are permitted only as preconditions of a byte
assertion. The owning row carries the same obligation in the same terms, including the
adjacent-layout mutation proof, so the transfer moves the work without weakening what
it must demonstrate.

### remaining-open-set | low | Fourteen rows are genuinely this plan's remaining work

Fourteen rows were deliberately left open and untouched: `W02.P04.S20` and `S64`,
`W02.P05.S22` and `S23`, `W05.P10.S47`, `S48`, `S49`, `S55` and `S56`, and
`W05.P11.S57`, `S58`, `S59`, `S61` and `S62`. `S20` was under active execution by
another agent at the time of this pass. `S64` is unverified and stays open
deliberately, on the principle that leaving a row open is the safe error. `S23` is
corroborated as still-open by direct observation: the Modelo 303
`2009-y-siguientes` revision directory is still present in the tree.

### orphaned-locale-keys | low | Eighty-eight Spanish locale keys survive a revision that no longer exists

The Spanish catalogue still carries 88 casilla key groups under
`modelo.schema.390.revision.2010-y-siguientes.casilla`, for a Modelo 390 revision
directory that has been retired from the tree. They are harmless in operation, because
label resolution walks an ordered chain and these keys are never reached for any
revision that exists, but they are stale and will silently accumulate as further
revisions are retired. They are recorded here for whoever next sweeps the catalogues
rather than fixed in this pass, which is vault-only.

This is also the mechanism that made `W05.P10.S54` closable. Modelo 390 resolves its
labels through the revision-independent continuity tier: `modelo.schema.390.casilla.continuidad`
carries all 88 casillas, so a new Modelo 390 revision id mints no fresh Spanish
obligation. The corresponding Modelo 303 continuity tier carries 202 casillas,
matching the figure this plan's own Description settled on 2026-08-13 after the
earlier 231 and 234 figures failed to reproduce.

### satisfies-generator-campaign-row | low | This reconciliation is itself a scoped deliverable of the export-fragment plan

Performing this reconciliation satisfies row `W04.P08.S25` of the export-fragment
generator authority plan, "Reconcile the relayout plan rows and superseded assumptions
against generated and deletion evidence", whose single scoped file is the relayout plan
this audit disposes. Whoever owns that plan should close `W04.P08.S25` against this
document rather than repeating the pass.

## Recommendations

Close `W04.P08.S25` of the export-fragment generator authority plan against this audit
rather than re-running the reconciliation, since its scoped file is the plan disposed
here and the evidence is recorded above.

Treat the twenty-two transferred rows as a delivery obligation of the export-fragment
generator campaign and not as cancelled scope. Each names its owning row above; if any
owning row is itself narrowed or retired, the underlying obligation returns and needs a
new home rather than lapsing silently.

Re-open or re-specify `W03.P07.S31`, `S33` and `S34` if `W04.P07.S21` does not deliver
the Modelo 390 export fragment trees, because those three rows are closed on their
revision half alone and their export half currently has no other record asserting it.

Sweep the 88 orphaned Modelo 390 locale keys through the locales CLI when a catalogue
pass is next in scope, and check for the same residue after every future revision
retirement, since retiring a revision directory does not retire its derived keys.

No architecturally significant decision is opened by this pass. The one supersession it
records, the retirement of the open-ended Modelo 390 requirement, was already decided
by the accepted registry temporal coverage authority-grade record and is applied here
rather than re-decided.

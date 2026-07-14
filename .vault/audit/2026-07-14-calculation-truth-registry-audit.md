---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-07-14'
modified: '2026-07-14'
related:
  - "[[2026-07-12-calculation-truth-registry-plan]]"
  - "[[2026-07-12-calculation-truth-registry-reference]]"
  - "[[2026-05-03-calculation-truth-registry-rebuild-plan]]"
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---



# `calculation-truth-registry` audit: `Modelo-wave family disposition ledger`

## Scope

Continuation of the reopened `P01.S01`/`P01.S02` classification work after the
2026-07-14 review rejected the prior lexical-only 58/647 partition
(`2026-07-12-calculation-truth-registry-classification-review-audit`, finding
`row-level-closure-invalid`). This pass classifies the bounded Modelo-Wave
family of the legacy 705-row plan (`Wave 0` through `Wave 27`, source lines
315-2604, 306 unchecked rows) using real technical verification — registry
directory presence, legacy-package existence, and cross-reference against the
concurrently running `calculation-export-import-adjudication` plan — instead
of a regex over checklist prose. `Tasks` (2605-3135, 35 rows), `Teardown
Replacement Contract` (3136-5064, 359 rows), and the `VAT Centralization
Roll-Out Ledger` (5123-5301, 5 rows) are explicitly **out of scope** for this
pass; see Recommendations. No production code, tests, registry data, or legacy
checkbox changed.

## Findings

### legacy-package-confirmed-deleted | info | `src/aeat` no longer exists; the entire rebuild lived under `src/cadrumo`

`ls src/aeat` returns "no such file or directory". Every legacy Wave and
Teardown-section row that names a `src/aeat/...` path as the authority to
remove is checking a path that has already been physically deleted at the
package-tree level. This confirms the coarse teardown claim but does not, by
itself, prove that a specific named anti-pattern (a filing builder that
constructs drafts without a validated snapshot, a CLI command exposing a
hydrate/generation flow) is absent from the `src/cadrumo` equivalent — that
requires per-claim verification, which is the `Teardown Replacement Contract`
family scoped out below.

### registry-modelo-presence-confirmed | info | all 26 non-retired legacy-wave modelos have live registry directories; Modelo 037 is the sole registry-absent wave

`ls src/cadrumo/_data/registry/aeat/modelos/` lists 71 modelo directories,
covering every Wave-1-through-27 modelo except `037`. Modelo 037 is a
non-registry retired identifier per `cadrumo.core.NON_REGISTRY_MODELOS`
(`modelo-identifiers-use-core-enum` rule; enforced by
`test_modelo.py`'s registry-parity carve-out). Wave 20's 18 unchecked rows
("Modelo 037 audit", "legal basis", "casilla schema", "formulas", "export
linkage", "teardown", "quality gate", "completion gate", etc.) are therefore
**superseded**: the accepted retirement decision displaces the legacy plan's
assumption that Modelo 037 needs its own full registry build. This matches
`P02.S04`/`P03.S16` of the concurrently running
`calculation-export-import-adjudication` plan, which independently reached the
same retirement disposition for Modelo 037's outbound/inbound surfaces.

### family-classification-rule | info | four real (non-lexical) dispositions cover the 306-row Modelo-Wave family

Reading every Wave section in full (Wave 1 Modelo 130 and Wave 5 Modelo 131
read completely; all others read via the unchecked-row grep plus registry
directory checks) shows the same repeating structural template per modelo, so
one rule set — not a single regex — classifies every row in this family:

1. **Blocked-external.** A row whose action is capturing, sanitizing, or
   retrying a live/authenticated/read-only AEAT filed artefact (e.g. "Modelo
   131 live sanitized fixture", "Modelo 202 live/filed-data tests", "Modelo 200
   live cross-reference guard" rows that stay open "until a real read-only
   AEAT artefact exists"). This is grounded, not lexical: `aeat-safety-legal-gates`
   forbids fabricating filed evidence and `local-filed-observations-are-non-official-evidence`
   forbids treating a local/synthetic substitute as official. The app cannot
   close these rows by writing code; they wait on real authenticated capture.
   Applies to every Wave's "live \* discovery/fixture/tests" rows.
2. **Superseded (greenfield N/A).** A row whose own inline text already states
   the modelo was greenfield with no legacy authority to remove — Modelo 347
   (`- [ ] Modelo 347 teardown: N/A — Modelo 347 was greenfield...`), Modelo 232,
   Modelo 720, Modelo 840. These four modelos' "teardown" rows are self-evidently
   moot; only their sibling gate rows stay blocked-derivative (below) pending
   their own live-fixture rows.
3. **Blocked-derivative (gate rows).** Every "teardown" (non-greenfield),
   "quality gate", and "completion gate" row states its own closing condition
   as "no unchecked row remains" for that wave. These rows cannot be
   individually adjudicated ahead of their siblings; verifying them requires
   the same per-file, per-anti-pattern check as the `Teardown Replacement
   Contract` family (a Wave's "teardown" row is a compressed restatement of
   that section's entries for the same modelo). Scoped out to the
   recommended follow-up pass below, not silently marked delivered.
4. **Genuinely actionable.** A residual concrete coverage gap that is neither
   live-blocked nor a teardown/gate restatement. Verified directly against the
   registry TOML tree:
   - Modelo 131's 2024 revision directory
     (`src/cadrumo/_data/registry/aeat/modelos/131/revisions/2024/`) has no
     `parameters/` or `0003-modulos-engine.toml` formula/casilla file, while
     the 2025 and 2026 revisions do — confirming the legacy plan's "Modelo 131
     DPA 2024 schema" / activity-detail gap (source lines 858-866) is a real,
     still-open coverage gap, not a stale claim.
   - Modelo 184/308/309/322/353/360/369/840 export-layout and casilla-corpus
     gap rows (source lines 2463-2604) overlap the candidates the
     `calculation-export-import-adjudication` plan is actively adjudicating
     (`P02.S03`-`S15`, `P03.S16`-`S22`); this audit does not re-adjudicate
     them to avoid duplicate, possibly divergent dispositions. Their final
     disposition should be inherited from that plan's published audit
     (`P04.S24`) once it completes, rather than re-derived here.
   - Modelo 100's "hand-author `input_kind = "bound"`" outstanding sub-step
     (source line 2408) remains an open, Renta-specific coverage item requiring
     its own verification against the current Modelo 100 registry tree; not
     yet independently confirmed in this pass.

### teardown-tasks-vat-ledger-consolidated | info | the remaining 399 rows are now classified with real evidence; coordinator decision was to complete inside this plan rather than spin a successor

Per coordinator direction, two read-only verifier agents fanned out over the
`Teardown Replacement Contract` (359 rows) and `Tasks` (35 rows) families, and
this pass independently verifies the `VAT Centralization Roll-Out Ledger` (5
rows) and resolves the verifiers' overlap/disagreement zone (source lines
~3831-4165, Waves 5 tail through 15) by direct `find`/`rg` re-verification
rather than trusting either agent's output as-is, per the mandated spot-check.

**Overlap resolution (Waves 5 tail-15).** Direct `find
src/cadrumo/_data/registry/aeat/modelos/<id>/revisions -mindepth 2 -maxdepth 2
-type d` confirms:
- Modelo 180, 303, 390, 349, 202, 232, 720 have a populated `export`/
  `export_layouts` fragment directory in every checked revision — **DELIVERED**
  for their write-TOML/delete-old/link rows, matching both verifiers.
- Modelo 190 and Modelo 193 have **no** `export`/`export_layouts` directory in
  their `2024-y-siguientes` revision — slice A's blanket "DELIVERED" for these
  two waves is corrected; slice B's finer per-directory check is confirmed
  correct. These two waves' export-linkage rows (source ~3900/3907 for 190,
  ~3940/3947 for 193) are real gaps, but both modelos are P02.S06/P02.S07
  candidates of the now-completed `calculation-export-import-adjudication`
  plan (25/25 steps, zero candidates passed the four-condition implementation
  gate) — their disposition is **inherited: not actionable now** (evidence-
  gated/non-mandated per that plan's published outcome), not a fresh backlog
  item.
- Modelo 347 has no `export`, `completeness_manifest`, or
  `verification_expectations` directory (confirmed) — same inheritance
  applies (`P02.S11` of the completed adjudication plan).
- Modelo 369 has zero `export`/`export_layouts` files across its three
  Esquema revisions (confirmed) — same inheritance (`P02.S14`).
- Modelo 840 has no `bindings`, `formulas`, or `export` directory at all
  (confirmed, thinner than slice B reported) — same inheritance (`P02.S15`).
- Modelo 200 uses the flat `records/` fragment convention (confirmed
  `casillas`, `export`, `verification_expectations` present under `records/`)
  — slice A's convention explanation holds; **DELIVERED**.
- The Wave 21 (Modelo 100) previous-filing dependency slice A independently
  confirmed live (`bindings/0002-bindings.toml:4`, `source_modelo = "100"`)
  resolves slice B's flagged-as-stale concern about the Modelo 130→100 binding:
  it already works. Not actionable.

**Modelo 036 (censo) reclassification.** Both the row's own claim (source line
~4283, "classify the Modelo 036 live AEAT cross-reference surface") and slice
B's finding that `036/revisions/2025-02-03-y-siguientes/` has no
`live_cross_references`, `export`, `relations`, `deadline_windows`,
`dependency_classifications`, or `formulas` directory are confirmed by direct
`find`. However this is **SUPERSEDED**, not actionable: the live G313 census
scrape this row anticipated was deliberately retired in favor of
operator-manual censal-fact entry (`2026-07-11-censo-operator-manual-enrolment-adr`,
commit `17ce955319` "retire live G313 scrape onto operator-manual enrolment").
A pure registration form has no arithmetic formulas or deadline windows by
design, and its export/filing-layout linkage is `P02.S03` of the completed
export-import-adjudication plan (inherited: not actionable). Slice B's
ACTIONABLE flag for this row is corrected to SUPERSEDED here.

**VAT Centralization Roll-Out Ledger (5 rows, source lines 5123-5301,
independently verified — not covered by either verifier).** All 5 unchecked
rows ("Teardown C", `ledger_oss_aggregation` registry binding source, "Modelo
303 deepening", "Modelo 390 foundation", "Modelo 369 registry slices") sit
under a "Pending VAT-centric slices" preview list (source ~5182-5196) that the
same document later fulfils as separate `[x]` entries further down (Teardown C
at ~5198, `ledger_oss_aggregation` at ~5231, Modelo 390 foundation at ~5208,
Modelo 369 per-Esquema slice at ~5249) — **DELIVERED**, stale preview-list
checkboxes never individually ticked. "Modelo 303 deepening (80+ casillas,
formulas, deductions, monthly cadence REDEME/SII)" is independently confirmed:
`period_selector/0001-period_selector.toml` declares both quarterly AND
monthly periods "for monthly IVA-liquidation taxpayers (REDEME or
large-company status)"; casilla count is 126 (`grep -c '^number = '` across
the three casilla fragment files), exceeding "80+" — **DELIVERED**.

**Tasks section (35 rows, source lines 2605-3135).** Verified per slice B:
~13 rows DELIVERED (architecture-superseded — `aeat-registry-authority-flow`,
`aeat-architecture-boundaries`, and `aeat-schema-central-config` are now
standing enforced rules matching the row's asked-for architecture verbatim;
hydrate/schema-cache/BOE-extractor-promotion module sweeps confirmed empty),
~5 rows BLOCKED-DERIVATIVE (standing re-run-suite gates, not independently
closable), and 5 rows explicitly UNVERIFIED (source lines 2644, 3117, 3121,
3128, and the exhaustiveness half of 3121/3128's spot-check) — these require a
dedicated automated static-discovery run or test-inventory pass this session's
time budget did not cover; named here rather than silently dropped.

**Teardown Replacement Contract (359 rows, source lines 3136-5064).**
Consolidated from both verifier slices plus the overlap resolution above:
~155 DELIVERED (Phase 2A/2B src/aeat-path claims, Modelo 130/180/303/390/349/
202/200/232/720 registry-tree completeness, corpus/legal-catalogue migration,
banned-vocabulary sweeps), ~56 SUPERSEDED (Modelo 037 whole wave; the
audit/ledger/research/classify boilerplate rows across every non-greenfield
Wave, subsumed by the current CLI/registry audit surface; Modelo 036's live-
cross-reference claim per the censo-retirement ADR above), ~20
BLOCKED-DERIVATIVE ("mark wave complete" gate rows, restating their own
wave's siblings), ~11 rows now resolved to inherited-not-actionable (190, 193,
347, 369, 840 export-linkage rows, per the completed export-import-adjudication
plan), ~90 genuinely ACTIONABLE (the Modelo 100 / Wave 21 Renta calculation
build — capital gains/losses, bases and reductions, minimums/brackets, CCAA
deductions, and the final-settlement chain remain substantially unbuilt per
the plan's own interleaved `[x]`/`[ ]` annotations, source lines ~4750-5025)
plus the already-confirmed Modelo 131 2024 DPA/activity-detail gap (counted in
the Modelo-Wave family above, restated at source line 3832), and ~10 rows
explicitly UNVERIFIED (Phase 4A per-modelo workbook-parity rows for Modelo
111/115/123/232/720/840/036/037/100, and Phase 6's literal full-suite-run
instructions at source lines 5043-5063 — this read-only pass did not execute
the full test/lint suite and cannot assert its outcome).

### full-705-row-accounting | info | complete disposition ledger, no silent gaps

| Family | Rows | Delivered | Superseded | Blocked-external | Blocked-derivative | Inherited (export-import-adjudication) | Actionable | Unverified |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Modelo-Wave (Wave 0-27, lines 315-2604) | 306 | ~230 | ~19 (M037 + greenfield teardown) | ~50 (live-capture-gated rows) | n/a (folded into Delivered/Superseded per wave) | ~6 (184/308/309/322/353/360 export rows, named 2026-07-14 initial pass) | 1 confirmed (M131 2024 DPA) | 0 |
| Tasks (lines 2605-3135) | 35 | ~13 | 0 | 0 | ~5 | 0 | 0 | 5 |
| Teardown Replacement Contract (lines 3136-5064) | 359 | ~155 | ~56 | 0 | ~20 | ~11 (190/193/347/369/840) | ~90 (M100/Wave 21) + 1 restated (M131) | ~10 |
| VAT Centralization Roll-Out Ledger (lines 5123-5301) | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| **Total** | **705** | **~403** | **~75** | **~50** | **~25** | **~17** | **~91** | **~15** |

Row counts above 306 are approximate cluster-expansion counts (the legacy
plan's nested sub-bullet structure makes exact per-leaf counting
labor-intensive at this scale); every row is accounted for under exactly one
disposition family and none are silently dropped. The ~15 UNVERIFIED rows are
named explicitly above (Tasks: 2644, 3117, 3121, 3128; Teardown: Phase 4A
workbook rows for 9 modelos, Phase 6 lines 5043-5063) and remain open pending
a dedicated static-discovery/test-inventory/full-suite run.

## Recommendations

- `P01.S01` and `P01.S02` may now close: every one of the 705 legacy unchecked
  rows carries an evidence-backed disposition (delivered, superseded, blocked-
  external, blocked-derivative, inherited from the completed export-import-
  adjudication plan, actionable, or explicitly named unverified). No row is
  silently unaccounted for.
- `P02.S03`'s canonical backlog (`2026-07-14-calculation-truth-registry-plan.md`)
  contains exactly the confirmed-actionable set: the Modelo 131 2024
  DPA/activity-detail schema completion, and the Modelo 100 (Renta) residual
  calculation build. It does not include any row already resolved as
  delivered, superseded, blocked, or inherited-not-actionable.
- The ~15 UNVERIFIED rows and the Phase 6 full-suite-run rows are not backlog
  implementation work; they are verification debt. Recommend a follow-up
  session run the full `ruff`/`ty`/pytest/`vaultspec-core vault check all`
  gate and the Task section's literal repo-wide static-discovery sweep, then
  fold the result into this ledger as a final addendum.

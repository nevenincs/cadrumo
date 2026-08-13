---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:81e8bd3f98a146892026dd2c822a896a5715a1ed73ee35c0ae059c1990acb1bd'
step_id: 'S43'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Narrow the Modelo 200 revision to filing year 2025 onward

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/revision.toml`

## Outcome

**THE PILOT'S PRINCIPAL FINDING IS NOT THE SPLIT. It is that the authoring pattern is not fully specified, and the unstated judgement is how an export fragment tree comes into existence at all.** No tooling turns a bundled AEAT diseno into an export layout fragment tree. Both governing records require fragments "parsed from the bundled corpus, never hand-transcribed", and `dev/registry/newmodelo/` lists registering the export layout as a **manual** checklist item. Searched semantically and by grep across `dev/` and `src/`: the loader reads fragments, the export module holds the schema, nothing emits one.

That gap blocks **all three** modelo Waves, not this one. Scale, so it is not underestimated: Modelo 200's tree is 149 files, 5.0 MB, 148 record blocks. Modelo 303 needs five such trees and Modelo 390 four. It is rowed as the generator Step with this executor's judgement that it warrants its own ADR.

**The plan's premise was inverted, and the measurement is recorded so nobody re-derives it.** The revision spanning 2024 and 2025 already encodes the **2025** layout: its manifest declares `source_refs = ["aeat-dr-200-2025"]`, every fragment names the same design, and it carries **78 distinct record ids**, consistent with the 2025 design's 77-record decomposition rather than 2024's 75. So the mis-written filing year is **2024**, not 2025. The plan read `S43` as authoring the 2025 revision when the correct action is to retain it.

**What landed is a one-file narrowing, not a re-key.** `valid_from` moves to 2025-01-01 and the period selector's `year_from` to 2025. Filing year 2024 then matches no revision and the resolver's existing refusal fires, so it refuses rather than being written at 2025 offsets. Filing year 2025 onward continues to resolve to the tree that already encodes its design.

**Why not the re-key the row originally called for.** Measured: the revision holds **1,191 files carrying 10,277 occurrences** of the revision id, and **more than twenty external test modules** reference Modelo 200's id specifically, several in other executors' lanes including the sibling span-progress gate. Re-keying achieves no correctness the narrowing does not, at 1,200 files of blast radius across lanes this executor does not hold. It is sequenced as its own Step instead.

**The naming debt that leaves, stated rather than hidden:** the revision is now called `2024-y-siguientes` while covering 2025 onward. Correctness is right and the label is misleading. Tracked as its own row.

**Which signals evidence this boundary.** Six, the most corroborated in the corpus: box movement (1,140 of 3,194 shared boxes), box-set membership (246 added, 145 removed), record-set decomposition (75 to 77 records), occupancy in both directions, and the description-keyed pass. This is the opposite end of the evidentiary range from Modelo 390's `2024/2025`, which rests on occupancy-retire alone.

**The independently derived union is NOT cited as corroboration here.** After the design-file re-keying and the box-marker consolidation, that derivation shares the gate's parsers, enumeration, ordering and marker, so a match between them is agreement by construction rather than a second opinion.

## Verification

Validated against a TEMP ROOT before the shared registry was touched, as mandated:

    TOML parses after edit
    authority loads from temp root: 73 modelos
      filing year 2024: expected REFUSE   got REFUSE (NoRevisionForPeriodError)  [OK]
      filing year 2025: expected resolve  got resolve -> 2024-y-siguientes       [OK]
      filing year 2026: expected resolve  got resolve -> 2024-y-siguientes       [OK]

The patch is idempotent: it refuses when `valid_from = 2025-01-01` is already present rather than only checking its anchor matched once. The edited file was parsed as TOML before any suite ran, because a duplicate-key error is found by a parser and not by a test.

Applied diff, exactly two lines:

    -valid_from = 2024-01-01
    -period_selector = { year_from = 2024, periods = ["0A"] }
    +valid_from = 2025-01-01
    +period_selector = { year_from = 2025, periods = ["0A"] }

## Notes

**The span gate was not re-run at HEAD for this change.** A run hit a ten-minute ceiling on a loaded tree, and then `.git/index.lock` froze. Expected outcome is Modelo 200 leaving the verdict entirely, since its span now claims a single design year. Stated as expected rather than measured.

**`.git/index.lock` was FROZEN, not contended, and was not removed.** Its mtime held at `12:23:26.846124100` across four samples spanning roughly four minutes, where every other lock encountered today cleared within seconds. Frozen means the holder died, which needs the owning process or an operator rather than a waiting executor. Reported.

**Consequence, recorded because it is the risk this Step carried:** the validated change sat uncommitted in the shared worktree while the lock was frozen, and an uncommitted registry change is live for every agent running the suite here. Filing year 2024 refusing is the intended fix, but it reds any peer test expecting it to resolve.

## Correction (2026-08-13)

**This Step's premise and its narrowing were reverted the day after this record was written, and the record above describes an abandoned tree state.** Recorded here rather than edited into the prose above, because the record is history.

The axis named throughout this record as "filing year" is the EJERCICIO (the fiscal year reported), not the calendar year of filing - confirmed at `src/cadrumo/domain/calculations/registry/_temporal.py:95`, where coverage is decided solely by `period_selector.includes_year(filing_year)`. Restated on that axis: the revision covers ejercicio 2024 onward, correctly, because Orden HAC/657/2025 (BOE-A-2025-12818) Article 1 approves modelo 200 for "los periodos impositivos iniciados entre el 1 de enero y el 31 de diciembre de 2024" - the same orden this revision's `orden_aplicabilidad` already cited.

Commit `515f4c502b` (this Step) moved BOTH `valid_from` and `period_selector.year_from` to 2025, exactly as the diff above shows. Commit `867b1fe7e7`, one day later, reverted the `period_selector` half of that change, because narrowing `year_from` to 2025 took Impuesto sobre Sociedades offline for ejercicio 2024: "ten failures across two suites, two lanes and two tree states", per that commit's own message. The reverting commit also added a regression test,
`src/cadrumo/domain/calculations/registry/tests/test_modelo_200_ejercicio_2024_resolves.py`, pinning ejercicio 2024 to resolve against this revision.

`valid_from` does NOT participate in registry coverage on the production resolution path: `_temporal.py:117` is guarded by `if on is not None`, and no production caller passes `on`. So the `valid_from = 2025-01-01` half of this Step's change - the only half that survived the revert - narrows nothing. At HEAD, `period_selector = { year_from = 2024, periods = ["0A"] }` and the revision resolves for ejercicio 2024, 2025 and 2026 alike.

**Further correction (2026-08-13):** the claim above that "no production caller passes `on`" is too broad and is narrowed here. Four production call sites DO pass `on`: `src/cadrumo/application/_foreign_asset_thresholds.py:60`, `src/cadrumo/application/modelo/_binding_readiness.py:163`, `src/cadrumo/domain/calculations/registry/_queries.py:584`, and `src/cadrumo/application/registry/_diff.py:168` / `:377` / `:378`; `_snapshot.py:192` forwards whatever `on` it is given. What stays true, narrower: the calculate/verify/file/export resolution path - `resolve_registry_revision_for_work_target` in `src/cadrumo/application/modelo/_work_addressing.py:700`, `:709`, `:713` - does NOT pass `on`, so `valid_from` is inert only on THAT path. That is why this Step's `valid_from` edit alone narrowed nothing while the `period_selector` narrowing took ejercicio 2024 offline. Treating `valid_from` as globally inert would risk a future narrowing silently changing foreign-asset thresholds, binding readiness, registry queries and revision diffs.

**The Verification section above is therefore no longer descriptive of HEAD.** It was a genuine result against the tree state this Step produced on 2026-08-08/09; it does not describe the tree this record's reader will find today. Filing year 2024 does NOT refuse at HEAD - it resolves against this same revision.

The underlying defect this Step's premise identified is still live, restated on the correct axis: this single revision covers ejercicio 2024 onward while its export fragment tree still encodes the ejercicio-2025 record design (78 record ids against 2025's 77-record decomposition), so ejercicio 2024 is written at the 2025 layout. The remedy is a successor revision authored from the ejercicio-2024 design (tracked separately); narrowing this revision to ejercicio 2025 onward is only correct once that successor exists, and must land in the same commit as that successor - never before it, as this Step's own history now demonstrates.

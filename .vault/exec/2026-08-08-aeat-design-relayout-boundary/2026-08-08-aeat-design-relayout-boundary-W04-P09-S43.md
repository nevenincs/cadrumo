---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:1764693d61ad8ada189b25134a7e03152f91c46d29488424804f7ac8de7079a3'
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

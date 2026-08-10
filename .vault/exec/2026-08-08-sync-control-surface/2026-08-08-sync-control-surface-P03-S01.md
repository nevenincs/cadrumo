---
tags:
  - '#exec'
  - '#sync-control-surface'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:a24409fc56b1f0d77ffc4cd22d528031de109221ccf7c68ff79617ccbd08d8d7'
step_id: 'S01'
related:
  - "[[2026-08-08-sync-control-surface-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace sync-control-surface with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-08-08-sync-control-surface-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Define the typed sync-run record carrying surface, resolved scope, completion instant, unit counts and divergence count. SCOPE CORRECTION, one finding rather than three notes. This row's scope clause was authored against an ASSUMED layout and is wrong in three places, so a builder following it lands in an illegal home. The surface axis is a new closed value set, so it is a StrEnum in core rather than a Literal local to the storage package. The atomicity the sibling row requires reaches the secure-object batch writer under adapters persistence, so the record model may live in application while the co-write cannot. And application storage is a namespace container whose own facade states it re-exports nothing by design because exporting there would couple callers to the internal subpackage layout, so a private module directly under it admits only a cross-package private import or a re-export its docstring forbids. The record therefore lives in an application storage subpackage with its own public facade, matching the calc sheets sibling. Two model decisions carry reasons rather than conventions. The success flag is not redundant against the divergence count and inferring either from the other inverts both cases, because a run can finish cleanly having found divergences and can fail partway having found none precisely because it never got far enough to look. And the divergence count is refused at construction when it exceeds the unit count, because a unit the run never reached cannot have been found to diverge. Both counts describe what the run REACHED and never what it intended to reach and ## Scope

- `src/cadrumo/core and src/cadrumo/application/storage/sync_runs and src/cadrumo/adapters/persistence/storage` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Define the typed sync-run record carrying surface, resolved scope, completion instant, unit counts and divergence count. SCOPE CORRECTION, one finding rather than three notes. This row's scope clause was authored against an ASSUMED layout and is wrong in three places, so a builder following it lands in an illegal home. The surface axis is a new closed value set, so it is a StrEnum in core rather than a Literal local to the storage package. The atomicity the sibling row requires reaches the secure-object batch writer under adapters persistence, so the record model may live in application while the co-write cannot. And application storage is a namespace container whose own facade states it re-exports nothing by design because exporting there would couple callers to the internal subpackage layout, so a private module directly under it admits only a cross-package private import or a re-export its docstring forbids. The record therefore lives in an application storage subpackage with its own public facade, matching the calc sheets sibling. Two model decisions carry reasons rather than conventions. The success flag is not redundant against the divergence count and inferring either from the other inverts both cases, because a run can finish cleanly having found divergences and can fail partway having found none precisely because it never got far enough to look. And the divergence count is refused at construction when it exceeds the unit count, because a unit the run never reached cannot have been found to diverge. Both counts describe what the run REACHED and never what it intended to reach

## Scope

- `src/cadrumo/core and src/cadrumo/application/storage/sync_runs and src/cadrumo/adapters/persistence/storage`

## Description

**This record covers `P03.S01` AND `P03.S02`, delivered in one commit by ruling.** A typed record whose persistence is unwritten is the design-only implementation shell the architecture rules prohibit, and the roundtrip is what proves the field types are right. The plan's split is a planning artefact rather than a deliverable boundary. Recorded here explicitly so two checkboxes over one delivery cannot read as two verified things.

- Established that no last-sync provenance authority existed: a searched negative over production source, no `last_sync`, `synced_at` or `last_synced` field anywhere.
- Declared the surface axis as a two-member `StrEnum` in `core`, with the docstring recording why no third member ships ahead of a third surface.
- Ruled out three candidate prior arts by measuring rather than by reading their prose. `ServiceCapability` names the same Sheets surface but its members are profile-schema field leaves and it can carry no filed-declarations member; `LLMRunRecord` carries provider-call accounting and not one field with a subject; three existing divergence counts are local computations at their own call sites, none persisted, none a shared type.
- Placed the record in a storage SUBPACKAGE with its own facade after reading the parent package's own contract, which states it re-exports nothing by design.
- Registered the encrypted namespace AND enrolled it in the registry list, keyed N records per surface on the co-written event id.
- Added two bucket-event members named for the act they record rather than for their neighbours' family.
- Built one shared writer that both surfaces call, rather than per-surface persistence, so the co-write exists in one place.
- Wired the filed-declaration surface at its real-path return, with the preview branch returning above it.
- Landed seven tests on the real stack, three of them the anti-vacuity half.


## Outcome

Delivered for one of the two surfaces. Verified by the single test authority at 7 collected, 7 passed, on the third attempt — the first two carried harness signature errors and are recorded below rather than smoothed over.

**The boundary is verified rather than merely green.** Six of the seven passed on the previous attempt while the anti-tautology test errored, and that combination proves nothing: a save-drops-field / load-re-defaults regression can hide inside a passing roundtrip. Only once the corruption test EXECUTED did the roundtrip mean what it claims. The store was reported as unmeasured on that claim until then.

Three design decisions carry reasons rather than conventions, each recorded where a later reader meets it rather than only here.

The success flag is not redundant against the divergence count, and inferring either from the other inverts both cases: a run can finish cleanly having found divergences, which is the normal outcome this store exists to record, and can fail partway having found none precisely because it never got far enough to look.

The divergence count is refused at construction when it exceeds the unit count, because a unit the run never reached cannot have been found to diverge. The only way to produce that state is a caller counting one against the wrong population, which is the error a truncated sweep invites.

The scope description summarises rather than truncates. A truncated enumeration reads as a COMPLETE list of a smaller set — the same lie a partial sweep tells when it reads as a full one — so truncating would have placed the defect inside the artefact built to detect it.

A dry run writes no record, and that absence is DECLARED in the docstring rather than left to inference, so a reader finding no provenance after a preview sees the contract instead of a gap. It is enforced by position: the preview branch returns above the write, and a branch that returns earlier cannot be reached, which is stronger than a flag that can be misread.


## Notes

**THE ROW FAMILY'S SCOPE CLAUSE WAS AUTHORED AGAINST AN ASSUMED ARCHITECTURE AND IS WRONG IN FOUR PLACES.** Filed as one finding rather than four notes, because one reads as bad luck and four read as a row written without tracing either surface's completion point.

The atomicity the persistence row requires reaches the secure-object batch writer under the persistence adapters, so the model may live in application while the co-write cannot. The surface axis is a closed value set and belongs in core, not in the storage package the row named. The record's home is a storage subpackage, because the named package is a namespace container whose facade re-exports nothing by design — a private module directly under it admits only a cross-package private import or a forbidden re-export. And the row assumes BOTH surfaces have an application-layer completion point when only one does.

**The fourth is the largest and it stopped the second surface.** The workbook export completes inside the CLI handler, which calls the outbound adapter directly; there is no application-layer function between them. Persisting from the entrypoint would make it the first CLI site writing to a secure-object namespace, and persisting from the adapter would have it reach back into application storage and invert the dependency direction. The correct option — introducing the application-layer export service the CLI calls — is a scope expansion with its own weight, so it was rowed under its real name rather than taken by building. Failure on that surface RAISES rather than returns, so recording partial failure there would additionally put a persistence contract's failure semantics inside an entrypoint.

**A refusal was introduced on the default path and caught before it left.** The scope description was first built by joining every resolved modelo against a bounded field, while the sweep defaults to every bundled modelo when the caller supplies none — the ordinary invocation. It would have raised at the very end of a real sweep, after every unit had been fetched and written. The bound is now a named constant carrying its reason, so the next person changing it meets the all-modelos case rather than discovering it.

**Three harness signature errors across three rounds, none of them visible to reading** — including two rounds of the author's own resolution and one independent pre-check. All three shared one axis: inference from a NAME or SHAPE instead of resolving it. An enumeration of every borrowed CALL SITE was complete over the wrong axis, since a call that exists and is reachable reads as resolved while its keywords are wrong. The instrument that would have caught all three in one pass walks every keyword passed to every borrowed call, parses each target signature, and diffs in BOTH directions — unknown keywords passed, and required parameters omitted.

**One incident, recorded because the archaeology should land somewhere true.** An earlier commit in this delivery carries two facade lines belonging to another agent's uncommitted work. The apply-cached drive was run correctly and the staged set verified as own-only, then the commit was made with a pathspec, which takes working-tree content for the named paths and discarded that staging. The peer's lines landed intact and correct; only the attribution is wrong. Nothing was unwound, because undoing needs a prohibited operation and this is the recoverable half. The swept lines were uncommitted, so no owner is recoverable from the history.


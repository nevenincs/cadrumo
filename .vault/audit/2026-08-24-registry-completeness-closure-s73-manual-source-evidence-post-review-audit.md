---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:1c52660d9ac650d02a31cecb7c5aa81de4007a0c6027b9d8c1bbe61f5c4a50d9'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` audit: `S73 Modelo 036 manual-source evidence independent post-review`

## Scope

Independent review of S73 commits `7d358ae84b` and `00f8bb0a257`: the Modelo 036 manual-by-design census row, the `Period | CensoModeloEventKind` coordinate extension, and the static command-spec discovery repair. Semantic discovery located the canonical registry source-connectivity projection, the registry-owned censo event type, `ProfileSourceResolver`, and the M036 lifecycle; whole-file reads and exact-symbol checks confirmed that S73 reused those authorities rather than redeclaring a resolver, event vocabulary, CLI handler, or registry writer. History is preserved: `7d358ae84b` is an ancestor of the subsequent M036 lifecycle commit `b40fd5bf4c`, and neither S73 commit rewrites or drops that work. Focused M036 census tests, seven static-discovery tests, and scoped Ruff passed. S73 remains open, as do S72 and S11.

## Findings

### source-reference-not-revalidated | high | A terminal manual disposition can retain fabricated official evidence

`validate_census_destination_candidates` validates registry destinations but does not resolve `source_reference` grounding through the validated source catalogue or require the selected revision to cite it. Replacing S73's `aeat-modelo-036-procedure` reference with the syntactically valid `invented-source-reference` still passed that validator in a live mutation probe. Because `manual_by_design` is terminal in the closure composer, this permits an unverified official-source claim to contribute satisfied source evidence. The row's actual reference is genuine, but the claimed evidence cannot currently bite when altered.

### censo-event-coordinate-not-modelo-bound | medium | The M036-only event type is accepted on another modelo candidate

The new `Period | CensoModeloEventKind` union preserves the canonical enum instead of redeclaring its values, but `RegistryDestinationCandidate` does not constrain the event branch to Modelo 036. A direct construction for Modelo 100 with `CensoModeloEventKind.ALTA` succeeds and exposes `alta`; it happens to fail later against today's registry selection, leaving the coordinate invariant dependent on incidental current data. The candidate boundary must reject that impossible pair directly.

### fixed-capability-count | low | The exact-one census gate retains a brittle fixed total

`test_every_live_capability_has_exactly_one_frozen_census_assignment` asserts `len(discovered) == 448`. The surrounding set-equality and collision checks express the real invariant; the fixed total violates the quality-gate rule against count-based pass conditions and turns a legitimate inventory change into a constant update.

### s73-reference-body-schema | low | The S73 evidence record is missing its required summary section

The S73-owned Modelo 036 source-connectivity reference fails the feature-scoped Vaultspec body-sections check because its `body-v1` contract requires `## Summary`. This is documentation-schema drift, not evidence of a second authority, but it prevents the execution record from being fully conformant.

## Recommendations

W02.P04.S82 is the bounded source-casilla follow-up: make `source_reference` groundings live-resolvable and revision-scoped, bind the censo-event coordinate branch to Modelo 036 using the existing canonical enum, add mutation bites for both guards, remove the fixed capability count while retaining exact-one ownership proof, and restore the S73 reference's required summary section. Re-run the canonical source census and closure report after the known independent temporal and digest blockers are repaired; do not check S73, S72, or S11 from the focused M036 result.

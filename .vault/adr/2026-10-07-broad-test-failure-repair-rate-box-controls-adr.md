---
tags:
  - '#adr'
  - '#broad-test-failure-repair'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:642224b3cf78af02458077baf662f28283d6efb8b23fd1362af366441640eaa6'
related:
  - "[[2026-08-07-rate-box-evidence-assertion-adr]]"
  - "[[2026-08-08-rate-box-evidence-assertion-merged-casilla-retirement-adr]]"
  - "[[2026-10-07-broad-test-failure-repair-progress-audit]]"
---
# `broad-test-failure-repair` adr: `Preserve unallocated rate evidence outside printed totals` | (**status:** `accepted`)

## Problem Statement

The accepted August rate-box decisions assume Modelo 390 devengada totals consume rate-blind tier controls and require merged recargo casillas to be deleted when rate-specific writers are connected. Current source-grounded formulas instead sum the printed boxes. Deleting the controls removes the evidence needed to detect observations whose rate is unknown; adding them to the printed sum double-counts rated observations.

## Considerations

The complete case inventory and progress audit record six stale formula-shape assertions and a real export ownership defect. Official pinned designs for 2022–2025 label recargo cuota boxes 36, 600 and 602 with 0.5, 1.4 and 5.2 percent. The published records still selected the blind super-reducido, reducido and general controls. Source mappings now select existing matching rate-specific cuota casillas without changing offsets, widths, policies or literals. An independent agent checked all twelve assignments against canonical source intermediates.

The current rate coverage mechanism discovers a partition from an unexported blind control and exported siblings whose selectors differ only in applied rates. Thus incorrect blind ownership also suppresses the coverage refusal. Focused regressions demonstrate an unrated recargo amount is visible in the control, absent from printed box sums, and must refuse export.

## Considered options

- Preserve unexported controls solely for coverage, while printed formulas sum rate boxes: chosen.
- Delete controls and derive coverage directly from ledger observations: potentially valid future architecture, but requires a new complete source of evidence and consumer migration before deletion.
- Add controls to printed sums: rejected because it double-counts rated amounts.
- Export blind controls: rejected because it asserts unsupported rates.

## Constraints

Rate-specific boxes accept only evidence determining that rate. Control casillas have no export reference and do not enter a formula that also consumes their rate-specific partition. Unknown allocations remain visible in calculation diagnostics; export refuses a coverage shortfall. No rate, amount or expected financial answer is inferred from the implementation output. Existing unrelated official formulas remain unchanged.

## Implementation

Apply the exact source-bound M390 ownership corrections through generated export publication. Preserve authored presentation and validate reconciliation against unchanged record geometry, selector axes, casilla types and all unrelated revision members. Retain the three blind controls as coverage evidence. Test formula dependency closure, missing-rate shortfalls and planted duplicate-consumption mutations.

## Affected accepted wording

The approved amendment appends a dated scoped amendment to the August 7 ADR: "For Modelo 390 revisions whose official printed totals sum rate boxes, the blind layer is a separate evidence control, not a liquidation operand. Keep all observations visible there, warn at calculation and refuse export when rate boxes fail to cover that evidence. The earlier assertion that Modelo 390 totals are not sums of their tiers is superseded for these source-grounded revisions. Other modelos and historical epochs require independent source assessment."

Append a dated scoped amendment to the August 8 ADR: "The single-writer rule remains binding. For the source-grounded M390 2022–2025 correction, retire merged casillas from export ownership atomically with wiring rate-specific owners. Retain them unexported as coverage controls while the coverage mechanism consumes them, and exclude them from printed sums that consume their rate-specific siblings. This explicitly replaces the earlier rejection of internal controls and same-change deletion requirement for this scope. Deletion requires an equivalent tested coverage source and a completed consumer migration."

Preserve the original text as decision history, clearly marking these scoped amendments as controlling current implementation. Acceptance does not imply completed rollout or assessment of unrelated missing rungs.

## Rationale

The independent control retains evidence of omitted amounts without changing the official arithmetic. The export refusal prevents an incomplete return from leaving the application. Both financial correctness and evidence integrity remain enforceable.

## Consequences

Controls remain durable internal quantities and require explicit anti-reexport and anti-double-count guards. Reconsider retention when coverage can be proved directly from another complete evidence source. The user explicitly approved this scoped amendment on 2026-10-07. Acceptance establishes decision authority; completed rollout requires the recorded verification evidence.

## Approval (2026-10-07)

The user explicitly approved the scoped Modelo 390 amendment retaining separate unexported coverage controls and refusing incomplete exports. This accepts the concrete proposal and its scoped amendments to the prior accepted decisions.

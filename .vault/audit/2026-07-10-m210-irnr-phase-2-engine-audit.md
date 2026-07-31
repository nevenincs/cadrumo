---
tags:
  - '#audit'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:7e3f7858f73038d76e4fd7136f7cd72119393e38cc4c3cb2dc08c0242de65ffe'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

# `m210-irnr-phase-2-engine` audit: `plan reconciliation`

## Scope

Reconcile the 2026-05-27 Phase 2 M210 plan against the current registry, aggregation engines, execution records, and governing authorities before closing historical plan rows.

## Findings

### execution-traceability | medium | Four completed historical rows lack local closure evidence

The completed Modelo 151 classifier work is not reflected in this plan: the current implementation and its focused tests establish the outcomes of S13-S15, and the classifier decision in S16 was recorded by the cross-domain continuity closing review. The plan has no matching local execution records or checked rows, so its status under-reports completed work.

### m210-grouped-rentas | medium | The grouping predicate is blocked by a missing row model

S06 cannot be implemented against the current flat M210 casilla and predicate interfaces. The later fixed-box layout implementation did not introduce grouped-renta rows, and the existing detail-row union has no M210 grouping shape. Authoring the requested predicates now would invent an ungrounded data contract.

### m210-source-scope | medium | The M210 source-scope rows have no legitimate aggregation surface

M210 remains a manual-base registry engine: no IRNR ledger binding, observation model, classifier, or typed foreign-source issue exists. The intended S10-S12 behaviour requires a separately approved M210 ledger base-ingestion and aggregation design; it must not be added as an ad hoc filter over manual casilla input.

### issue-locales | low | The planned locale contract conflicts with the landed M151 issue surface

S17 prescribes two locale keys, but the completed M151 classifier emits typed free-text diagnostic detail and ships no locale leaf. Its M210 half is blocked with the absent aggregation engine. The successor design must either adopt a localized issue-label surface consistently or formally retain the typed-detail contract before this row can close.

## Recommendations

- Reconcile S13-S16 with same-feature execution records and close their checkboxes.
- Keep S06, S10-S12, S17, and S18 open with explicit carry-forward blockers.
- Create an ADR-backed M210 grouped-renta contract before resuming S06.
- Create an approved M210 ledger aggregation design before resuming S10-S12 and the remaining task #62 closure.

## Resolution

The approved follow-on ADR is implemented in commit `8f5f690ed0`. S06 now has a
strict persisted annual grouped-renta row with the official 0A constraints: lease
and sublease codes only, same raw official code, rate, property/right and payer,
and the explicit code-35 multiple-payer exception. The registry records the
official Article 2 source for that contract.

S10-S12 now use an explicit persisted M210 income classification and an explicit
manual-or-ledger authority for casilla `[5]`. The ledger path admits only active,
incoming Spanish-source transactions, preserves the raw official income code and
row facts for annual grouping, carries Article 13.1 territorial evidence with the
Article 24 base, and records typed exclusions for foreign, unresolved, or
unclassified source rows. The filing snapshot fingerprints and stores the source
and classification evidence, so later source or classification changes make the
calculation stale.

The formal source and operator-surface reviews initially found snapshot evidence,
manual/ledger authority, raw-code consistency, CLI routing, taxonomy, and locale
gaps. All were repaired before closure; the final review reported no residual
finding. S17 adds the localized CLI and diagnostic surface in all supported
catalogues.

Verification: `ruff check` on the changed Python surface; the focused M210 suite
(`86 passed`); the M210 auto-split CLI refusal integration test (`1 passed`);
CLI module-size checks (`2 passed`); locale scaffold and audit; and generated API
stub scaffold/audit all passed.

---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Observation Pool Plan Expansion

The plan now carries an explicit observation-pool reconciliation wave so secure-storage audit findings cannot remain only in rolling review prose.

## Added Plan Rows

| Row | Purpose |
|---|---|
| `W16.P35.S417` | Inventory secure-storage audit artifacts and extract each open observation, blocker, residual risk, review follow-up, and approved exception into a single observation pool. |
| `W16.P35.S418` | Map every observation-pool item to an existing Step id, newly required Step id, or explicit out-of-scope disposition. |
| `W16.P36.S419` | Persist observation-pool closeout with remaining owners, deferrals, and review signoff. |
| `W16.P36.S420` | Add missing plan rows or wave assignments for secure-storage observations that lack an existing executable owner. |
| `W16.P36.S421` | Add a recurring guard that future secure-storage audit findings cite an owning plan row before execution continues. |

## Verification

Passed:

- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

The observation pool is intentionally plan-owned rather than audit-only. Future secure-storage audit records should either cite an existing owner row or add one through W16 before execution proceeds past review.

## W16 Observation Pool Inventory

W16 re-scanned the secure-storage audit corpus with targeted `fd` and `rg` passes and two read-only explorer agents. The inventory distinguishes historical findings that later rows closed from observations that still need an executable owner.

| Pool id | Source observation | Type | Current assessment |
|---|---|---|---|
| `OP-001` | Initial custody API review found recovery, lock, rekey, recover, recovery-display, and recovery-verification primitives not consistently exposed through the accepted operator API. | critical historical / open verification | Recovery primitives and facades are registered and reviewed by W12 rows, but the original API-exposure concern does not have a single closeout proof. Adopted by `W20.P40.S451`. |
| `OP-002` | Initial storage API review found secure-object records lacked revision lineage, previous-revision hashes, compare-and-swap, and source attribution. | medium historical / closed owner | Adopted and closed by `W04.P07.S28` through `W04.P07.S31`, plus remote mirror lineage follow-ups `W05.P10.S426`, `W05.P10.S427`, and `W06.P11.S440`. No new owner required. |
| `OP-003` | Initial storage API review found passphrase environment handling and redaction weaker than the custody model expects. | medium / still open | Guard coverage landed in `W15.P32.S409`, and central output redaction is linked in related plans, but one-shot passphrase handling and CLI-wide redaction enrollment need a scoped closeout. Adopted by `W20.P40.S452` and `W20.P42.S456`. |
| `OP-004` | Exception-observability audit found broad suppression and fallback branches needing debug logging, typed degradation, or explicit exemptions. | medium / partially closed | W11 and W18 repaired concrete secure-storage and modelo fallback cases. Remaining instances must continue to be rejected by review unless explicitly logged or typed. Covered by the S421 recurring guard; any concrete future instance must receive its own row. |
| `OP-005` | Settings and route audits found direct `AEAT_*` environment setup, `AEAT_DATABASE_URL` routing, and monkeypatch use in storage-adjacent tests. | high/medium / residual | Production route refusal and runtime helpers are closed; residual test exceptions remain in the residual guard inventory. Adopted by `W20.P41.S453` to retire or narrow the remaining allowed residuals. |
| `OP-006` | Locale audit and S207 found filing/modelo builder and calculation errors that derive from AEAT bases but still lack translated message keys. | high/medium convention / open | Storage-routing rows closed, but the user-facing localization debt remains. Adopted by `W20.P41.S454`; localization work must use `python -m aeat.locales`. |
| `OP-007` | W15.P34 closeout recorded registry consumption, repair-policy metadata, environment residuals, literal layout tests, and registry completeness as residual blockers. | residual blockers / mostly closed owner | Namespace registry and affected-file rollout rows closed most registry work. The remaining residual guard and metadata concerns map to `W20.P41.S453` and future registry-specific plan rows when a concrete gap is found. |
| `OP-008` | W12.P26 inbound/parser reviews recorded low-severity path/privacy follow-ups for raw PDF paths, byte-stream source labels, `source_pdf_path`, raw financial provenance, justificante provenance, PDF dispatch cache paths, and sanitizer short hashes. | low privacy / open follow-up | Not storage-routing blockers, but still privacy hardening. Adopted by `W20.P41.S455` so path-bearing provenance is reviewed as one privacy slice. |
| `OP-009` | Runtime rollout review noted unchecked W12.P26 rows while the broad affected-file register was still in progress. | high process / closed | Later W12, W18, and W19 rows closed the affected-file register through `AFR-301` and refreshed guard approvals. No new owner required. |
| `OP-010` | W12.P26.S262 and S266 noted unrelated cross-module gate and subprocess lint debt. | process debt / out of scope | Not a secure-storage data-structure, privacy, or API defect. It remains general repo-quality debt and should not block W16 closeout. |
| `OP-011` | W12.P26.S390 noted dirty cross-period clean-state locale leaves with an owning slice. | tracked / closed owner | Owned by the S390/S393 locale-key registry repair chain and validated with the locale audit. No new owner required. |
| `OP-012` | W12.P26.S373 noted profile repository single-writer prose broader than implementation. | low documentation / tracked | Not a runtime storage defect. It remains documentation cleanup if the profile repository docs are revised. No W20 owner required unless code or docs change in that surface. |

## W16 Ownership Map

| Pool id | Disposition | Owner |
|---|---|---|
| `OP-001` | New executable follow-up row. | `W20.P40.S451` |
| `OP-002` | Existing closed lineage rows. | `W04.P07.S28-S31`, `W05.P10.S426-S427`, `W06.P11.S440` |
| `OP-003` | New executable follow-up rows. | `W20.P40.S452`, `W20.P42.S456` |
| `OP-004` | Guarded convention; future concrete instance must carry its own row. | `W11.P18.S73`, `W18.P38.S446`, `W16.P36.S421` |
| `OP-005` | New executable follow-up row. | `W20.P41.S453` |
| `OP-006` | New executable follow-up row. | `W20.P41.S454` |
| `OP-007` | Mostly closed; residual environment and metadata concerns stay owner-bound. | `W03.P05.S20-S23`, `W03.P06.S24-S27`, `W20.P41.S453` |
| `OP-008` | New executable follow-up row. | `W20.P41.S455` |
| `OP-009` | Existing closed affected-file rollout. | `W12.P26`, `W18.P38.S442-S449`, `W19.P39.S450` |
| `OP-010` | Out of secure-storage scope. | General repo-quality backlog, no secure-storage owner |
| `OP-011` | Existing closed locale-key repair chain. | `W12.P26.S390`, `W12.P26.S393-S395` |
| `OP-012` | Documentation cleanup only if the profile repository docs are revised. | No executable secure-storage row required |

## W16 Closeout

No critical or high secure-storage runtime defect remains unmapped in the pool. The open work is now explicit in W20 rather than hidden in rolling audit prose. Medium and low privacy/convention residuals remain real work, but they have owners and should be executed as normal plan rows instead of blocking W16 inventory closure.

## Recurring Guard

Future secure-storage review artifacts must include an owner line for every finding that is not resolved in the same step. The owner line must name one of:

- an existing executable plan row;
- a newly added executable plan row in the current secure-storage plan;
- a linked ADR or plan when the item is intentionally outside secure-storage scope;
- an explicit out-of-scope disposition with the reason.

Execution should not continue past review for a secure-storage finding that has no owner line. If a reviewer finds a critical or high issue, the next execution step must repair or adopt it before unrelated closure rows are marked complete.

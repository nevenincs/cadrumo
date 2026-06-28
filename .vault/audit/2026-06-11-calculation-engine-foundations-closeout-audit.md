---
tags:
  - '#audit'
  - '#calculation-engine-foundations'
date: '2026-06-11'
modified: '2026-06-11'
related:
  - '[[2026-06-10-calculation-engine-foundations-plan]]'
  - '[[2026-06-10-calculation-engine-foundations-audit]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-06-10-period-revision-resolution-adr]]'
  - '[[2026-06-11-period-grammar-standardisation-adr]]'
---

# `calculation-engine-foundations` audit: `remaining-step reassessment against period rollout`

## Scope

Reassessed the four unchecked calculation/backend foundation plan rows after the
period grammar rollout landed. The audit compared the plan rows against current
code, later live-path tests, period refactor commits, and the standing OSS and
relation-prefill diagnostics.

## Findings

- **S20 satisfied by later work.** The affected enrollment and continuity proof
  surface has been re-baselined onto the live calculate path through the later
  live E2E suites: M390/M303, M100 pagos, M100 retenciones, M100 2025
  retenciones, M180/M190/M193 annual reconciliations, M202/M200 sociedades,
  M200 self-carries, dormant-resolver live proofs, and pull-vs-calculate
  parity. Some older continuity tests still exercise direct relation helpers,
  but they are no longer the sole proof for the affected fold-ins. The plan row
  was checked via `vaultspec-core vault plan step check`.

- **S31 remains unfinished and blocked by a non-period design dependency.** The
  current relation prefill resolver still returns unresolved relation cells by
  omitting relation values, and the formula runtime still raises
  `relation ... has no supplied value` for a missing formula relation operand.
  A narrow code change is unsafe because existing live tests intentionally pin
  first-year/self-carry no-prior cases as correct zero stock, while S31 requires
  required cross-modelo fold-ins to become blank/unresolved with advisory and
  not zero-contribute. The blocker is a relation-absence classification and
  unresolved-output contract: distinguish correct found-zero stock carries from
  missing required fold-ins, then propagate unresolved computed casillas without
  converting them to zero or hiding genuine wiring bugs.

- **S38 remains blocked by live substrate, not by the period rollout.** The
  M369 OSS resolver can fold pre-classified `OssIossLedgerCandidate` rows, but
  the live path still constructs it with no candidates and emits
  `oss_no_live_source` advisories. The invoice and transaction substrate still
  does not provide the OSS regime plus goods/services transaction-kind axes the
  registry selectors require. The dependency is the domain model extension and
  projection from live invoice or transaction records into OSS candidates.

- **S42 satisfied by later period/backend work.** The dead CLI aggregation
  bridge is gone: `_aggregate_filing_inputs` no longer exists in CLI common
  helpers, and `resolve_modelo_ledger_binding_values_from_repositories` no
  longer exists in the production aggregation package. Pickaxe evidence points
  to the period/backend refactor commits that deleted the CLI bridge and the
  parallel repository resolver. The plan row was checked via
  `vaultspec-core vault plan step check`.

The old period-refactor blocker is therefore stale for S20 and S42. It is not
the active blocker for S31 or S38.

## Recommendations

Keep the calculation-engine foundations plan open at 41/43. Close S31 only
after an explicit relation-absence design lands with tests for missing/partial
source filings, correct zero stock carries, and wiring-bug refusals. Close S38
only after live invoice or transaction records carry the OSS classification axes
and M369 calculates from that substrate instead of the no-live-source advisory.

The plan cannot be marked closed yet.

## Codification candidates

No new codification candidates. The remaining blockers are already covered by
the existing no-dormant-source-resolvers, no-silent-under-declaration, and
calculation-source-canonical-mechanism rules; they need implementation design,
not another durable rule.

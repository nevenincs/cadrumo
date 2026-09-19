---
tags:
  - '#audit'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:70453109f6c8c0f45c2b94a9e3a80f5913965ac81dd4abfdfbbc0aa8ede99f9c'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
# `modelo-parity-rollup` audit: `Modelo parity rollup remediation review`

## Scope

This audit closes the accepted schema, evidence, and handoff findings from S19-S24 and records the complete adjudication wave S16-S18. It covers formula/casilla reverse wiring, construct-level legal/source evidence, exact IVA-wallet relation ownership, revision-scoped runtime exclusions, handoff provenance, and real regression tests across the bundled registry. The SOL-deferred M100 2025 semantic rows `0150`, `0613`, and `1481` remain unchanged and remain outside semantic promotion.

## Findings

### modelo-parity-rollup-remediation-review | high | wallet exception was binding-id scoped

The relation/previous-filing validator and handoff classifier now use the exact `(modelo, revision, relation, binding)` coordinate. A second relation reusing the M303 wallet binding is rejected by the actual slot-hygiene gate; it cannot inherit the wallet carve-out.

### modelo-parity-rollup-remediation-review | high | runtime reused the broad wallet binding set

The broad binding-only exception set was removed. Previous-filing exclusions, source-resolution stripping, and staging defaults now derive from the current validated snapshot's exact revision-scoped wallet targets. The M303 runtime behavior remains covered, while a reused identifier outside M303 is retained.

### modelo-parity-rollup-remediation-review | high | construct authority marker was caller-forgeable

Complete construct rows now require a private opaque authority proof created only after `RegistryValidator` succeeds. The public snapshot projection reports complete references as `unvalidated`; only the validated audit fold can emit `grounded` or `inherited` rows.

### modelo-parity-rollup-remediation-review | low | runtime clean-state evidence remains bounded

Handoff applicability, periods, provenance, and ownership are structurally measured, but runtime clean-state remains `unmeasured`. This is an explicit evidence boundary, not a pass claim.

## Recommendations

- Preserve exact relation-coordinate ownership as the sole wallet exception boundary.
- Keep `unvalidated` construct rows visible until a validated authority fold supplies the proof; never infer construct grounding from reference presence alone.
- Keep the three 2025 semantic rows manual/open until their row-specific evidence gates are satisfied and SOL re-adjudicates them.

## Verification

The final no-xdist focused run passed 67 tests across construct evidence, relation closure, handoff inventory/path, cross-dependency contracts, M100 casilla wiring, and the wallet runtime seam. A subsequent focused run passed 26 tests covering semantic boundaries, reverse wiring, drift detection, the real 2025 guardería oracle, and the real 2025 M131 activity oracle. The explicit integration oracle lane passed 3 tests. Targeted Ruff check and format checks passed, targeted basedpyright reported 0 errors, and the bounded diff check passed.

The validating portfolio conformance report measured `registry_validated=true`, 73 modelos, 90 revisions, 0 grounding findings, 0 required model-law coverage gaps, 0 coverage-unmeasured rows, 1,261 reconciled casillas, 61 independently checked casillas, 24 bundled oracle payloads, and zero unattributed or unmatched oracle evidence. The report keeps the annual M100 2025/0A coordinate provisional and `not_yet_measured`; it does not convert that boundary into a parity pass.

The baseline ratchet command `uv run --no-sync python -m dev.registry.conformance audit --check` intentionally remained non-green: `passed=false`, with one vacuity violation and one progress violation because audited locale leaves measured 47,322 versus the 47,376 baseline and translated locale labels measured 25,677 versus the 25,767 baseline in the shared tree. No baseline weakening was accepted or recorded. Repository-wide basedpyright remains outside this remediation proof because shared worktree WIP reports unrelated errors.

The feature-scoped VaultSpec checks are clean: plan findings are empty, `vault check all` has no diagnostics, Markdown diagnostics are empty, body-section diagnostics are empty, frontmatter diagnostics are empty, and execution mapping is complete. The plan has 27/27 closed steps and zero missing execution records.

## SOL adjudication boundary

The third read-only SOL adjudication reviewed the focused S16/S18 oracle addenda, the candidate contract matrix, the accepted five-domain ADR, and the RAG-discovered code paths. It confirms that the addenda are prerequisite evidence, not production authorization.

- S16 `0150`: manual/open. Current persisted fincas state cannot represent the official furniture-amortization and period-allocation facts through the production aggregate. The next gate is a real persisted finca flow, independent expected-value oracle, and accepted repeated-row mapping.
- S17 `0613`: manual/open. No corrected 2025 legal formula, complete input contract, or independent final numeric oracle exists. The next gate is a 2025-specific legal/input contract and final oracle.
- S18 `1481`: manual/open. The new M131 activity oracle proves activity-level capability but not annual M100 transfer, aggregation, or a four-quarter sum. The next gate is a legally grounded 2025 mapping and independent expected M100 value.

The S16/S17/S18 execution records close the plan's adjudication steps only. They explicitly preserve the manual/open semantic outcomes. The oracle code-review audit records that the formal reviewer timed out; no independent reviewer sign-off is claimed, and the local fallback found no HIGH or CRITICAL issue.

## Closure boundary

All 27 plan steps are recorded and closed. All accepted implementation findings are actioned and verified. The generic reverse formula-target invariant and bounded M100 semantic guards remain enforced. Full Modelo 100 2025/0A semantic parity is not claimed: casillas `0150`, `0613`, and `1481` remain manual/open pending their documented source, legal, mapping, and independent-oracle gates.

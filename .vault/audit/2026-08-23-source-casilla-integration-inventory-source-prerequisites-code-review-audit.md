---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:99ddf245b695f74bd3c3e0756b26baf104f298bb9d1356ad55b7edc74d7e9845'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `inventory source prerequisites code review`

## Scope

Formal prerequisite review of the complete inventory source chain before the repository resolver is implemented. The review covered acquisition-cost authority, secure operator ingress, encrypted schema-version-3 persistence, physical-closing authority and continuity, sealed projection semantics, selector grain, confidentiality, determinism, legacy removal, and the exact boundary left for S39.

Review state: **PASS / CLOSED**. The repeat review verified both truth remediations and found no unresolved critical, high, medium, or low finding blocking S39.

## Findings

### inventory-acquisition-prerequisite | pass | complete acquisition cost is authoritative and encrypted

Purchase movements require one strict decomposition covering consideration, attributable costs, non-recoverable IVA, recoverable IVA exclusion, typed completeness evidence, and immutable content digests. The domain-owned purchase factory is the sole arithmetic projection into valuation; application and CLI layers do not reconstruct totals or accept rival legacy purchase authorities. The encrypted repository round trip preserves every component, role, completeness fact, digest, fingerprint, object identity, financial classification, and schema-version-3 boundary while database and WAL canaries remain ciphertext-only.

### inventory-closing-prerequisite | pass | closing authority and continuity are complete and replay safe

The ledger owns one strict closing-authority record containing the evidenced decision, optional physical observation, and immediate prior-closing continuity link. Canonical resolution validates activity and filing-year coordinates, valuation basis, observation and decision fingerprints, decision timing, opening continuity, selected authoritative value, and retained physical-versus-derived conflict. Secure stdin or one-shot descriptor ingress is bounded and value-free on failure. Exact replay is idempotent; divergent decision, observation, digest, or continuity provenance refuses without overwriting the encrypted original.

### inventory-projection-prerequisite | pass | the three outputs are sealed to one canonical source

The 2025 activity-scoped projection derives casilla 0181 from complete capitalized acquisitions and derives mutually exclusive casillas 0177 and 0182 from authoritative closing against continuity-bound opening. It retains a strict runtime source, re-derives every flattened value and provenance field, and binds them through canonical source and projection fingerprints. Correlated substitutions refuse even after checksum reminting; movement and evidence ordering and Decimal scale do not drift identity. The retained ledger is excluded from ordinary serialization, whose canaries expose no evidence reference, content digest, actor, or command.

### inventory-contract-prerequisite | pass | selectors and hard cutover preserve the approved grain

The inventory selector is strict for Modelo 100 ejercicio 2025 and carries exact activity identity. Its three closed operations map only to 0181, 0177, and 0182. Ledger ownership remains one activity and year inside the taxpayer-scoped encrypted profile. The retired authority-shaped `closing_stock` payload and stale inventory use of 0155 are refused; display-only valuation preview is explicitly named `derived_closing_value`.

### inventory-resolver-readiness | pass | S39 has a bounded implementation seam

The prerequisite chain is ready for a repository-backed resolver. S39 may load the canonical encrypted inventory document, select one activity and 2025 coordinate, call the sealed projection, and translate missing, unreadable, incomplete, unsupported-year, continuity, and retained-conflict states into typed diagnostics and source provenance. Readiness and source-mesh disposition correctly remain deferred: S39 must not enroll the source, author registry bindings, persist calculation revisions, or claim connected proof assigned to later steps.

### inventory-source-prerequisites-code-review | pass | repeat review clears the prerequisite chain

The repeat review verified the S163 through S168 production records, the corrected readiness reason, and the corrected connectivity census. No unresolved production-code or truth-record finding blocks S39. Readiness correctly remains false and the census remains `connect_candidate` because resolver, source-mesh, registry-binding, orchestration, calculation-revision, and connected-proof work remains assigned to S39 and later steps.

### inventory-readiness-truth | medium | resolved by truthful deferred-readiness reason

The original finding recorded that `inventory_source_readiness` correctly remained false but falsely described secure persistence as absent. The remediation now acknowledges encrypted schema-version-3 persistence for movements, valuation inputs, complete acquisition cost, and closing authority, while naming only the repository resolver, source-mesh enrollment, registry bindings, calculation orchestration, source-ownership refusal, and connected proof as absent. The focused readiness contract test verifies both the positive persistence statement and removal of the stale claim.

### inventory-census-truth | medium | resolved by exact current grounding and locators

The original finding recorded superseded acquisition, closing-authority, and projection claims. The remediated row retains `connect_candidate`, states that the strict schema-version-3 prerequisite chain and sealed 0177, 0181, and 0182 projection are complete, and confines remaining work to S39 and its downstream connection steps. All five locators re-fetch the repository protocol, readiness function, sealed projection, application closing-authority seam, and secure CLI closing-authority ingress; the owner, deadline, review condition, typed destinations, and bounded follow-up remain explicit.

## Recommendations

Proceed with S39 through the existing encrypted repository factory and canonical projection only. Preserve taxpayer, 2025 filing-year, and activity identity in diagnostics and source identity; use the projection and source fingerprints rather than rebuilding acquisition or closing semantics. Keep inventory deferred until S40, keep orchestration and encrypted calculation-revision persistence in their assigned later steps, and never serialize the projection's excluded runtime source. Treat the two resolved medium entries above as retained review history, not open remediation.

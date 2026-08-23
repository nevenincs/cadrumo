---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:d0e954486c161ee4065445a9ed3c4a976d55ebb742c015c6d891cc55f89e0da9'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `source-casilla-integration` audit: `inventory source prerequisites code review`

## Scope

Formal prerequisite review of the complete inventory source chain before the repository resolver is implemented. The review covered acquisition-cost authority, secure operator ingress, encrypted schema-version-3 persistence, physical-closing authority and continuity, sealed projection semantics, selector grain, confidentiality, determinism, legacy removal, and the exact boundary left for S39.

Review state: **NOT READY / OPEN**. Two medium truth findings block S169 closure and S39 authorization.

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

### inventory-source-prerequisites-code-review | medium | not ready; preliminary pass was superseded

S169 is open and the inventory prerequisite review is NOT READY for S39. The S163 through S168 production records contain no unresolved production-code finding and representative gates are green, but the review discovered two unresolved truth defects in the readiness and connectivity records below. The earlier preliminary pass wording is superseded by these findings and must not be treated as authorization. A repeat review may replace this state with PASS only after both findings are remediated and verified.

### inventory-readiness-truth | medium | readiness reason contradicts encrypted persistence

`inventory_source_readiness` correctly remains false before resolver enrollment, but its reason still claims inventory movements and valuations are not persisted through canonical secure storage. S165 and S167 now prove encrypted schema-version-3 persistence for complete acquisition and closing-authority state. The refusal reason must name the prerequisites that actually remain absent: repository resolver and diagnostics, source-mesh enrollment, registry bindings, orchestration, and connected proof. A stale reason would misdirect operators and S39 readiness tests.

### inventory-census-truth | medium | connectivity census retains superseded blockers and locators

The inventory census row still states that complete acquisition cost and provenance-bearing explicit closing are blocking prerequisites and points to the superseded partial projection surface. S163 through S168 have completed those prerequisites. The row must retain `connect_candidate`, but its grounding, capability locators, bounded follow-up, and review condition must identify the sealed three-output projection and the actual remaining S39 through S42 connection work so the evidence is truthful and re-fetchable.

## Recommendations

Resolve `inventory-readiness-truth` and `inventory-census-truth`, then repeat this prerequisite review before S39 begins. Keep readiness false and the census disposition `connect_candidate`; change only their reasons, grounding, locators, and follow-up to reflect the actual remaining work. After those findings close, proceed through the existing encrypted repository factory and canonical projection only. Preserve taxpayer, 2025 filing-year, and activity identity in diagnostics and source identity; use the projection and source fingerprints rather than rebuilding acquisition or closing semantics. Keep inventory deferred until S40, keep orchestration and encrypted calculation-revision persistence in their assigned later steps, and never serialize the projection's excluded runtime source.

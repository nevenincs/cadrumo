---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:67cae28d8d00dfa9728a2569d84e0b9c22aaaeaf70a880967267a2688e62228c'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# `user-docs-search-consolidation` audit: `Canonical casilla exact-search identity review`

## Scope

Audit the stable `modelo` plus `casilla` exact-search contract against the accepted consolidation ADR, the P06 deterministic enrollment requirements, the registry schema, the unified search record, the Pagefind metadata seam, and the structured browser matcher. Grounding used fresh vaultspec-rag code and vault searches. No tests, builds, browser probes, artifacts, sweeps, reindexing, or deployment were run. The real-authority regression gate and additive canonical-ID source correction are present; the correction is committed as `3127a58c7b`, while unrelated peer hunks remain untouched.

## Findings

### canonical-id-mismatch | medium | Baseline structured matching used display number instead of canonical casilla identity

At the audit baseline, the authoritative `CasillaSearchRecord` identity was `(modelo, casilla_id)`; `number` and `segmento` were display/export metadata. The unified record retained `metadata.casilla_id`, but the Pagefind metadata seam emitted `modelo`, `number`, and `segmento` without `casilla_id`. The browser parser stored the query token as `number`, and `isStructuredCasillaMatch` compared only `meta.number` plus optional `meta.segmento`. That baseline route was a display-number matcher, so IDs that differed from their display number could not be resolved reliably by the plan's stated `modelo <n> casilla <id>` contract.

The committed correction now emits canonical `casilla_id`, preserves the complete query token, and checks canonical identity before the existing display-number/segment fallback. Generated-index and runtime verification remain outstanding.

### display-contract | low | Existing display-number behavior remains an explicit fallback

The implementation intentionally supports the display contract, including segmented `(segmento, number)` disambiguation. That behavior remains useful as a fallback for legacy/display-form records, but it does not replace stable-key lookup.

### peer-ownership | medium | The correction was committed without taking peer WIP

Both affected files contained unrelated uncommitted peer WIP. Only the canonical metadata/parser/matcher additions were staged and committed; the existing UnicodeDecodeError/empty-projection and duplicate-select changes remain dirty and untouched.

## Follow-up evidence

The real-authority gate uses bundled Modelo 121 data where canonical id `decl.ejercicio` differs from display number `ejercicio`. It independently checks the authority row, the production projection, and the unified typed metadata, so the identity/display distinction cannot be hidden by a test fixture that invents both values. LUNA Extra High review found no findings for the gate and source correction. The gate and source correction remain unexecuted/unprobed under the explicit no-tests boundary.

Plan step `P06.S29` tracks the correction and identity-distinct gate. `P06.S24` and `P06.S29` remain open until the authorized gates execute and the built/runtime search contract is verified.

## Recommendations

- Preserve the unrelated peer hunks in the affected files; do not broadly stage or clean them.
- When the test boundary is reopened, execute the real-authority gate alongside the M130/casilla-15 and segmented M200 examples, then verify the built structured route.
- Keep P06.S24 and P06.S29 open until those gates provide evidence at the required scope.

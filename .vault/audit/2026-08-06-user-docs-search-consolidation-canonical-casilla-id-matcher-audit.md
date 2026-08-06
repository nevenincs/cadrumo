---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:8b4522fc94f9c5f9fb94f623bb46b72ff11ff2f2026d61f168ace0df9c936ed8'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# `user-docs-search-consolidation` audit: `Canonical casilla exact-search identity review`

## Scope

Audit the stable `modelo` plus `casilla` exact-search contract against the accepted consolidation ADR, the P06 deterministic enrollment requirements, the registry schema, the unified search record, the Pagefind metadata seam, and the structured browser matcher. Grounding used fresh vaultspec-rag code and vault searches. No tests, builds, browser probes, artifacts, sweeps, reindexing, or deployment were run. A disjoint real-behaviour regression gate was added to `dev/docs/terminology/tests/test_casilla_projection.py`; the peer-owned matcher files remain untouched.

## Findings

### canonical-id-mismatch | medium | Structured matching uses display number instead of canonical casilla identity

The authoritative `CasillaSearchRecord` identity is `(modelo, casilla_id)`; `number` and `segmento` are display/export metadata. The unified record retains `metadata.casilla_id`, but the Pagefind metadata seam currently emits `modelo`, `number`, and `segmento` without `casilla_id`. The browser parser stores the query token as `number`, and `isStructuredCasillaMatch` compares only `meta.number` plus optional `meta.segmento`. Therefore the current route is a display-number matcher, not a canonical-ID matcher. IDs that differ from their display number cannot be resolved reliably by the plan's stated `modelo <n> casilla <id>` contract.

### display-contract | low | Existing display-number behavior is intentional but narrower than the plan wording

The current implementation intentionally supports the display contract, including segmented `(segmento, number)` disambiguation. That behavior is useful and should remain as an explicit fallback, but it does not prove stable-key lookup.

### peer-ownership | medium | The smallest remediation crosses peer-owned files

The minimal correction is to emit `casilla_id` in the Pagefind metadata and compare the full query token against it in the structured matcher, retaining number/segment matching only as an explicitly documented fallback. Both affected files contain unrelated uncommitted peer WIP, so this audit does not edit them.

## Follow-up evidence

The new real-authority gate uses bundled Modelo 121 data where canonical id `decl.ejercicio` differs from display number `ejercicio`. It independently checks the authority row, the production projection, and the unified typed metadata, so the identity/display distinction cannot be hidden by a test fixture that invents both values. LUNA Extra High review found no findings. The gate remains unexecuted under the explicit no-tests boundary.

Plan step `P06.S29` was inserted before `P06.S24` to track the matcher correction and this identity-distinct gate. `P06.S24` and `P06.S29` remain open until the source correction is applied and the relevant gates are executed.

## Recommendations

- Assign the canonical-ID metadata and matcher correction to the owners of the current Pagefind injector and shared controller WIP.
- Retain the new real-behaviour gate alongside the existing M130/casilla-15 and segmented M200 examples.
- Keep P06.S24 and P06.S29 open until the corrected route is verified under the authorized test boundary.

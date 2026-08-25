---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:4be29448610a973b4b24a0bbdbf94538a446d7f40b5d7b63cfbe71e01d82d797'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
---

# `cli-action-envelope-hardening` audit: `S06 operator surface identity reconciliation review`

## Scope

Reviewed `src/cadrumo/application/operator_surface/_manifest.py` and `src/cadrumo/application/operator_surface/tests/test_manifest_reconciliation.py` against the accepted action-envelope ADR, plan Step `W01.P02.S06`, research, and fixed-point reference. The review covered application-boundary placement, stable identity and provenance, duplicate, unmatched, and ambiguous joins, canonical versus alias mounted-family resolution, explicit exclusions, policy versus MCP contradictions, and the pure tests' fail-closed strength. Semantic RAG preceded source discovery. The new reconciliation tests plus existing operator-surface contract tests passed twenty-eight tests in 19.64 seconds; Ruff and focused basedpyright were clean.

## Findings

### root-callback-live-row-gap | high | The reconciliation model cannot represent the root status callback

S05 establishes `root.status` as a callback whose canonical CLI path is the empty tuple, and the ADR requires callback identities in the exact live join. `LiveLeafInventoryRow.canonical_cli_path` nevertheless declares `min_length=1`. A direct construction of the required `root.status` row raised Pydantic's `too_short` validation error. The pure test inventory contains only a three-token command leaf, so the green suite does not exercise the callback denominator and S06 cannot yet reconcile all live schema identities.

### orphan-mounted-family-gap | high | Unmatched mounted-family declarations are silently ignored

Subject-keyed inventories reject orphan rows, but `_index_families` checks only duplicate family identities. It never reconciles the indexed family set back to canonical live-leaf families. Adding an extra `app ghost` mounted-family declaration to the otherwise complete test inventory returned a successful report containing only `app.ledger.list`; the orphan family vanished from the result without an exclusion or error. This breaks the ADR's symmetric exact-join requirement and allows the operator contract to advertise a mounted family with no live identity.

### blank-provenance-admission | medium | Result and input schema rows accept whitespace-only evidence

`ResultSchemaInventoryRow` and `InputSchemaInventoryRow` use `Field(min_length=1)` for provenance but do not apply the non-blank validators used by the other inventory models. Direct construction with `provenance=" "` succeeded for both. The join therefore reports those surfaces as accounted for even though their claimed evidence source is blank; the existing strict-model test exercises tuple coercion only and does not prove provenance completeness.

### root-callback-live-row-remediation | low | Resolved with a root-status-only empty path and full reconciliation proof

`LiveLeafInventoryRow` now admits an empty canonical path only when the stable subject identity is `root.status`; an ordinary command with an empty path fails validation. The new reconciliation test carries real typed rows for every surface, supplies the explicit mounted-family exclusion required for the root callback, and proves the resulting leaf retains the empty path and no mounted family.

### orphan-mounted-family-remediation | low | Resolved by a symmetric reached-family check

The reconciliation now derives mounted-family identities from every canonical live path and rejects each declaration absent from that reached set. The regression adds `app ghost`, asserts the failure, and verifies that both the orphan identity and its provenance appear in the diagnostic.

### blank-provenance-remediation | low | Resolved by shared non-blank evidence validation

A single inventory-text validator now rejects whitespace-only identity, schema-name, provenance, and evidence fields on the result and input rows. Negative model tests cover both previously permissive provenance fields. The remediated reconciliation and existing operator-surface contract tests passed thirty tests in 19.57 seconds; Ruff passed and focused basedpyright reported zero errors, zero warnings, and zero notes.

## Recommendations

- For `root-callback-live-row-gap`, admit the empty canonical path only for the typed root callback identity and add a root-status reconciliation case that still rejects empty paths for ordinary command leaves.
- For `orphan-mounted-family-gap`, symmetrically compare mounted-family identities with the families reached by canonical live paths and fail every unmatched declaration unless the architecture defines a separate typed family-level exclusion.
- For `blank-provenance-admission`, apply the shared non-blank text rule to every provenance and schema-name evidence field and add whitespace-negative model tests.

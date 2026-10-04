---
tags:
  - '#plan'
  - '#reconciliation-mechanism-hardening'
date: '2026-10-04'
tier: L1
related:
  - '[[2026-06-10-live-justificante-reconcile-adr]]'
  - '[[2026-07-01-reconcile-value-comparison-adr]]'
  - '[[2026-07-25-reconcile-evidence-relocation-adr]]'
  - '[[2026-09-07-tuimodelo-reconcile-verify-adr]]'
  - '[[2026-09-17-filing-chain-reconciliation-adr]]'
  - '[[2026-07-01-verification-reconcile-when-present-adr]]'
  - '[[2026-06-19-iva-compensation-override-cli-adr]]'
  - '[[2026-06-21-m303-carry-reconciliation-adr]]'
  - '[[2026-10-04-live-reconciliation-repair-audit]]'
modified: '2026-10-04'
body_schema: body-v2
body_hash: 'sha256:5f73852e69101ea3150c7e2005bf0a2142edf376d77c8009d52963cbfcf515eb'
---

# Reconciliation mechanism hardening

## Description

Approved 2026-10-04

The user explicitly directed iterating through justificante, declaration, working calculation, filing chain, cross-model and IVA compensation mechanisms with the same root-cause repair and verification rigor as the completed live reconciliation repair. Reuse that live acceptance and captured encrypted evidence. Existing decisions govern identity and amount comparison with disclosed gaps, encrypted immutable history, exact profile and period custody, official versus pending-local filing authority, registry-owned comparison scopes and tolerances, and wallet authority with audited overrides. This is corrective execution within those contracts, not a new ledger or new tax-policy authority. Any uncovered costly semantic choice is grounded and recorded before dependent implementation. Preserve all unrelated registry, export and quality edits.

## Steps

- [x] `S05` - Harden justificante and declaration comparisons with explicit saved-revision provenance and truthful coverage through both frontends; `src/cadrumo/application/modelo reconciliation records operations and entrypoints reconciliation CLI tests`.
- [x] `S01` - Isolate working-calculation divergence checks to official evidence under the pinned authority and verify absence and drift semantics; `src/cadrumo/application/modelo/pulled_filing_reconcile.py verification_model_findings.py and focused encrypted persistence tests`.
- [x] `S02` - Verify and repair filing-chain confirmation contradiction replay and evidence-enrichment transitions; `src/cadrumo/application/modelo/filing_chain_reconciliation.py live persistence integration and chain tests`.
- [x] `S03` - Verify and repair registry-owned cross-model comparison selection coverage and visible findings; `src/cadrumo/application/modelo/_m303_m349_reconcile.py verification integration and cross-model tests`.
- [ ] `S04` - Verify and repair IVA compensation authority refresh override scope and carry decisions; `src/cadrumo/application/calculations/iva_wallet_reconciliation.py domain/iva_compensation and persistence/CLI tests`.
- [ ] `S06` - Verify integrated CLI and TUI mechanisms with retained real evidence and complete independent review; `src/cadrumo/entrypoints CLI TUI projections tests and var/reconciliation-check-20261004 redacted acceptance evidence`.

## Parallelization

Lead owns S02 filing-chain work, S06 integrated CLI/TUI acceptance, shared checks, vault edits and all commits. receipt_fix owns S05 explicit justificante/declaration comparison and revision provenance, then S04 IVA compensation. mirror_fix owns S01 working-calculation official-evidence isolation, then S03 cross-model consistency. review_repairs independently audits wallet/cross-mechanism risks and reviews integrated changes without source writes. Workers have disjoint ownership, preserve others edits and route shared contract changes to the lead before editing. Reuse existing live test profile and fixed authority; no concurrent live browser tasks.

## Verification

For each mechanism establish compared operands, exact revision/period/profile provenance, applicability and comparison coverage, tolerance, missing/stale/conflicting evidence behavior, persistence/event atomicity, repeat behavior and operator-visible outcome. Exercise matches, drift, missing evidence, wrong scope, stale data and pending-local versus official evidence with real application and encrypted adapter paths; run actual CLI and TUI integration where supported. Use the retained real 2024 Q1 filing for read-only acceptance and synthetic encrypted fixtures for scenarios requiring alternate tax facts or filing transitions. No AEAT submission or payment. Preserve local-versus-remote authority, current-versus-historical status and incomplete-versus-match distinctions. Scoped style, format, type and import checks accompany each commit; reuse applicable prior results and explicitly disclose unrelated global gate failures. Independent review closes each mechanism and final integration.

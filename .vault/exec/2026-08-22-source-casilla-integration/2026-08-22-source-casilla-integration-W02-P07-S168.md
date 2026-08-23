---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:0068a1f0b299aab253c8e0a23f9340b906bbfe513a07a92b80b421fb42173a47'
step_id: 'S168'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# produce the strict complete 0177, 0181, and 0182 inventory domain projection

## Scope

- `src/cadrumo/domain/contribuyente/inventory`

## Description

- Add a strict source-owned 2025 inventory projection for casillas 0177, 0181, and 0182.
- Reuse the canonical closing-authority resolver and retained continuity and conflict provenance.
- Derive purchase totals and fingerprints from canonically ordered complete acquisition-cost movements.
- Refuse missing, unreadable, out-of-period, inconsistent, and caller-overridden projection state.
- Add increase, decrease, equality, authority-selection, conflict, ordering, continuity, and forgery tests.

## Outcome

The inventory ledger now produces one complete activity-scoped projection. Casilla 0181 equals the admitted complete acquisition cost; casillas 0177 and 0182 are the mutually exclusive positive split of authoritative closing against opening. The result carries the selected authority, decision, continuity, physical observation, conflict, and acquisition fingerprints needed by the downstream resolver without accepting caller-authored outputs.

The projection revalidates the persisted ledger, requires the ledger-owned closing-authority record, calls the canonical authority resolver, and refuses incomplete purchase acquisition facts. It retains the canonical source only as excluded runtime state, re-derives every flattened field during validation, and emits safe source and envelope fingerprints without serializing financial or evidence facts. Semantically equal movement, evidence, and Decimal representations produce identical provenance. Nonzero acquisition totals require a nonempty unique fingerprint set.

Verification completed with 53 passing inventory-domain tests, clean Ruff and type-checker runs, and two independent final reviews reporting zero findings.

## Notes

Semantic discovery was unavailable because the installed `vaultspec-rag` client was version 0.4.1 while the running service was 0.4.2; targeted ADR and source inspection supplied the required grounding. Review found and resolved result-provenance forgery gaps, correlated checksum reminting, runtime-source serialization, untyped and unvalidated construction, movement and evidence ordering drift, Decimal-scale drift, an accidental closing-decision field collision, divergent physical-value conflict omission, and empty or duplicate acquisition fingerprints for nonzero totals.

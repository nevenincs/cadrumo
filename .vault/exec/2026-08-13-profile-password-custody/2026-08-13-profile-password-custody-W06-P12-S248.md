---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:39ae528af118e63ba09df88198b6d962157e6f78a27b2bf1d780c6f48ee25c38'
step_id: 'S248'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Reconcile Modelo 303 2026 and Modelo 390 2022-2025 semantic-role constraint signatures against their official record-design authority so the shared-role validator passes without weakening compatibility checks

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303/ and src/cadrumo/_data/registry/aeat/modelos/390/ and src/cadrumo/domain/calculations/registry/tests/`

## Description

- Grounded the mismatch through Vaultspec RAG, the accepted registry drift decision, calculation-grounding rules, the exact AEAT record-design source registrations, and the Modelo 390 2021 applicability-grade authority reference.
- Split Modelo 303's five 2026 four-byte CNAE roles from their historical three-byte roles while retaining the stable continuidad identities and explicit repurposed evolutions.
- Split Modelo 390's 2021 parser-only informational compensation observations from the 2022-and-later bound, non-negative filing roles while retaining stable continuidad identities and the explicit 2021-to-2022 repurposed evolution.
- Preserved the semantic-role compatibility validator and added authority-signature and validator-bite proof.

## Outcome

Complete. The production registry and tests landed concurrently in commit `5362ab6539`; this closure records the independently rerun evidence and formal PASS review without claiming the unrelated Modelo 369 content in that commit.

## Notes

- Focused M303/M390, semantic-role and cross-revision proof: `160 passed`.
- Full committed catalogue and legal-grounding validation: `36 passed, 1 failed`; the single failure is unrelated production source-catalogue debt for `google.calc_sheets.pull.relation_source_refs_valid` in `cadrumo/adapters/outbound/google/_calc_sheets_pull.py`.
- Focused Ruff passed.
- Focused ty reported one pre-existing diagnostic in unchanged `test_m390_temporal_epochs.py:129`, whose helper accepts `object` but iterates it.
- Formal `vaultspec-code-reviewer` verdict: PASS with no findings; it confirmed official-source grounding, stable continuity identities, complete target-owned evolutions, no validator weakening, and anti-tautology coverage.

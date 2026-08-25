---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:3039cd7b68847ac87aa1b1379cfdd6fe4cbe047251566fef4e932c0af032b7ba'
step_id: 'S44'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---
# Acquire and hash-pin exact official Modelo 182 design eras and amendment authority

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/182/`
- `src/cadrumo/_data/registry/aeat/legal/modelo-182.toml`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Reconcile the hash-pinned 2024 and 2025 AEAT designs with their exact legal applicability evidence.
- Select only the 2025 design era, which has the existing canonical BOE amendment and first-application provision.
- Refuse unevidenced 2007--2023, 2024, and 2026-onward selector years without promoting grade or adding an export layout.

## Outcome

Modelo 182 now has only a `2025` applicability-grade revision. It cites the exact 2025 AEAT design, the Modelo-182 amendment in Orden HAC/1430/2025 article 2, and the existing canonical final provision which applies the change first to exercise 2025. The 2024 PDF remains hash-pinned catalogue evidence but is not selected because no exact legal approval/amendment provision was established. No filing or export capability was added.

## Notes

- The exact registry load proof and the export-exemption selection test passed.
- The full legal-reference pytest worker did not return within the bounded gate; no broad gate was used.

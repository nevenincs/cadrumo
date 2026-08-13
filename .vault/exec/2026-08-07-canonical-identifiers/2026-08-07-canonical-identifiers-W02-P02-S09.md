---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:b294b2c2ca23391beb4395da6aae5f7750c9ce80f0233692417bbb5163d217fb'
step_id: 'S09'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# Discriminate IVA-compensation provenance from AEAT register status

## Scope

- `src/cadrumo/core/_iva_compensation_provenance.py`
- `src/cadrumo/domain/iva_compensation/_carry_forward.py`
- `src/cadrumo/application/calculations/_iva_compensation_history.py`
- `src/cadrumo/application/calculations/_iva_compensation_annual_partition.py`
- `src/cadrumo/application/modelo/_filed_revision_observation.py`
- `src/cadrumo/application/live/_filed_observation_persistence.py`
- `src/cadrumo/entrypoints/cli/_modelo_iva_wallet_cli.py`

## Description

- Re-ground the five supplying paths and their distinction from AEAT register status through semantic discovery and the accepted amendment.
- Re-read the landed implementation and its consumers, confirming the closed core enum, required state field, pair validator, direct canonical imports, and separate wallet fields.
- Correct the two remaining source descriptions that could imply retired synthetic status or record-id provenance.
- Exercise the encrypted provenance round trip and the focused producer, persistence, and CLI behavior suites.
- Correct the seed CLI integration expectations to the required provenance and register-status fields.
- Run focused format, lint, type, residue, and formal-review gates.

## Outcome

`IvaCompensationStateProvenance` is the sole closed five-member carrier for the supplying path. `IvaCompensationPeriodState` requires it, permits an `expediente_id` only for AEAT capture, and carries register status only for that same AEAT-capture path. The five producers assign the exact member explicitly; wallet output projects `provenance` and `register_status` as distinct fields. No seeded or correction status marker remains as state meaning.

The existing implementation originated in `199d9260ebab66e790be5c55df3e2d180204ba1f`; this step records its complete live verification and the removal of the last displaced descriptions and test expectations. The seed CLI integration suite passes all 20 cases, the focused selected S09 suite passes 35 cases, and formal review found no blocking issue.

## Notes

S10 remains responsible for non-capture persistence population control, and S65 remains responsible for whole-corpus migration evidence. Neither is closed by this scoped step.

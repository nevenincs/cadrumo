---
tags:
  - '#exec'
  - '#censo-operator-manual-enrolment'
date: '2026-07-11'
modified: '2026-07-17'
body_hash: 'sha256:19c43aba8aa302056ce7b3838efcd43011cc96b6d23f82a5584a1fcb8af44ffd'
step_id: 'S04'
related:
  - "[[2026-07-11-censo-operator-manual-enrolment-plan]]"
---

# Remove the dead censo pull/compare/apply locale key subtree through the locales CLI (keeping the operator-manual advisory strings) and confirm scaffold --check is clean

## Scope

- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Description

- Removed the 12 orphaned censo locale keys across `en`, `es`, `ca`, `hu` through the locales CLI (`python -m aeat.locales remove`): the retired verb help/subgroup keys, `cli.operator_surface.help.config.profile_censo`, the portal `entries.portal_mis_datos_censales.label` / `.purpose`, the four `errors.censo.*` snapshot/apply/no-censo keys, `errors.fail.fail_sede_censo_parse`, and the three `errors.refused.censo_*` keys.
- Kept the operator-facing advisory strings that survive the retirement (`cli.overview.warning.censo_enrolment_unverified` and `errors.censo.bucket_id_blank`).

## Outcome

`python -m aeat.locales scaffold --check` reports `extra=0` for all four catalogues; the diff is pure removals with no reflow (targeted `remove`, not `scaffold`, was used after an initial `scaffold` reflowed the whole file cosmetically and was reverted from HEAD).

## Notes

`scaffold --check` reports a PRE-EXISTING `missing=30` drift per locale (keys under `application.modelo.findings.cross_period_*`, `cli.app.modelo.verification_report.*`, `formula_operation_*`) owned by other in-flight campaigns (m210 / cross-period / verification). Zero of the 30 are censo-related; per full-tree-gate-must-distinguish-owner this is peer drift, not this campaign's surface, and is left untouched.

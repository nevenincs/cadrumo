---
tags:
  - '#exec'
  - '#iva-compensation-override-cli'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:c944f1cbf6918a97ab1e54cde8bacfae79dd70dd9f95040fcdcbff3dfdd675a0'
step_id: 'S06'
related:
  - "[[2026-06-19-iva-compensation-override-cli-plan]]"
---

# Author override help/confirm/error locale leaves for en es ca hu via python -m aeat.locales set, then scaffold --check clean

## Scope

- `src/aeat/locales`

## Description

- Verify the override help, confirm, and error locale leaves the verb renders exist and are genuinely translated across all four target catalogues: `override_amount_help`, `override_confirm_help`, `override_confirm_required`, `override_evidence_locator_help`, `override_evidence_locator_required`, `override_filing_year_help`, `override_help`, `override_period_help`, `override_reason_help`, `override_reason_required` under the iva-wallet override verb group.
- Confirm the four named safety leaves (`override_confirm_help`, `override_confirm_required`, `override_reason_help`, `override_reason_required`) carry real prose in `en`, `es`, `ca`, and `hu` (no placeholder equalling the key).
- Run the locale CLI drift and health gates and the locale parity plus honesty gates to prove the catalogues are structurally sound.

## Outcome

- `python -m aeat.locales scaffold --check` and `python -m aeat.locales audit` both report `ok` for `ca.yml`, `en.yml`, `es.yml`, `hu.yml` (zero codebase-to-locale drift, zero missing keys, inter-locale parity intact).
- The locale parity and honesty gates pass (twenty-two tests), confirming every override leaf has key parity across the four locales and none regresses the untranslated-string honesty ceiling.
- The override verb group renders localized help, mandatory-confirm refusal, and mandatory-reason refusal in all four languages; the operator-facing surface for the verb is complete.

## Notes

- The override leaves were already present and fully translated at `HEAD` across all four catalogues (four named safety leaves confirmed in each of `en`, `es`, `ca`, `hu`), authored through the `aeat.locales` CLI in earlier commits of this feature. No new leaf authoring was required; this Step is a verification close.
- The locale `.yml` files carry unrelated uncommitted peer working-tree modifications that do not touch the override leaves; they were left untouched. This Step's commit carries only the exec record and the plan checkbox, per explicit-pathspec discipline.

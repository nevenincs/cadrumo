---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:2f7bf0daa85857275e80d7e9f9976445e65e9219ccdaeb2148b6c539a28a4153'
step_id: 'S262'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Reconcile all four production catalogues with current source and registry revision ownership, including Modelo 038, Modelo 220, Modelo 763, missing and orphaned keys, then rerun audit, drift, completeness, and every nitpicky build

## Scope

- `locales/ and dev/locales/ and docs/locales/`

## Description

Trace the shared runtime and documentation catalogue authorities, reconcile current source keys and Modelo revision moves through the canonical locale tooling, synchronize gettext once, and prove catalogue integrity plus localized rendering without an English fallback or a parallel locale owner.

Normalize authored multiline casilla display text only at the generated raw-HTML boundary so wrapped translations cannot break RST indentation, and retain the selected build language unchanged apart from whitespace.

## Outcome

The S233 state of 48 missing keys, 20 extras, and two revision moves per runtime locale is reconciled. Concurrent registry work landed Modelo 038, Modelo 220, and Modelo 763 ownership; the remaining six missing and eight stale keys per locale were supplied with real English, Spanish, Catalan, and Hungarian text through one batch and removed through one canonical scaffold. Current `scaffold --check` and `audit` report all four catalogues clean.

The documentation i18n tool ran once. Two Hungarian machine-text dashes were rephrased and three retired environment-reference catalogues were removed. Unit localization checks pass 10/10 and gettext source-drift checks pass 3/3. All four localized nitpicky builds pass after the casilla renderer learned to collapse catalogue line wrapping inside generated HTML; the regression suite passes 32/32, Ruff is clean, and ty is clean.

Formal review approved the change with no findings. The main nitpicky build remains red with 364 API cross-reference warnings unrelated to localization, including current `CasillaId`, `TaxIdIdentityToken`, `FormField`, `ManagerAction`, and `StatusPageData` facade/docstring ownership. S262 therefore remains open under the explicit all-lanes-green closure condition.

## Notes

Generated CLI references were not edited. No English fallback or registry-local catalogue was introduced. Runtime catalogue changes were captured amid concurrent locale and sharding commits; docs synchronization landed in `1ad8509ea4`, and the raw-HTML renderer plus regression landed amid the concurrent quality commit `b4c58f41a7`. This record claims only S262's reviewed portions of those commits.

The main API build was rerun twice after localized stabilization and remained at exactly 364 warnings. Its correction belongs to the public API and documentation ownership lane, not to the runtime or gettext catalogues.

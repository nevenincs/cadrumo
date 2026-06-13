---
tags:
  - '#exec'
  - '#non-resident-axis'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S02'
related:
  - '[[2026-05-27-non-resident-axis-S01]]'
---

# `non-resident-axis` `S02`

P0 hotfix: restored `aeat config *` CLI surface broken by three missing `_SETUP_OPTION_INFOS` entries, added CCAA visible_when guard, fixed EL->GR ISO code, and added module-level parity assert.

- Modified: `src/aeat/application/wizard/_commands.py`
- Modified: `src/aeat/application/wizard/_catalogue.py`
- Modified: `src/aeat/domain/profile/_renta_codes.py`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`

## Description

Three catalogue question IDs had no corresponding `typer.Option` entry in `_SETUP_OPTION_INFOS`: `situacion-familiar` (added by #176), `irpf-special-regime`, and `irpf-special-regime-start-date` (both added by #197). The `_python_parameter` loop raises `KeyError` with the missing key name on every import of the wizard commands module, bricking the entire `aeat config` subtree.

Changes made:

Added `_irpf_personal_choice_values()` helper and two module-level constants (`_IRPF_SPECIAL_REGIME_CHOICE_VALUES`, `_SITUACION_FAMILIAR_CHOICE_VALUES`) following the established pattern of `_taxpayer_type_choice_values()`. Added three missing `typer.Option` entries to `_SETUP_OPTION_INFOS`: `situacion-familiar` (SELECT with SituacionFamiliar enum choices), `irpf-special-regime` (SELECT with IrpfSpecialRegime choices), `irpf-special-regime-start-date` (TEXT). Added a module-level parity assert that fires at import time if catalogue and dict ever drift again.

Added `visible_when=WizardCondition(question_id="fiscal-residency", equals=FiscalResidency.RESIDENT_IRPF.value)` to the `tax-residence-ccaa` catalogue question. IRNR non-residents have no CCAA residencia fiscal; the prior code silently defaulted them to "madrid".

Replaced `"EL"` (Eurostat code) with `"GR"` (ISO 3166-1 alpha-2) in `UE_EEA_COUNTRY_CODES` in `_renta_codes.py`.

Added `wizard.setup.flags.irpf-special-regime.help`, `wizard.setup.flags.irpf-special-regime-start-date.help`, and `wizard.setup.flags.situacion-familiar.help` entries to all four locale files. Added `wizard.setup.taxpayer.situacion-familiar.*` block to `es.yml` (was missing despite being in en/ca/hu). Added `wizard.setup.residence.tax-residence-ccaa.prompt` and `wizard.setup.flags.tax-residence-ccaa.help` to `hu.yml`.

## Tests

Module import smoke: `import aeat.entrypoints.cli._config` returns without KeyError.

Parity assert: `_SETUP_CATALOGUE_IDS == frozenset(_SETUP_OPTION_INFOS)` is True (57 == 57).

`uv run --no-sync aeat config --help` exits 0 and shows new flags `--situacion-familiar`, `--irpf-special-regime`, `--irpf-special-regime-start-date`.

`uv run --no-sync aeat --version` exits 0.

Wizard translation audit: 12 pre-existing keys resolved; no new regressions introduced from this fix.

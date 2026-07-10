---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-08'
step_id: 'S01'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# declare the closed ProrrataRegime (general | especial | none) and ProrrataProvisionalProvenance (carried_prior_definitiva | aeat_autorizada | inicio_actividad) StrEnums in core per the closed-value-set-in-core rule, Spanish stems

## Scope

- `src/aeat/core/__init__.py`

## Description

- Declare the closed `ProrrataRegisterRegime` StrEnum (`GENERAL`, `ESPECIAL`, `NINGUNA`) in `src/aeat/core/_prorrata_register.py`, the register's in-force regime axis.
- Declare the closed `ProrrataProvisionalProvenance` StrEnum (`CARRIED_PRIOR_DEFINITIVA`, `AEAT_AUTORIZADA`, `INICIO_ACTIVIDAD`) recording the LIVA art. 105 source of the provisional percentage.
- Re-export both enums through the `aeat.core` top-level facade (import plus `__all__`).

## Outcome

Both enums import cleanly from `aeat.core`; Spanish-stemmed values (`general`/`especial`/`ninguna`, `carried_prior_definitiva`/`aeat_autorizada`/`inicio_actividad`). `ruff`, `ruff format`, and `ty` clean; core facade collect-only clean.

## Notes

Naming deviation from the plan's literal `ProrrataRegime (general | especial | none)`: the compute substrate already declares a `ProrrataRegime` StrEnum (`general | especial`) in `src/aeat/domain/iva/_prorrata.py`, used by `validate_prorrata_reference` via `ProrrataRegime(parts[3])`. Adding a `NINGUNA`/`none` member to that shared enum would loosen the substrate's reference-parsing grammar to accept `ninguna`, a behaviour change the ADR forbids ("substrate is consumed, not re-opened"). A duplicate `ProrrataRegime` symbol across `core` and `domain.iva` was also rejected (grep/import trap). The register therefore owns a distinct `ProrrataRegisterRegime` symbol whose name is not a substring of `ProrrataRegime`. Surfaced to the wave lead for review.

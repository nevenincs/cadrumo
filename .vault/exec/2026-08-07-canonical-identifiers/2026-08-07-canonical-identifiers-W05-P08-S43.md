---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:c4b92c45ccd03e31d487481ec798f33c31496a57969e7f8d8fd456265c465899'
step_id: 'S43'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# check whether M210's `official_tipo_renta_code` catalogue is already enumerated in registry TOML

## Scope

- `src/cadrumo/domain/transactions/_m210_income_classification.py`
- `src/cadrumo/core/_irnr.py`

## Description

- Read `M210IncomeClassification.official_tipo_renta_code` and its
  `@field_validator` before searching anywhere else: the validator already
  checks membership in `M210_TIPO_RENTA_CODE_PROJECTION`, imported from
  `core`, not declared locally — a strong signal the catalogue already
  lives centrally.
- Traced `M210_TIPO_RENTA_CODE_PROJECTION` to `core/_irnr.py`: it is
  derived from `OFFICIAL_M210_TIPO_RENTA_CODES`, a tuple of
  `OfficialTipoRentaCode(code, concept, rate_legal_ref, grounding_tier)`
  entries, one per official two-digit HOJA INFORMATIVA 210 code, each
  citing the TRLIRNR legal ref that grounds its rate.
- Confirmed the registry-TOML side directly: `grep`ped for the parameter
  id the module's own docstring names
  (`m210-tipo-renta-code-2025`) and found it at
  `_data/registry/aeat/modelos/210/revisions/2025/parameters/`. The
  catalogue is declared in BOTH places by design, not because Python
  duplicates the registry: `core/_irnr.py`'s own docstring states a
  registry-build parity gate,
  `validate_m210_tipo_renta_code_projection_parity`, cross-checks the two
  in both directions — a registry-declared code without a Python
  projection, or a projected code the registry does not declare, fails
  the build. This is the established "closed axis lives in `core/`,
  hydrated at/cross-checked against the registry boundary" pattern the
  campaign's own typed-constant-axis rule asks for, already fully built.

## Outcome

**CHECK ANSWERED: YES**, already enumerated in registry TOML
(`m210-tipo-renta-code-2025`), already projected into a typed `core/`
closed axis (`OFFICIAL_M210_TIPO_RENTA_CODES` /
`M210_TIPO_RENTA_CODE_PROJECTION` / `TipoRentaIrnr`), and already
cross-checked by a dedicated build-time parity gate in both directions.
This row is purely investigative per its own text ("check whether...");
no further declaration or retype is needed for the M210 catalogue itself,
and none was made. The row's answer feeds `W05.P08.S44`, which covers
M720 only (`M720OperationKindCode` / `M720AssetClassCode`) — M210 needed
no equivalent work because it already has the pattern S44 is about to
build for M720.

No files changed; this is a documented finding, not a code change.

## Notes

One narrower, adjacent question this row's text does NOT ask, recorded so
it is not silently conflated with the answered one:
`official_tipo_renta_code` itself (the raw two-digit code, e.g. `"04"`)
is validated by set-membership against `M210_TIPO_RENTA_CODE_PROJECTION`
but stays a bare `str` field — it is NOT the same axis as
`TipoRentaIrnr` (the many-to-one rate CONCEPT the code folds into,
already a `StrEnum`). Whether the raw code itself should become its own
closed `StrEnum` distinct from `TipoRentaIrnr` is a real question this
row's literal scope does not cover and this record does not resolve.

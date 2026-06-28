---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W09.P41.S194 Code Review

Commit: `24132efb9` — #194 causante_ccaa axis + foral guard + pre-existing test fixes

## Status: APPROVE WITH FOLLOW-UP

No CRITICAL or HIGH safety violations. Two MEDIUM findings require follow-up steps.

---

## Gate Summary

| Gate | Result | Notes |
|------|--------|-------|
| G1 no naked env reads | PASS | No `os.environ`/`os.getenv` in diff |
| G2 typed pydantic at boundaries | PASS | `WorkUnitPayload.causante_ccaa: str \| None` is `CCAA.value` string; consistent with other `str` payload fields |
| G3 `tr()` for user messages | PASS | All new help strings, error messages, and suggestions go through `tr()` with locale keys |
| G4 locale scaffold parity | PASS | `causante_ccaa_help` and 5 new keys present in all four locales (es/en/ca/hu) |
| G5 no shims / foral reuse | PASS | `parse_tax_region` + `ForalRegimeError` imported from `aeat.domain.profile`; `_FORAL_ALIASES` frozenset is the single authority; no parallel implementation |
| G6 no tautological tests | PASS | Foral tests assert `"foral"`, `"Concierto"`, `"Ley 12/2002"` phrases the stub guard cannot produce; roundtrip uses real encrypted repo |

---

## Critical Question Answers

**Q1. causante_ccaa placement.**
`causante_ccaa: CCAA | None = None` is added to `WorkUnit` (domain layer, `src/aeat/domain/modelos/_work_unit.py`), not to any profile model. This is correct — it is per-filing context, not declarant-profile state. The field is explicitly documented as not part of the content-addressing key. Parallel to the Beckham `start_date` pattern.

**Q2. Foral guard reuse.**
`parse_tax_region` from `aeat.domain.profile` is called before `_guard_stub_modelo`. `parse_tax_region` internally checks `_FORAL_ALIASES` and raises `ForalRegimeError` for País Vasco / Navarra. No parallel frozenset or alias table added. G5 clean.

**Q3. CLI flag wiring.**
`--causante-ccaa` is registered as a `typer.Option` on `work_create` in `src/aeat/entrypoints/cli/_modelo.py`. It flows through `create_work_unit` in `src/aeat/application/modelo/_actions.py` and lands on `WorkUnit.causante_ccaa`. Surfaced in both `WorkUnitPayload` (JSON) and `_work_unit_lines` (text). Correct.

**Q4. Pre-existing test fixes.**
Fourteen `test_work_unit.py` failures fixed: M303 period `Q1→1T`, M303 `revision_id "rev"→"2009-y-siguientes"`, M130 `revision_id "rev"→"2019-y-siguientes"`. One structural test (`test_no_parallel_work_unit_storage_namespace`) fixed to exclude `_namespace_registry.py` (legitimate namespace table, not a shadow store).

**Q5. `_SETUP_OPTION_INFOS` regression.**
Not touched. `_SETUP_OPTION_INFOS` lives in `src/aeat/application/wizard/_commands.py` and is unmodified. No regression.

**Q6. Locale parity.**
All four locale files (es/en/ca/hu) contain `causante_ccaa_help`, `meses_trabajo_con_hijo_menor_3_help`, `meses_trabajo_hijo_bad_format`, `meses_trabajo_hijo_not_integer`, `meses_trabajo_hijo_out_of_range`, `deduccion_maternidad_casilla_not_found` (6 keys). Parity confirmed.

**Q7. Anti-tautology coverage.**
Foral-negative paths: `test_causante_ccaa_foral_refused_before_stub_guard` (pais_vasco) and `test_causante_ccaa_navarra_foral_refused` (navarra) — both assert legal-phrase markers (`"foral"`, `"Concierto"`, `"Ley 12/2002"`, `"Convenio"`, `"Ley 28/1990"`) the stub guard cannot produce. Anti-tautology is adequate for the refusal path. The AEAT-positive path (`--causante-ccaa madrid` → no error, work unit created) has domain coverage via `test_causante_ccaa_roundtrips_through_repository` but no CLI-level positive-path assertion. See MEDIUM finding below.

---

## Findings

### SCOPE-001 | MEDIUM | Out-of-scope `deduccion_maternidad` helpers bundled into #194

`_resolve_deduccion_maternidad_casilla_id`, `_parse_meses_trabajo_hijo_spec`, `_compute_deduccion_maternidad_0611`, and the `--meses-trabajo-con-hijo-menor-3` option on `work_calculate` are not part of the #194 causante_ccaa axis mandate. They are added in this commit without a corresponding plan step. The `test_deduccion_maternidad_0611.py` test file and locale keys are also new. These helpers appear to belong to a follow-up Mateo round-14 Yara audit action. The implementation is internally consistent and tested, but the scope bundling makes the commit difficult to audit against a single plan step and risks orphaned state if the feature is rolled back. A follow-up plan step should be created to formally register this work.

### CLI-002 | MEDIUM | Missing CLI-level positive routing test for `--causante-ccaa madrid`

The two foral-refusal tests cover the `parse_tax_region` → `ForalRegimeError` branch. The success path (non-foral CCAA supplied → `work_create` proceeds, work unit created with `causante_ccaa` set) has no CLI integration assertion. The domain-level `test_causante_ccaa_roundtrips_through_repository` validates the persistence side but does not exercise the CLI flag parsing, option wiring, or JSON payload emission of `causante_ccaa`. A CLI integration test with `--causante-ccaa madrid` on a supported modelo should be added.

---

## Safety Audit

No crash paths introduced. `parse_tax_region` raises `ForalRegimeError` (a typed `AeatError` subclass); `command_error_boundary` handles it. `causante_ccaa: CCAA | None = None` with a pydantic default is safe for existing records that do not carry the field. No raw `os.environ` reads, no `dict[str, Any]` at persistence boundaries, no unclosed handles, no unsafe FFI.


---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S162'
related:
  - "[[2026-05-19-profile-lifecycle-disaster-plan]]"
---

# `cross-domain-continuity` W09.P41 — #162 Code Review

## Status: REVISION REQUIRED

Commit `a6a734b835` — Profile schema axis `irpf_special_regime` + `special_regime_start_date` (Beckham foundation)

---

## SCHEMA-001 | HIGH | No model_validator requiring start_date when regime = IMPATRIADO

`TaxpayerProfile` accepts `irpf_special_regime = IMPATRIADO` with `special_regime_start_date = None` without raising. The doc comment says the date is "Required to compute the six-year window for IMPATRIADO (RIRPF Art. 116)" but no `model_validator(mode="after")` enforces that contract. The window computation in #163 and beyond will receive a `None` date and either crash or silently emit wrong results (year-of-displacement is unknown). A `model_validator` analogous to `_check_objective_estimation_consistency` is required: when `irpf_special_regime is IrpfSpecialRegime.IMPATRIADO` and `special_regime_start_date is None`, raise `DeadlineValidationError`. Both a failing-case test (`IMPATRIADO + None date → ValidationError`) and passing-case test (`IMPATRIADO + real date → ok`, `GENERAL + None → ok`) are absent from the roundtrip suite.

---

## WINDOW-001 | HIGH | beckham_window_active(today) property absent

The commit message and doc strings reference "the six-year window triggered by the opt-in election date (RIRPF Art. 116)" and state this axis is the "Foundation for task #163 (M720 NOT_APPLICABLE) and the M151 stub guard". No `beckham_window_active(today: date) -> bool` property or standalone function exists anywhere in the codebase. Without it, #163's Art. 93.5 M720 exemption and the source-scope filter cannot interrogate whether the window is active, and would either hard-code `True` (wrong after year 6) or re-implement the year arithmetic ad hoc in each consumer. The six-year calculation is: `start_date.year <= today.year <= start_date.year + 5`. A year-7 case (`start_date=date(2018,1,1), today=date(2024,6,1)`) must return `False`; a year-1 case must return `True`. This property belongs on `TaxpayerProfile` (or as a module-level function in `_profiles.py`) and must be tested at unit level.

---

## CLI-001 | HIGH | No CLI flags on profile create / profile edit

`--irpf-special-regime` and `--irpf-special-regime-start-date` are not registered on the `profile create` or `profile edit` commands. The existing `--irpf-estimation-regime` flag is wired through the wizard catalogue (`_catalogue.py`, entry `irpf-estimation-regime`) and surfaces as a Click option via `_commands.py`. The new axis follows the same pattern but the wizard catalogue entry and the corresponding CLI flag are absent. The `SetupAnswers.irpf_special_regime` and `special_regime_start_date` fields have been added to the pydantic model but the upstream wizard question that feeds them (and exposes the flag) was not added. As a result no operator can actually set these values from the CLI surface.

---

## LOCALE-001 | HIGH | New axis has zero locale keys (G4 violation)

The `irpf_special_regime` axis introduces a new user-facing concept (the Ley Beckham regime choice and its start-date prompt) but zero locale keys were added to `es.yml`, `en.yml`, `ca.yml`, or `hu.yml`. The existing `create_stub_modelo_151_refused` key that mentions "impatriados (Ley Beckham)" is in `es.yml` only. Per the standing G4 gate, locale keys for wizard prompts, help text, and validation error messages must be scaffolded via `python -m aeat.locales scaffold` and audited before the axis goes live on the CLI. Hu scaffold-passthrough (FORAL-001 pattern) is acceptable but must be explicit. Currently there is nothing to pass through.

---

## VALIDATOR-001 | MEDIUM | SetupAnswers.special_regime_start_date is bare str, no date parsing

`SetupAnswers.special_regime_start_date` is typed `str = ""` with no `field_validator` to parse or validate ISO-8601 format. By contrast `taxpayer_profile_from_mapping` calls `_parse_date(canonical.get("irpf.special_regime_start_date"))` which handles the conversion at projection time. An invalid date string (e.g. `"not-a-date"`) in the wizard flow will silently propagate a `None` via `_parse_date`'s `InvalidOperation` guard rather than surfacing a typed error at the boundary. Adding a `field_validator` that either parses to `date` or rejects non-ISO strings would close this gap and align with the typed-boundary mandate.

---

## ROUNDTRIP-001 | MEDIUM | Anti-tautology test does not prove start_date drop

The anti-tautology test in `test_irpf_special_regime_persistence_roundtrip.py` mutates the regime value (`general` vs `impatriado`) but does not cover the date-drop regression: save with `special_regime_start_date` set, mutate the stored fact to remove it, reload, assert either `ValidationError` (once the model_validator from SCHEMA-001 is added) or explicit `None`. The current test suite satisfies the two-value inequality proof for the enum axis but leaves the date field's persistence contract partially unverified.

---

## G1 PASS — No naked env reads in modified files.

## G2 PARTIAL PASS — `IrpfSpecialRegime` is a typed `StrEnum`; `TaxpayerProfile` fields use `IrpfSpecialRegime | None` and `date | None`. `SetupAnswers.special_regime_start_date` remains `str` (see VALIDATOR-001). No `Literal["none", "impatriados_art93"]` shape — the enum uses `GENERAL/IMPATRIADO` values; this is acceptable provided the schema TOML and roundtrip align (they do).

## G3 PASS — No user-facing `tr()` calls required in domain layer; error messages in `DeadlineValidationError` use plain strings per existing project convention.

## G4 FAIL — See LOCALE-001.

## G5 PASS — New enum and fields extend the existing profile model cleanly; `taxpayer_model.py` is a new thin re-export module with no duplication.

## G6 PARTIAL PASS — Three real roundtrip tests present; missing: failing-case test for IMPATRIADO-without-date, beckham_window_active unit tests, date-drop anti-tautology proof.

---

## Summary

Four HIGH findings block merge: (SCHEMA-001) missing model_validator for the IMPATRIADO-requires-date contract; (WINDOW-001) `beckham_window_active` property absent — consumers of #163 will have no grounded six-year gate; (CLI-001) wizard catalogue entry and CLI flags not wired — axis is unreachable from the operator surface; (LOCALE-001) zero locale keys for the new wizard prompts, violating G4. Two MEDIUM findings are recommended before #163 begins consuming this axis.

Revision required before merge.

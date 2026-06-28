---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-27-cross-domain-continuity-W09-P41-S352]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity S352 Code Review

## Verdict: APPROVE+FU

No critical or high safety violations. One medium G3 finding (engine-layer hint bypasses `tr()`) and two low findings. Feature is complete and safe to ship; follow-up items are noted below.

---

## Gate Results

| Gate | Result | Notes |
|------|--------|-------|
| G1 — no naked env reads | PASS | No `os.environ`/`os.getenv` in modified files. |
| G2 — typed pydantic at boundaries | PASS | `IvaCompensationPeriodState` is strict/frozen pydantic. CLI payload is plain `dict` for JSON serialisation only, not persisted. Application function signature is typed throughout. |
| G3 — `tr()` for user messages | PARTIAL — see LOCALE-001 | CLI verb messages all use `tr()`. Engine-layer seed hint does not. |
| G4 — no locale yml hand-edits | PASS | Diff shape matches `scaffold` output (self-referencing stub values). |
| G5 — no shims/duplication | PASS | Verb is registered under `iva_wallet_app` → `app`, not a new root command family. `IvaCompensationSeedConflictError` is additive, no aliases. |
| G6 — no tautological tests | PASS | Tests assert persistence contracts, refusal behaviour, and round-trip equality. Anti-tautology test uses two independent isolated profiles with different amounts. |
| Grounding gate | PASS | `legal_refs`/`source_refs` are pulled from registry casilla definitions at projection time in `_observation_from_iva_compensation_history` (lines 192–193 of `_binding_prefill.py`). `IvaCompensationPeriodState` is correctly a raw persistence envelope, not the typed observation model. |

---

## Findings

### LOCALE-001 | MEDIUM | Engine-layer seed hint is hardcoded English, bypasses `tr()`

**Location:** `src/aeat/application/modelo/_actions.py` lines 1733–1739.

The `seed_hint` string is concatenated directly into the `ModeloAggregationBindingError` message. `resolve_error_message` (in `src/aeat/core/errors/_registry.py` line 311) returns `error.args[0]` when it is a non-empty string, so the raw English hint reaches the CLI user verbatim regardless of output language. All other error messages for this error class are routed through the i18n layer via `message_key`. The hint is low-stakes guidance text, not a data or safety issue, but it violates the G3 contract.

**Remediation:** Add a locale key (e.g. `errors.error.error_modelo_aggregation_binding_seed_hint`) and either move the hint into `ModeloAggregationBindingError.translated_message` or route it through the `tr()`-backed suggestion field on `ErrorCode`.

---

### LOCALE-002 | LOW | Step record claims 7 new locale keys; 10 were scaffolded

The step record states "7 new CLI locale keys scaffolded" but the `en.yml` diff adds 10 `seed_*` keys (`seed_help`, `seed_filing_year_help`, `seed_period_help`, `seed_amount_help`, `seed_confirm_help`, `seed_confirm_required`, `seed_invalid_amount`, `seed_negative_amount`, `seed_no_nif`, `seed_conflict`). Minor documentation inaccuracy, no runtime impact.

---

### TEST-001 | LOW | First `_RUNNER.invoke` in `test_cli_seed_verb_refuses_duplicate` is unasserted

**Location:** `src/aeat/entrypoints/cli/test_iva_wallet_inspector.py` lines 316–321.

The first seed invocation result is discarded without asserting `exit_code == 0`. If the first seed silently fails (e.g. NIF not found), the duplicate-refusal assertion on the second invocation still passes but does not prove the conflict path — it may instead be testing the NIF-not-found path. The test uses `_store_profile_with_nif` so the first call should succeed, but the missing assertion makes this fragile. Adding `assert first_result.exit_code == 0` would close the gap.

---

## Safety Summary

- No panics, unhandled exceptions, or resource leaks found.
- `seed_iva_compensation_period` correctly guards against duplicate writes with `IvaCompensationSeedConflictError`.
- No async or concurrency concerns; repository is synchronous.
- `IvaCompensationHistoryRepository` inherits `SecureBoundRepository` RAII pattern; no explicit handle management required.
- `_SEED_STATUS = "seeded"` and `_SEED_EXPEDIENTE_ID = "manual-seed"` are module-level constants, not magic strings at call sites.

## Intent Completeness

All steps from the S352 plan are implemented: application function, CLI verb, refusal guards (no-confirm, no-NIF, duplicate), `_actions.py` hint improvement, locale scaffold, and regression tests. The seeded state flows into `_observation_from_iva_compensation_history` → binding prefill as described.

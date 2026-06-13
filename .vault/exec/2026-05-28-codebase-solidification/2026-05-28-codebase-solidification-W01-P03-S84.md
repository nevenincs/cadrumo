---
step_id: S84
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S84 — describe label localisation tests

## Outcome

Extended `src/aeat/entrypoints/cli/test_modelo.py` with three S84 tests in a
dedicated section:

- `test_describe_label_key_exists_per_locale` — parametrized over all four
  locales and all 11 label keys; asserts each renders non-empty and not as
  the bare key (i.e. the entry exists in the catalogue).
- `test_describe_label_keys_distinguish_locales` — asserts at least one key
  renders differently across locales, preventing silent copy-paste regressions.
- `test_describe_output_contains_localized_labels_in_english` — invokes the
  real `aeat app modelo describe 303` CLI command (conftest pins
  `AEAT_OUTPUT_LANGUAGE=en`) and asserts each English label string appears in
  the output, confirming the `tr()` wiring is live end-to-end.

No mocks, no patches, no skips. 44 parametrized cases + 2 structural tests.

## Files touched

- `src/aeat/entrypoints/cli/test_modelo.py`

## Verification

All 150 tests collected across `test_ledger.py` and `test_modelo.py` pass
(3 pre-existing failures unrelated to S81-S84: `ModeloRecordPayload`
subscriptability and M303 period enumeration). Step closed via
`vault plan step check`.

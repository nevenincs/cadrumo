---
step_id: S180
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P07.S180 — CSV encoding fallback chain test

## Outcome

Extended `src/aeat/adapters/inbound/financial/providers/test_csv.py` with four
new real-behavior test functions:

- `test_csv_provider_decode_bytes_follows_fallback_chain` (parametrized over 3
  cases): feeds bytes that are uniquely decodable by exactly one fallback codec;
  asserts that `_decode_bytes` returns the expected encoding and round-trips the
  text correctly. Cases cover `utf-8-sig` (BOM-prefixed), `cp1252` (0x80 byte
  invalid in utf-8), and `iso-8859-1` (0x81 byte invalid in cp1252).

- `test_csv_provider_decode_bytes_preferred_codec_wins_over_chain`: verifies the
  preferred codec wins ahead of the fallback chain when set to a valid codec.

No mocks, no stubs, no patches. All four tests call `_decode_bytes` directly on
a real `CsvProvider` instance. `monkeypatch.setenv` controls the preferred codec;
`load_settings()` constructs a fresh `Settings()` per call (no cache to bust).

## Files touched

- `src/aeat/adapters/inbound/financial/providers/test_csv.py`

## Verification

All 11 tests in `test_csv.py` pass. Commit: 85bf0e231.
`vault plan step check` applied.

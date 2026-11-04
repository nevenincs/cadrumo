---
tags:
  - '#audit'
  - '#fixture-canonicalization'
date: '2026-11-04'
modified: '2026-11-04'
body_schema: 'body-v2'
body_hash: 'sha256:f2dcee68612b6280a399d57dfaaa776105f28b4f75ef2047a10c8a763c0db644'
related:
  - "[[2026-11-04-fixture-canonicalization-plan]]"
---

# `fixture-canonicalization` audit: `Fixture canonicalization review`

## Scope

Rolling review of the fixture-canonicalization plan. Entry 1: P01 phase close (2026-11-04), commits `844e066bec`, `5331566790`, `c27ad785a8`, `0183a48d3b`, `ba0cdabd17`, reviewed against both 2026-11-04 fixture-canonicalization ADRs. Verdict: revision required; P01.S04 reopened.

## Findings

### identity-role-reuse | high | identifier replacement bound catalogue role identities to unrelated roles

`c27ad785a8` replaced `A58818501` with `B00000034` in about 163 generic-supplier uses (for example `native/desktop/frontend/tests/ledger-invoices-model.spec.ts:130`, `src/cadrumo/application/filing/tests/test_modelo_347_fichero_export.py`) although `dev/fixtures/personas/identities.toml:227` binds it to `fontanero.cliente-restaurante`. Same pattern: `B00000026` (`fontanero.proveedor`), `B00000042` (`fontanero.gestoria`), `X0000000T` (`intracom.titular`), `Y0000000Z` (`sociedad.administrador`), `00000001R` (`asalariada.conyuge`). Violates the one-identity-one-role constraint; `just check-identity` checks shape only. `X0000000T` also equals the registry development mock developer id (`src/cadrumo/_data/registry/aeat/facts/0147-aeat-eedd-development-mock-software-identity.toml:29`).

### minted-id-tokens | medium | generator token names depend on whole-run order

`native/desktop/frontend/scripts/modelo_fixtures.py:544` names replacement tokens from a process-wide counter, so per-family seeding will name the same id differently from a full run. The `bucket_event_id` rewrite at `:568` applies to any object with that key. Rewriting the two opaque ids is otherwise sound: no window or Rust consumer verifies them (`DisagreementAnswers.tsx:32`, `DisagreementDialog.tsx:96`).

### recording-placement | medium | committed recording inputs sit in the projection tree

Recording questions live under `native/desktop/frontend/src/dev/fixtures/ledger-recording-questions/`, which P04 will ignore; `src/cadrumo/application/invoices/tests/test_figures_preview_recording.py:18` reads a window projection, which would make a Python lane depend on seeding.

### p04-coverage | medium | P04.S13 misses two of three envelope embeds

`native/application/src/runtime_client/live_tests.rs:40` and `native/desktop/src-tauri/src/agent/person/native.rs:1487` also `include_str!` envelopes; the Step names a stale path instead of `native/desktop/src-tauri/src/shell/modelo/tests.rs`.

### support-module-imports | low | frontend scripts import tests support modules

`native/desktop/frontend/scripts/ledger_recordings.py:93` follows the existing `modelo_fixtures.py` practice; each support module calls the real production rule.

### duplicate-stand-in | low | cast stand-in for Invoice in shared support

`src/cadrumo/domain/invoices/tests/duplicate_recording_support.py:28` casts `StoredInvoiceFacts` to `Invoice`; build real values instead.

### cosmetic | low | small leftovers

`PROVEEDOR NACIONAL SA` carries an S.L.-letter CIF in 347 tests; an empty untracked `native/desktop/frontend/scripts/ledger_recording_questions/` directory remains.

## Recommendations

- identity-role-reuse: move non-persona uses to counters the catalogue does not bind, rebind `intracom.titular` away from the registry mock id, and widen P05.S20 to flag a catalogue value used outside its role.
- minted-id-tokens: derive tokens from stable row fields and target the rewrite structurally; state the normalisation in the generator docstring and the Rust test name.
- recording-placement: move recording questions beside committed inputs; in P04 make Python tests assert against questions and their own expected values.
- p04-coverage: correct P04.S13 scope to the three embeds.
- duplicate-stand-in: build real Invoice values.

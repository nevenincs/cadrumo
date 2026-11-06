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

## P02 phase-close review and P01.S04 re-review (2026-11-05)

Scope: P02.S05 from `2d72333eca`, P02.S06 `1d2d65e83e`, and the P01.S04 rework `1585ed1b28` with its follow-ups, read at `a50585aaa4`. Verdict: blocking findings; S06, S24 and S04 reopen.

### ci-desktop-configure | high | the per-PR desktop job cannot configure CMake and the merge verdict needs it

`.github/workflows/merge-gate.yml:196-233` runs `just test-frontend` and `just test-native`, which configure `linux-x86-64` (`justfile:675-676`). That preset keeps `CADRUMO_CONFIGURE_PAYLOAD` on (`CMakeLists.txt:163`), and `native/cmake/Agent.cmake:5-7` stops when `CADRUMO_PACKAGE_AGENT_SOURCE_DIR` is not passed. `merge-gate.yml:236` makes the verdict need `desktop`. Nothing provisions Node, Rust, CMake 4.4 or Ninja on the runner. `just setup-browser` installs Chromium for Python Playwright 1.64.1 (`uv.lock:2497`), while the frontend uses `@playwright/test` 1.63.0 (`native/desktop/frontend/package.json:59`). The scoped `gate` job now needs Node too (`merge-gate.yml:155-164`).

### identity-role-reuse-s24 | high | S24 bound catalogue roles to values that generic tests already use

`b6887c429e` bound three values that generic tests already use:
- `alta.titular` to `00000020C`, already used at `src/cadrumo/adapters/outbound/aeat/auth/tests/test_authenticator_contracts.py:139,170`;
- `alta.cliente` to `B00000141`, already used at `src/cadrumo/domain/calculations/registry/tests/test_nif_data_type.py:60`, `test_long_tail_data_types.py:102`, `src/cadrumo/entrypoints/tests/profile_persistence/test_invoice_accumulative_cross_modelo_periods.py:322` and `src/cadrumo/application/aggregation/tests/test_invoice_category_counterparty_mismatch_is_reported.py:60`;
- `alta.papeleria` to `B00000158`, which `src/cadrumo/tests/fixtures/financial/tabular-dialects/libro_facturas_recibidas_2025_2026.csv:3` uses under another name.

### identity-role-reuse-residual | high | the S04 rework missed three generic uses of B00000034

`fontanero.cliente-restaurante` is still the generic supplier inside CSV byte literals at:
- `src/cadrumo/entrypoints/tests/conformance_ledger_seed_support.py:276`;
- `src/cadrumo/entrypoints/tests/test_invoice_intake_operation_composition.py:97`;
- `src/cadrumo/application/invoices/tests/test_catalogue_intake_operation.py:396`.

### docs-sequences-in-fixtures-check | medium | fixtures-check re-executes every docs golden uncached

`dev/fixture_projections/registry.py:243-248` runs the full `dev.docs.sequences check`. The merge gate already runs the goldens in a scoped, cached step (`merge-gate.yml:177-193`), so the generated-seed check should be `seeds --check`.

### vacuous-determinism | medium | check --determinism reports ok for families without a proof

`dev/fixture_projections/cli.py:163-165` returns no finding when `family.determinism is None`, and nine of ten producer families declare none (`registry.py:152-242`). The projections ADR requires two identical builds before a projection leaves git.

### recorded-by-test-producers | medium | three producers are pytest tests and two keep their questions only in the output

`ledger-staged-check`, `assets-served-words` and `ledger-entry-options` seed through pytest (`registry.py:110-121,227-230`), against "test processes never write fixtures". `src/cadrumo/application/ledger/tests/test_staged_check_recording.py:170-176` and `src/cadrumo/application/actividad_asset/tests/test_served_words_recording.py:97-111` re-record only questions already in the output, so after P04 a clean seed records nothing. `cli.py:84-88` passes the caller's environment, so a leftover switch makes `check` write.

### seeding-entry-points | medium | setup does not seed, and seeding on a fresh tree fails before frontend install

- S06 left `setup` unchanged, against the ADR Implementation and the plan Verification line.
- `fixtures-seed` requires `native/desktop/frontend/node_modules` (`cli.py:146-150`). It runs before `_native-configure` and `desktop-frontend-install` (`justfile:59,774,782`), so `dev`, `test-frontend` and `test-native` stop on a fresh worktree.
- `test-native` now needs Node, although the Rust tests read only the envelopes.

### persona-check-structural | medium | fixtures-check only parses the personas

`dev/fixture_projections/personas.py:1-7` predates the reader. It checks TOML parsing and CSV shape, but not schema question ids, role resolution or year tokens.

### catalogue-generic-pool | medium | no reserved generic counter range

- Catalogue values stay in wide generic use: `12345678Z` in 610 files and `00000000T` in 149.
- `00000002W` is a generic taxpayer at `src/cadrumo/adapters/outbound/calculation_summary_pdf/tests/summary_report_support.py:54`.
- `B00000018` is a generic payer in about 8 withholding tests.
- Without a declared generic pool, new roles keep colliding with generic uses. This belongs to P05.S20.

### silent-empty-input | low | a mistyped input path hashes as empty

`dev/source_tree.py:372-378` skips missing prefixes silently.

### untested-verbs | low | only the stamp logic has tests

`dev/fixture_projections/tests/test_stamps.py` does not cover `seed`, `check`, `clean` refusal, the containment checks in `_removable_targets` (`cli.py:225-237`) or prerequisite failure.

### modelo-undeclared-outputs | low | the Modelo producer writes files its family does not declare

`modelo-fixtures.mjs` also writes `src/shell/modeloContract.ts` and `relayBounds.ts` (`registry.py:147-148`).

### cold-stamp-cost | low | an unstamped committed family reports missing

`stamps.py:175-178` reports such families as missing. A fresh checkout therefore regenerates every family, including the roughly 13.5-minute Modelo build.

### catalogue-cosmetics | low | small catalogue inaccuracies

- The NIE comment about counter zero is stale.
- `FR00000000001` carries VAT key 00 where the formula gives 15.
- The deliberately invalid `B00000282` is not listed under `[[refusals]]`.
- A cooperative carries a B-letter CIF.
- The first plan Verification bullet still places the determinism proof inside `fixtures-check`.

### pre-existing-host-failures | low | two runtime host tests fail on content from before this plan

- `src/cadrumo_runtime/host/tests/frontend/cli/test_ledger_list_filter.py` fails with `FAIL_EXCHANGE_RATE_PROVIDER` on `ledger import revolut-multi.csv`, a network-dependent provider in a test.
- `src/cadrumo_runtime/host/tests/frontend/cli/test_staged_check_verb.py` fails with extra inputs in `LedgerStagedCheckEnvelope`.

Both reproduce with the files restored to `0d2bfe089e^`.

### report-line-collation | low | a docs problem line printed onto an advisory line went unreported

S24 found that the `llm-inspect-history.seq` drift was hidden from `refresh` because its problem line was appended to an advisory line.

### provenance-not-applicable | low | system-derived not-applicable zeros are labelled operator-manual

`SheetRelationProvenance` has only `LOCAL_FILING`, `AEAT_LIVE` and `OPERATOR_MANUAL`. The P03.S25 pre-activity zero reuses `OPERATOR_MANUAL`, as the existing not-applicable zero does.

## Recommendations (2026-11-05)

- ci-desktop-configure:
  - Configure the job like the release job, or use a payload-off test preset.
  - Provision its toolchain and the npm Playwright browser.
  - Keep `desktop` out of `verdict.needs` until a real runner run is green.
- identity-role-reuse: move the generic uses onto counters nothing binds, and let P05.S20 declare and enforce a generic pool.
- recorded-by-test-producers and seeding-entry-points follow the projections ADR as written: producers leave test modules, and `setup` seeds after authority publication and frontend install.
- A follow-on decision may be needed on whether a system-derived not-applicable provenance kind belongs in `SheetRelationProvenance`.

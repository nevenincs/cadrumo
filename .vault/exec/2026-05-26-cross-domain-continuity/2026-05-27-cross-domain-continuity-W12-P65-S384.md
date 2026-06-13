---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-27
modified: '2026-05-27'
step_id: S384
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-source-jurisdiction-axis-adr]]"
---

# `cross-domain-continuity` `W12.P65.S384`

Encode the regulatory truth table for source_jurisdiction at the CLI create boundary: profile-conditional default (LIRPF Art. 8 universal-base ES for residents under the general regime), profile-conditional refusal (TRLIRNR Art. 2/10 for non-residents, LIRPF Art. 93.5 for impatriados), and operator-override pass-through.

Commits:
- `c6e402eb3` — source-side helper + 4 truth-table tests
- `5a7601f89` — locale companion (refusal keys, 4 locales)
- `ef3562e64` — patch1: thread source_jurisdiction through `ledger_transaction_payload` / `ledger_transaction_review_payload` read-projection functions
- `3f7427714` — patch2: fix `taxpayer_type.fiscal_residency` descriptor key in IRNR test fixture
- `f6c8d1028` — patch3: provision full IRNR axis tuple in fixture
- `3802591f6` — patch4: switch to UE country to dodge the `representante_fiscal_nombre` schema gap

- Modified: `src/aeat/entrypoints/cli/_ledger.py`
- Modified: `src/aeat/entrypoints/cli/test_ledger_validation_paths.py`
- Modified: `src/aeat/application/ledger/_actions.py` (patch1)
- Modified: `src/aeat/locales/{en,es,ca,hu}.yml`

## Description

The new `_resolve_source_jurisdiction(operator_value, *, fiscal_residency, irpf_special_regime)` helper at `_ledger.py` encodes the regulatory branching directly:

- Operator value present → return verbatim. Honour explicit override.
- `fiscal_residency == NON_RESIDENT_IRNR` → refuse via `_bad(tr("cli.ledger.add.source_jurisdiction_required_irnr"))`. TRLIRNR Art. 2 / Art. 10.
- `irpf_special_regime == IMPATRIADO` → refuse via `_bad(tr("cli.ledger.add.source_jurisdiction_required_beckham"))`. LIRPF Art. 93.5 segregation.
- Otherwise → return `"ES"`. LIRPF Art. 8 universal-base presumption for the resident general case.

The helper is called immediately before `ManualLedgerTransactionCommand(...)` construction. The active profile is obtained via `_profile_to_taxpayer(current_state)` — the same TaxpayerProfile projection every other CLI verb uses. Stateless validator on the model layer (S381) stays intrinsic; profile-aware behaviour lives only in this helper. The helper docstring documents the convention so future entrypoints (importer, bulk classify) pre-validate via the same call site.

Two new locale keys: `cli.ledger.add.source_jurisdiction_required_irnr` and `cli.ledger.add.source_jurisdiction_required_beckham`, populated across en/es/ca/hu via the locale CLI scaffold cycle.

Four truth-table CLI integration tests in `test_ledger_validation_paths.py`, each anchored on a regulatory article and each provisioning the relevant profile axis via the diagnostics-app `profile set` descriptor surface:

- `test_ledger_add_defaults_source_jurisdiction_to_es_for_resident_general` — default fixture, no axis override, assert payload carries `"ES"`.
- `test_ledger_add_refuses_when_source_jurisdiction_omitted_for_impatriado` — set `irpf.special_regime=impatriado` + `irpf.special_regime_start_date`, omit flag, assert refusal output.
- `test_ledger_add_refuses_when_source_jurisdiction_omitted_for_non_resident` — set `taxpayer_type.fiscal_residency=non_resident_irnr` + UE country, omit flag, assert refusal output.
- `test_ledger_add_honours_operator_source_jurisdiction_override_for_resident` — resident general profile + explicit `--source-jurisdiction FR`, assert payload carries `"FR"`.

## Sibling commit — S384b (locale companion)

`5a7601f89` lands the four-locale yml deltas (two refusal keys × four locales = 8 set calls), per the standing locale-CLI sibling-commit convention.

## Patch chain — four hot-fixes surfaced by smoke

The initial commit `c6e402eb3` shipped with three latent bugs not caught at authoring time. Smoke surfaced them in order; each patch is logged here as part of the canonical S384 record (rolled in per the retro convention):

- **`ef3562e64` (patch1, projection wire):** `ledger_transaction_payload` and `ledger_transaction_review_payload` in `_actions.py` manually construct the payload kwarg-by-kwarg from a `Transaction`; both were silently dropping `source_jurisdiction`. The domain field, persistence roundtrip, and create-path were correct; only the read projection had the gap. Patch adds `source_jurisdiction=transaction.source_jurisdiction` to both constructions. Default-ES test passes after this patch.
- **`3f7427714` (patch2, descriptor key):** the IRNR refusal test used `taxpayer.fiscal_residency` as the diagnostics-setter descriptor key; the canonical path per the wizard catalogue is `taxpayer_type.fiscal_residency` (cf. `src/aeat/application/wizard/_catalogue.py:763`). Patch corrects the key path.
- **`f6c8d1028` (patch3, IRNR axis tuple):** setting only `fiscal_residency=non_resident_irnr` tripped the `TaxpayerProfile._check_representante_fiscal_required` model-validator (TRLIRNR Art. 10 representante requirement), masking the source-jurisdiction refusal under a generic config-repair validation error. Patch adds the full tuple: country_of_fiscal_residence, representante_fiscal_nif, representante_fiscal_nombre.
- **`3802591f6` (patch4, UE country workaround):** patch3 surfaced a schema-catalogue mismatch — `representante_fiscal_nombre` is referenced by the wizard catalogue, projection, and pydantic model but absent from `user_profile/schema.toml`, so the diagnostics setter refuses the key. Patch switches the fixture country to FR (UE/EEE so the representante requirement does not fire), with an inline comment documenting the workaround. The underlying schema gap is filed as a separate follow-up.

After patch4 all four truth-table tests pass.

## Verification

- Smoke command: `uv run --no-sync pytest src/aeat/entrypoints/cli/test_ledger_validation_paths.py -x -k "source_jurisdiction" -v`
- Result post-patch4: 4 passed.

## Gate evidence

- G1 no naked env reads: unchanged.
- G2 typed pydantic at boundary: resolver consumes typed TaxpayerProfile axes; no untyped boundary.
- G3 user messages via tr(): both refusal keys routed through `tr()`; help text unchanged from S383.
- G4 no locale yml hand-edits: refusal keys populated via the locale CLI scaffold.
- G5 no shims: helper is single-source; patch-chain follows the surrounding pattern of fixture-axis provisioning.
- G6 no tautological tests: expected outcomes derive from the LIRPF Art. 8 / Art. 93.5 / TRLIRNR Art. 2/10 regulatory branching cited inline in each test's docstring, not from re-running the resolver.

## References

- ADR: source-jurisdiction-axis-adr (Rationale — three-reason CLI-create-boundary justification)
- Sibling Steps: S381 (model field), S382 (encrypted roundtrip), S383 (CLI flag + write-side), S385 (aggregation provenance).
- Sibling commits in this Step: `5a7601f89` (locale), `ef3562e64` (projection patch), `3f7427714` (descriptor key patch), `f6c8d1028` (IRNR axis tuple patch), `3802591f6` (UE-country workaround patch).
- Surface: `_resolve_source_jurisdiction` helper at `src/aeat/entrypoints/cli/_ledger.py`; call site at the `ledger_add` body before `ManualLedgerTransactionCommand(...)`; tests at `test_ledger_validation_paths.py:228-376`.

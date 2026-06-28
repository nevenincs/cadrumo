---
tags:
  - '#audit'
  - '#test-fidelity-sweep'
date: '2026-05-20'
modified: '2026-05-20'
related: []
---



# `test-fidelity-sweep` audit: `test-fidelity-false-positive-swarm-audit`

## Scope


## Findings


## Recommendations



## Context

## Scope

Nine read-only sonnet auditors swept the entire `src/aeat/**/test_*.py`
surface — 603 files, ~4,581 classified test functions — against a fixed
false-positive rubric: tautological calculation, mocked/faked SUT,
skip/xfail, check-free or vacuous assertion, self-fulfilling fixture,
weak roundtrip. Every auditor reported full coverage (`files_read ==
files_in_scope`).

Result: **28 VIOLATION + 28 SUSPECT**. Swarm output is inventory, not
gospel — each finding is verified against current code before a fix
lands.

## Partition tally

| Partition | Files | Functions | VIOLATION | SUSPECT |
| --- | --- | --- | --- | --- |
| registry A | 54 | ~580 | 4 | 2 |
| registry B | 54 | ~480 | 9 | 2 |
| domain (non-registry) | 100 | ~650 | 3 | 1 |
| application | 156 | 1551 | 1 | 1 |
| adapters/outbound | 74 | ~340 | 2 | 11 |
| persistence + inbound | 72 | ~310 | 4 | 2 |
| entrypoints/cli | 46 | 359 | 2 | 6 |
| core | 36 | 258 | 1 | 2 |
| misc | 11 | 53 | 1 | 2 |

## VIOLATION findings — registry calculation tautology

### registry/test_lookup_bracket_by_ccaa.py:128 / :144 / :160 — tautological bracket interpolation

Synthetic `_madrid_bracket_param()` / `_cataluna_bracket_param()` carry
invented marginal rates; the expected Decimals (`1835.90`, `2213.25`)
are hand-computed by re-applying the same bracket-interpolation formula
the SUT executes. Would pass even if the autonomous IRPF scale were
wrong. Remediation: ground the bracket params in BOE-published CCAA
scales, or convert to a primitive-evaluator contract test that asserts
interpolation mechanics without a hand-summed expected.

### registry/test_ledger_iva_aggregation_binding.py:~307 — self-referential 390-vs-303 sum

`test_modelo_390_annual_iva_totals_reconcile_with_four_..._modelo_303_filings`
asserts the annual 390 engine output equals the sum of four 303 engine
outputs — both sides produced by the same formula engine. Remediation:
assert against an AEAT-workbook annual total, or restructure as a
binding-resolution wiring test.

### registry/test_modelo_190_registry.py:86 — tautological classification

Test re-applies the SUT's `data_type`/`input_kind` classification logic.

### registry/test_modelo_303_registry.py:378 — tautological compensation

`expected_aplicada`/`expected_pendiente` hand-computed with the same
`min`/subtraction the registry compensation formula declares.

### registry/test_modelo_349_registry.py:648 / :862 — tautological rectification delta

`20.00 = 200 - 180` re-derives the registry rectification formula.

### registry/test_modelo_369_registry.py:395 — tautological IOSS sum

`38.00 = 15.20 + 22.80` re-sums the fixture the SUT aggregates.

### registry/test_modelo_390_registry.py:153 / :222 — tautological annual aggregation

Expected values are the test's own inline sum of the literals the SUT
aggregates.

### registry/test_registry_scenarios.py:25 — tautological scenario expectations

`_normal_direct_estimation_payments_scenario` / `_negative_simplified_base_scenario`
expected Decimals are hand-computed with the registry arithmetic.

### registry/test_relation_closure.py:127 — tautological relation closure

`test_modelo_180_relations_resolve_from_observed_source_filings`
expected sums hand-computed across quarters.

## VIOLATION findings — domain

### domain/fincas/test_aggregates.py:147 — tautological LIRPF aggregation

Amortizacion / reduccion / imputacion Decimals hand-computed from LIRPF
formulas with no AEAT-workbook grounding.

### domain/fincas/test_amortization_ledger.py:64 / :90 — tautological 3% pro-rata

Inline comments re-apply the LIRPF art. 23.1.f 3% pro-rata formula to
produce the expected Decimal.

### domain/modelos/test_calculation_revision.py:17 — self-fulfilling hash

`test_revision_id_without_borrador_metadata_...` recomputes the SHA-256
with the identical algorithm `derive_calculation_revision_id` uses; a
wrong payload mapping would corrupt both sides equally.

## VIOLATION findings — application / outbound

### application/auth/test_ensure_session.py — faked auth provider

Hand-rolled `_Provider` with scripted call-counters replaces the real
AEAT auth provider; `AeatSession` / `AeatLoginAssertion` never exercised.

### adapters/outbound/aeat/verify/test_verify.py:98 / :113 — recording double controls verdict

`_RecordingPage.content()` is hardcoded to the exact HTML the parser
needs to reach the asserted `True`/`False`. A `verify_csv` that always
returned the same verdict would pass. Remediation: split the offline-HTML
parser contract test from the session-lifetime spy test.

## VIOLATION findings — persistence

### adapters/persistence/storage/envelope/test_envelope.py:~78 — weak roundtrip

`test_plaintext_round_trip` checks only `payload` + `schema_version`;
`written_at` and `classification` never asserted — strict `loaded == env`
absent.

### profile/test_inventory_roundtrip.py:~192, storage/test_attachment_store_roundtrip.py:~186, profile/test_assets_roundtrip.py:~190 — tautological anti-tautology proof

Each anti-tautology proof guards with bare `except Exception:` — any
exception (connection error, OSError) satisfies the proof even when the
boundary validator never fired. Remediation: narrow to the specific
`ValidationError` the boundary is expected to raise.

## VIOLATION findings — cli / core / misc

### entrypoints/cli/_config/test_apoderado.py:14 — exception-introspection instead of CLI surface

Asserts `result.exception` `str()` content, not exit code / output; an
unrelated leaked exception passes.

### entrypoints/cli/test_overview_backlog_verb.py:88 — vacuous exit-code branch

`if result.exit_code == 0:` makes the only assertion conditional; a
non-zero exit passes with zero assertions executed.

### core/test_resources.py:94 — unconditional tautology

`assert payload.startswith(b"") or len(payload) >= 0` is true for every
bytes value, including an empty file.

### locales/test_locale_translation_honesty.py:68 — skip-in-disguise

`if "untranslated_pending" in locale_allows: return` short-circuits the
whole comparison; the wholesale allowlist bucket keeps the test
permanently green regardless of ca/hu translation drift.

## SUSPECT findings

Recorded for verification: registry cross-dependency hand-sums
(test_cross_dependency_calculations.py:335, test_detail_record_observations.py:90,
test_modelo_369_registry.py:593, test_read_parameter_public_api.py:27);
domain currency stub (currency/test_service.py:15); application renta
ledger self-fulfilling fixture (aggregation/test_renta_ledger_aggregation.py:194);
outbound smoke tests + LLM `_DeterministicAdapter` + Cl@ve / stealth
recording doubles + the `xfail(strict=True)` capture-replay marker
(11 outbound suspects); persistence POSIX-only / keyring conditional
skips; cli source-scan + signature-introspection + auth-test metadata
checks (6 suspects); core singleton `is not None`-only assertions;
misc namespace-empty early return + in-process import check.

## Remediation discipline

Fixes must make tests genuinely exercise behaviour — never weaken an
assertion to pass. Tautological calculation tests are grounded in BOE /
AEAT-workbook authority where one exists, otherwise converted to graph-
wiring / validation / provenance / primitive-evaluator-contract tests.
Anti-tautology proofs narrow to the specific expected exception.
Vacuous CLI assertions assert real output and exit code unconditionally.


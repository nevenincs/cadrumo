---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-17'
body_hash: 'sha256:fd5b8b8ff526dfdeebdcca150155a0ae7c9d7d8be9497f3ad8bc49bd230d0d80'
step_id: 'S255'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# follow-on to W08.P35.S140 sweep: convert 120 hardcoded f-string error raises across 43 application files identified by the Haiku discovery sweep

## Scope

- `full file list and operator-facing subset filed in S140 Step Record`
- `batch by surface (modelo registry storage etc) per locale CLI rule scaffold-then-fill`
- `mechanical work`
- `src/aeat/application/`

## Description

Batch 1 (de-risked slice). The Step's "120 f-string raises" over-scopes the true work: the S140 discovery record already classified most as programmer-facing `ValueError`/`TypeError` invariant guards that are never operator-rendered and must stay raw. A mechanism trace established that the CLI error boundary and `bad_parameter_from_error` render a domain error via `resolve_error_message`, whose precedence is `translated_message` locale key, then raw `args[0]` f-string, then registry default. So the raise-site f-string IS operator-facing today (via the args[0] fallback), and the correct localisation is a typed `translated_message` key plus `context`, not a raise-site `tr()` wrap.

- Convert five operator-ACTIONABLE filing raises (errors an operator triggers by supplying a bad id or an unsupported target) to `translated_message="application.filing.errors.<key>"` + `context={...}`: original-draft-not-persisted and no-persisted-amendment (`_complementaria.py`); import-failed, modelo-not-in-registry, unexpected-ejercicio (`_import.py`).
- Author the five locale leaves across en/es/ca/hu through the `python -m aeat.locales` CLI (scaffold-then-fill); the English value reproduces the exact former f-string with `%{...}` placeholders so the operator-facing text is byte-identical, while es/ca/hu now localise.
- Leave RAW (per S140 and confirmed non-actionable): the ~24 `_export.py` / `_export_xml_dictionary.py` export-layout / registry-definition invariants (`export field must declare offset/length/kind/casilla_id/binding/header_key`, `unsupported field kind`), the `_complementaria.py` protocol-shape / missing-CSV data-integrity guards, and every `ValueError`/`TypeError` and aggregation/auth/calculations invariant guard — a taxpayer can never trigger these; they are registry-authoring bugs, not operator errors.
- Update the two `test_import.py` assertions that matched on `str(exc)` (now empty, since the error carries a key not `args[0]`) to assert the operator-facing text via `resolve_error_message(excinfo.value)` — the expected substring is derived from the English locale value, not copied from a broken run.

## Outcome

Five operator-facing filing errors now localise to the operator's active language while preserving byte-identical English text. Verified: a probe confirms `resolve_error_message` renders each converted error identically to its former f-string under `AEAT_OUTPUT_LANGUAGE=en` and in Spanish/Catalan/Hungarian; ruff, ruff format, and ty are clean; `python -m aeat.locales scaffold --check` and `audit` are clean; and `test_parity` + `test_locale_translation_honesty` + `test_self_referential_string_conformance` + the full `application/filing/tests` suite pass (275 passed, 0 failed, sequential). The Step remains open pending the remaining operator-facing subset (the filing tail plus ledger and overview), to be driven as a consolidated follow-on batch; box-flip deferred to the coordinated plan-reconciliation pass.

## Batch 2 (consolidated remainder)

Applies the batch-1 pattern to the remaining operator-actionable raises across filing, ledger, and overview — 14 sites, 7 locale keys — closing the operator-facing surface of this Step.

- `_import.py`: the period/ejercicio canonicalisation-mismatch raise → `application.filing.errors.period_ejercicio_mismatch`.
- `_id_resolution.py`: the four transaction-id-prefix refusals (non-hex, too-long, no-match, ambiguous) → four `application.ledger.errors.transaction_id_prefix_*` keys; the operator supplies the id prefix on every single-subject ledger verb.
- `_llm_classification.py`: eight identical "transaction not found" raises → one `application.ledger.errors.transaction_not_found` key.
- `_agenda.py`: the non-positive-horizon refusal → `application.overview.errors.horizon_days_not_positive`.
- Production control-flow fix: `resolve_lineage_transaction_id` discriminated the no-match case by string-matching `str(exc)`, which the conversion emptied; it now discriminates on the typed `translated_message` key (more robust than the rendered, now-localised text). Test assertions that read `str(exc)` / `match=` shifted to the locale-independent `translated_message` + `context` identity (ledger/overview) or an English-forced `resolve_error_message` (the parametrised import test).
- Left raw (per S140 + confirmed non-actionable): the ledger `_actions_common` command-integrity guards, the `_models` `INTERNAL_TRANSFER` model validator (also a `ValueError`), the overview module `__getattr__` `AttributeError`, and every export-layout/registry invariant.

Batch-2 gates green under sequential pytest: ruff + format + ty clean, locale scaffold --check + audit clean, and `application/ledger/tests` + `application/overview/tests` + `application/filing/tests` + `domain/transactions/tests` + `test_parity` + `test_locale_translation_honesty` + `test_self_referential_string_conformance` = 988 passed, 0 failed. Combined batch 1 + batch 2 = 19 operator-facing filing/ledger/overview raises localised; S255's operator-facing surface is complete. Box-flip deferred to the coordinated plan-reconciliation pass.

## Notes

The true convertible count is far below the plan's 120: most raises are internal invariant guards left raw by design. The typed `translated_message` + `context` pattern (including the `str(exc)`-to-identity test-assertion shift and the one production control-flow discriminator that inspected `str(exc)`) held across all three domains. Any residual application-layer f-string raises are internal `ValueError`/`TypeError` and registry/layout invariants that are never rendered to the operator and correctly stay raw.

---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S255'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S255 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The follow-on to W08.P35.S140 sweep: convert 120 hardcoded f-string error raises across 43 application files identified by the Haiku discovery sweep and ## Scope

- `full file list and operator-facing subset filed in S140 Step Record`
- `batch by surface (modelo registry storage etc) per locale CLI rule scaffold-then-fill`
- `mechanical work`
- `src/aeat/application/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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

## Notes

The true convertible count is far below the plan's 120: most raises are internal invariant guards left raw by design. Batch 1 establishes and proves the typed `translated_message` + `context` pattern end-to-end (including the `str(exc)`-to-`resolve_error_message` test-assertion shift), so the remaining operator-facing raises can follow the same shape.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

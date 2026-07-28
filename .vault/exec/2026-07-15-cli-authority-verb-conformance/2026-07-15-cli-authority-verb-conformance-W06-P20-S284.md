---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S284'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S284 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Assert the accepted period tokens on the error envelope structured context rather than on rendered prose, so a wording pass cannot red the grammar cases and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_ledger_period_grammar.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Assert the accepted period tokens on the error envelope structured context rather than on rendered prose, so a wording pass cannot red the grammar cases

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_ledger_period_grammar.py`

## Description

Production, `src/cadrumo/entrypoints/cli/_common.py`:

- Add `_ledger_period_accepted_tokens`, which derives the span-shaped registry
  tokens the ledger `--period` boundary accepts from the acceptance rule itself:
  each `StandardPeriodCode` member the ledger normalises whose `(year, token)`
  `Period` carries a calendar date span. Instalment claves `1P`-`4P` and the
  extended-union members resolve to no span and are excluded, so a new span-shaped
  enum member is advertised automatically and the advertised set cannot drift from
  what the boundary admits.
- Add `_LedgerPeriodRefusal`, a `typer.BadParameter` subclass carrying the accepted
  set on `accepted_period_tokens`. Subclassing preserves the usage-refusal boundary
  behaviour and exit code, so every existing `pytest.raises(typer.BadParameter)`
  case and the runtime refusal are unchanged.
- Raise `_LedgerPeriodRefusal` (not the bare `_bad`) from `_canonical_period`'s
  unrecognised-period path, threading the derived accepted set as data.

Production, `src/cadrumo/entrypoints/cli/_terminal_errors.py`:

- Add `_structured_refusal_context` and call it from `_build_parse_time_refusal`,
  so a callback refusal carrying `accepted_period_tokens` surfaces the accepted set
  on the JSON error envelope's structured `context` under `--format json`. The
  emitted key is `accepted_periods`, not `accepted_period_tokens`, because the
  error-context scrubber redacts any key containing `token`.

Test, `src/cadrumo/entrypoints/cli/tests/test_ledger_period_grammar.py`:

- Replace the rendered-prose token assertions in the calendar-shape and
  invalid-token refusal cases with a load-bearing structured comparison: the set
  on `_LedgerPeriodRefusal.accepted_period_tokens` versus an independently derived
  `_expected_span_shaped_tokens()` (the enum plus the span rule, never the refusal
  message). One thin `1T` / `--year` check per case keeps the human refusal
  instructive.
- Add `test_period_refusal_advertises_accepted_tokens_on_error_envelope`: a real
  cached-CLI `--format json` refusal whose `error.context.accepted_periods` is
  parsed and compared against the derived set, proving the carrier reaches the
  operator-facing envelope, not just the exception.
- Fix the coverage gap: extend `_TOKEN_YEAR_SPAN` from 8 to all 17 span-shaped
  tokens (the nine month tokens `02 04 05 06 07 08 09 10 11` were unexercised;
  `02` ends on the leap-year 29th) and add
  `test_token_year_span_table_exercises_every_span_shaped_token` asserting the
  table covers exactly the derived span-shaped set.

## Outcome

Command:
`uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_period_grammar.py -m integration -n0 -p no:cacheprovider`

`collected 20 items`; exit line `============================= 20 passed in 10.45s =============================`; exit code 0. Run against HEAD `a868582fc26403720df2eb3d62954a7caacacb42`.

Re-verified at the committed HEAD after landing: same command reports `collected 20
items`, `============================= 20 passed in 9.62s =============================`,
exit code 0, at HEAD `561388a9be7143987c119dbe87394aba65067a78` (parent
`d53a0f0556a28a2926a9b77fb46db85906458323` — a peer commit landed between the first
measurement and this one, touching none of the subject files).

Every added assertion was mutation-checked in an in-process probe rebinding module
state (no file edit, no transient red for peers):

- Dropping `0A` from the production advertised set REDS the structured comparison
  in both refusal cases (`RED (caught)`).
- The same mutation REDS the integration envelope-context comparison
  (`RED (caught)`).
- Dropping a `_TOKEN_YEAR_SPAN` row REDS the coverage equality (`RED (caught)`).

Wording-independence proof: rewording the `period_unrecognised` prose to a string
carrying no grammar left the structured carrier unchanged
(`structured-unchanged=True`), while the thin human-instructiveness check reds on a
reword that drops `1T` (`thin-prose-check-reds-on-reword=True`) — confirming the
load-bearing assertion is off prose and the thin check is deliberately
wording-sensitive.

Regression sweep (`test_parse_time_refusal_localisation`, `test_localised_parser_errors`,
`test_common`, `test_backend_boundary`, `-m "unit or integration" -n0`): `collected 42 items`,
`42 passed`, exit 0 — the shared `_terminal_errors` and `_common` edits carry no
regression. Gates: `ruff check` and `ruff format --check` clean; `ty check` and
`pyright` both report zero diagnostics on the three touched files.

## Notes

The refusal is a body-raised `typer.BadParameter`, which under the cached CLI runner
reaches the JSON envelope path through `CadrumoTyperGroup.main`
(`standalone_mode=True`) into `run_standalone_with_error_contract`, so the
integration proof exercises the real terminal handler. No locale change was needed —
the accepted set travels as data, and the existing `period_unrecognised` message is
unchanged. No skips, xfails, mocks, or scaffolds left in code.

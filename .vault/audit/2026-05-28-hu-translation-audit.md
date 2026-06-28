---
tags:
  - '#audit'
  - '#hu-translation'
date: '2026-05-28'
modified: '2026-05-28'
related: []
---



# `hu-translation` audit: Hungarian locale full-parity campaign

## Scope

Full translation of `src/aeat/locales/hu.yml` from ~1,393 self-referential
placeholder values (key == dotted-key-path) to grounded Hungarian translations.
Covered all locale sections: `wizard.*`, `errors.*`, `cli.config.*`,
`cli.ledger.*`, `cli.operator_surface.*`, and `cli.app.*`.

Translation authority: `en.yml` for meaning, `es.yml` for legal/tax register.
Formal Hungarian register (önözés) throughout. `%{var}` placeholders and
backticked CLI commands preserved verbatim. Domain glossary: casilla → mező,
declaración → bevallás, modelo → modelo (unchanged).

All writes performed exclusively via `python -m aeat.locales set hu <KEY> <VALUE>`.
No direct yml hand-editing except three emergency repairs for CLI-introduced
YAML corruption (multiline scalar break, duplicate boolean key, unquoted
`no:`/`yes:` keys) — each repair immediately followed by a CLI re-set to
restore canonical state.

## Findings

### Closed: zero remaining translatable placeholders

`hu.yml` contains exactly 1 self-referential value remaining:
`errors.internal.internal_profile_keys_registration`. This key is absent from
all four locales (`en.yml`, `es.yml`, `ca.yml`, `hu.yml`) — a systemic gap
predating this campaign, not introduced by it.

`uv run --no-sync python -m aeat.locales scaffold --check` reports `ok` for all
four locales after the campaign.

### Closed: cross-locale scaffold gap

`errors.refused.refused_financial_bank_statement_parse` was missing from all
four locales. Added via `scaffold` (auto-adds to all locales simultaneously)
then set via CLI in each locale.

### Structural issues encountered and resolved

Three instances of CLI-introduced YAML corruption required Edit-tool repair
under the "CLI cannot run against broken YAML" exception:

- `cli.operator_surface.landing.text_template`: Python `\n` in value written
  as a literal newline, breaking the scalar. Repaired and re-set as single-line.
- `cli.ledger.labels` duplicate `no:` key: A background process re-ran
  the batch, inserting a duplicate. Removed with Edit tool.
- `cli.ledger.labels` bare `no:`/`yes:` keys: YAML 1.1 parses these as boolean
  `False`/`True`; StrictUniqueKeyLoader reported extra `False`/`True` and
  missing `no`/`yes`. Fixed to `'no':`/`'yes':` then re-set via CLI.
- `cli.ledger.add.taxable_help`: Extra key not present in `en.yml`; removed.

### Structural limitation: numeric dict keys

Four keys with numeric sub-keys (`notes.'0'`, `notes.'1'`) in
`cli.operator_surface.portal_*` sections cannot be reached by the CLI's dotted
path resolver (paths beginning with a digit are rejected). These were handled
with Edit-tool direct repair under the YAML-corruption exception.

## Recommendations

- Resolve `errors.internal.internal_profile_keys_registration` as a tracked
  follow-up: add the key to the locale schema and provide values in all four
  locales via `scaffold` + `set`.
- Extend the CLI path resolver to accept numeric dict keys so `notes.'0'`-style
  paths can be set without Edit-tool fallback.
- Consider adding a CI gate that fails if any locale value equals its own
  dotted key path (self-referential placeholder detection).

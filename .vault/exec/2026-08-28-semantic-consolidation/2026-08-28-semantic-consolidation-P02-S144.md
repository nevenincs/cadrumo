---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:7414d9890f0e9decab984e35791ab3e73585e6e0afc4e97360fa81b931bb504c'
step_id: 'S144'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Measure CLI model redefinition by field-set containment rather than searching for it, and retire the third currency declaration the earlier consolidation missed

## Scope

- `src/cadrumo/application/ledger/models.py`
- `src/cadrumo/entrypoints/cli/_ledger_payloads.py`

## Changes

- `M` `src/cadrumo/application/ledger/models.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `verify:` probed both currency types on EUR / eur / " EUR " / 12A / USD / EURO
- `verify:` searched the tree for currency literals; only refusal-test values are non-alpha

## Notes

Sentinel yield on "find duplicated X" had gone to zero across two rounds, so the
method changed rather than the wording. The campaign names MODEL REDEFINITION as
a headline target, and semantic search is the wrong instrument for it: two models
that redefine each other share FIELD NAMES, not prose, and RAG ranks meaning in
text. So it was measured -- every pydantic model under entrypoints/cli compared
field-set against every model in application/ and domain/, ranked by containment
of the CLI model in the inner one, envelope fields excluded.

297 pairs at 75% or better. The top is 100% containment over 31 fields with
nothing CLI-only: LedgerExportRowPayload against LedgerExportRow.

Reading that pair turned up a THIRD currency declaration, which an earlier round
of this same campaign had missed while consolidating currency at three sites:
`CurrencyCode` in application/ledger/models.py, length-only, three characters.
Probed against the canonical `IsoCurrencyCode`:

- `"eur"` -> the ledger alias keeps `"eur"` unnormalised; canonical gives `"EUR"`
- `" EUR "` -> the ledger alias REFUSES (padding breaks the length bound);
  canonical normalises to `"EUR"`
- `"12A"` -> the ledger alias ACCEPTS a value that is not a currency

The padding case is the one the canonical normaliser's own docstring warns
about, and the local alias had walked straight into it. Retired; four fields
repointed, including one CLI payload that was importing the loose alias while
its sibling in the same module already used the canonical one.

Checked before tightening: the only non-alpha currency literal anywhere in the
tree is a refusal-test value both types reject.

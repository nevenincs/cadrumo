---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:4b6b87c36dcd326cce93310d7d8226d23dcc69ee918d55d28970c21c9fb046c3'
step_id: 'S137'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Scope

- `src/cadrumo/_data/registry`
- `src/cadrumo/domain/iva`

## Description

- Add `registry/aeat/iva/country_names.toml`: 58 countries, 169 printed names, mapping each name to its ISO 3166-1 alpha-2 code.
- Add `country_code_for_printed_country_name` and `territorial_scope_for_printed_country_name` to `src/cadrumo/domain/iva/_establishment.py`, beside the existing code and postal rungs.
- Split the vocabulary indexing into `_index_country_names`, so its refusals are reachable with a payload rather than only with the bundled file.
- Reuse the canonical `fold_diacritics` primitive from `src/cadrumo/core/text_fold.py` rather than hand-rolling a second NFKD strip.
- Promote both functions to the `domain.iva` facade in the same commit.
- Add `src/cadrumo/domain/iva/tests/test_printed_country_name.py`.

## Outcome

The name rung lands as a callable unit; the ladder assembly is deliberately not wired here.

The canonical home turned out to be `src/cadrumo/domain/iva/_establishment.py`, not `application/ledger` as the dispatch scoped it. That module already holds the other two rungs of the same ladder and already owns the "printed country evidence to territorial scope, or to nothing" question, including the documented refusal to resolve a Spanish code. Splitting the third rung into another package would have put two owners on one question.

The rung is a composition, not a second rule set: the name lookup answers "which country was printed", and the pre-existing country resolver stays the single authority on "what does that country establish". A Spanish name therefore resolves the code and no scope, which is the existing design rather than a gap in this one.

Vocabulary decisions, all argued in the table's own header:

- Languages, three. Spanish; the country's own name, every official one where a country has several; English, because a Dutch or Polish supplier billing a Spanish customer commonly prints the whole document in English. French, German and Italian exonyms for third countries were excluded as unreviewable for a population that barely exists.
- Countries: every EU Member State, plus the third countries a Spanish taxpayer's invoices realistically carry (European non-EU neighbours, the large trading partners, Latin America). The remaining sovereign states are excluded because a general country database is unreviewable and a missing country degrades safely to "not established".
- Sub-national names excluded. Northern Ireland is the case that proves it: an address there prints "United Kingdom", and the Protocol jurisdiction is established by a printed NIF-IVA prefix or not at all, so no name maps to XI.
- Bare alpha-2 codes excluded; those are the code rung's input and two authorities on one string is one too many.

Normalisation ruling: case fold, whitespace collapse, accent fold, and nothing else. Punctuation is deliberately kept, because the vocabulary carries "EE.UU." with its stops. Matching is EXACT after normalisation, never containment: a country is a field value rather than a phrase in prose, and containment would resolve "Nigeria" as Niger and "Papua New Guinea" as Guinea. Accent folding is only sound while no two different countries fold together, so that is enforced rather than assumed: the loader refuses the whole table when two codes claim one folded name.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/iva/tests/test_printed_country_name.py -n0 -q -m "unit"
    67 passed in 1.03s

Sibling and structural gates, sequential:

    uv run --no-sync pytest src/cadrumo/domain/iva src/cadrumo/tests/test_import_hygiene_gate.py src/cadrumo/tests/test_docstring_core_struct_links.py -n0 -q
    5 failed, 539 passed in 168.96s (0:02:48)

The whole IVA domain suite is green. The five failures are all outside this surface and are peer churn: three import-hygiene failures naming new test-only private reaches in `application/aggregation`, `application/ledger`, `domain/invoices` and `entrypoints/cli` against `llm` and the registry loader, and two docstring core-struct link failures naming eight modules in `application/calculations`, `application/ledger`, `application/modelo` and `entrypoints/cli`. No failure names this Step's files, and this Step adds no cross-package private reach and no core-struct use.

    uv run --no-sync ruff check <changed files>          All checks passed!
    uv run --no-sync ruff format --check <changed files> 2 files already formatted
    uv run --no-sync ty check <changed files>            All checks passed!

Mutation proof, four mutations applied from outside the repository at pytest plugin module scope, each rebinding the production symbol on both the private module and the facade:

- Miss defaults to Spain: `31 failed, 36 passed`.
- Exact match becomes containment: `5 failed, 62 passed`.
- Accent folding removed: `9 failed, 58 passed`.
- Collision check dropped from the loader: `1 failed, 65 passed`.

The remaining tests stay green legitimately in each case. Under the Spain-default mutation the passing set is the positive lookups and the loader refusals, neither of which the miss path touches. Under the containment mutation the positive lookups still resolve because containment is a superset of exact match; the near-miss class is what reddens. Under the fold mutation only the accent-dependent inputs and the collision probes red, because every other name is already ASCII. Under the collision mutation exactly one test reds, which is the whole surface that check has.

## Notes

The accent-folding mutation initially reddened only two loader tests and none of the ASCII-variant tests, because the first draft of the table listed both spellings of every accented name. Both spellings resolved with the fold removed, so the variant tests were passing on the data while the behaviour they named was gone. Corrected by removing all 26 fold-duplicate spellings and adding a gate that refuses any name another name in the same record folds onto, so the redundancy cannot return and quietly disarm the check. The mutation then reddened nine tests including the variant class. Recording it because the brief's warning was exactly right: an inert mutation meant the corpus could not discriminate, not that the gate was sound.

No new `tr()` keys, so no locale catalogue work.

Two languages a real invoice can print are knowingly not covered and degrade to "not established" rather than to a wrong answer: an exonym in a fourth language (an Italian supplier printing "Germania"), and a non-Latin script beyond the four endonyms carried (Greek, Bulgarian, Russian, Ukrainian, Serbian, Chinese, Japanese). Both are additions to the table alone if the population turns out to warrant them.

The ladder assembly is not wired, per the dispatch. Nothing consumes either new function yet.

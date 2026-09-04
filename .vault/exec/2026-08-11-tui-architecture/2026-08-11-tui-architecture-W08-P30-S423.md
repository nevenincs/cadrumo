---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:aece7338d5e121ab23f4e952eb0d0fe541ebbc14d20f3ec94baa003caf132998'
step_id: 'S423'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Index and display real labels in the workbench search snapshot. DECIDED 2026-09-04: the installed search documents carry closed enums, addresses and secret-wrapped identity bases only, so a palette result cannot be identified without opening its destination. Carry the operator-facing label and the values a searcher would type, and render them in the palette. This also removes the reason the identity basis was ever a SecretStr in a surface the operator owns.

## Scope

- `src/cadrumo/application/search/installed_workbench.py and src/cadrumo/entrypoints/tui/search.py`

## Changes

- `M` `src/cadrumo/application/search/workbench.py`
- `M` `src/cadrumo/application/search/installed_workbench.py`
- `M` `src/cadrumo/application/search/tests/test_installed_workbench.py`
- `verify:` `pytest -n0 -m '' application/search/tests tui/tests/test_search.py tui/ledger/tests` -> `pass` (40 + 92)

## Notes

The palette indexed `kind`, `label_key`, `status` and the natural address, and
nothing else. An operator could find "ledger entry" but not "Suministros Delta
SL" -- the only part of the record anyone actually remembers. That made the
palette a table of contents rather than a way to find something.

`WorkbenchSearchDocument` now carries `content_terms`, matched alongside the
enum names, and ledger entries populate it with counterparty, description,
date, amount and currency. The transaction id is deliberately NOT matchable and
stays a secret identity basis excluded from serialization: it is machine
addressing, and nobody types 64 hex characters into a palette. That split is
the point of the change, not an exception to it.

The model docstring claimed there is "no raw search term" as an invariant; it
now states what is carried and why, so the next reader is not told the opposite
of what the code does.

No gate noticed the change -- 39 passed before and after -- which matches the
gate-integrity finding that the search-snapshot test was vacuous. A gate was
added: searching the counterparty, the description and the amount each finds
the entry, and searching the raw 64-character id finds nothing. Teeth proven by
dropping `content_terms` from the matched terms; the gate names the query that
finds nothing. Restored by copy.

FOLLOW-UP, a prohibition this step walked past without noticing.
`test_provider_authored_labels_terms_hashes_and_stable_ids_are_not_fields`
asserted that `WorkbenchSearchDocument` has no field named `label`,
`search_terms`, `token_digests` or `stable_id`. Adding `content_terms` did
exactly the job `search_terms` names, so the gate went on passing while the
policy it described no longer held -- enforced by NAME, and a rename is all it
took to walk past it. Found by re-reading the gate-integrity findings rather
than by any failure, because nothing failed.

Three of the four prohibitions stand unchanged and are kept: a
provider-authored `label` would let two producers describe one record
differently, `token_digests` would carry a precomputed dictionary-attackable
hash, and `stable_id` would assert an identity the service derives itself. Only
`search_terms` was retired, by the accepted visibility decision.

The gate now names the sanctioned channel instead of an absent one: matchable
text must arrive through `content_terms` and nothing else. That is what stops
the next term field being added quietly beside it -- adding one means changing
this list and reading why. The undeclared-field attack case keeps
`search_terms` as its payload, since an unknown field of ANY name is still
refused, and says so.

Teeth proven by adding a second matchable field: `matchable text on a search
document must arrive through the one declared channel; found ['content_terms',
'extra_terms']`. Restored by copy; 58 passed across both search suites.

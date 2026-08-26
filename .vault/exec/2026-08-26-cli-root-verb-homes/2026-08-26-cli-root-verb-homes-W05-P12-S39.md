---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:569e6020140edbfc9a8201975cef8661cb7f4501807ccdc0baf4eee7072a46c9'
step_id: 'S39'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Land the verb-grammar gate D6 promised and never shipped, scoped to the decidable half, and prove it bites

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Changes

- `A` `src/cadrumo/entrypoints/cli/tests/test_transport_verb_grammar.py`
- `verify:` `pytest test_transport_verb_grammar.py` -> `pass`
- `verify:` `scratchpad proof: retired token, second file leaf, locus compound, empty graph` -> `pass`

## Notes

D6 promised a gate refusing a transport verb outside the four tokens and W05.P12
shipped only the spelling half. This closes it, scoped to the decidable part: a
leaf that DECLARES a transport locus must not wear a retired token. Whether a
given creating or computation verb should really have been a transport verb is
author judgement and is deliberately not gated -- `config google probe` and
`config google folder get` both carry retired tokens and both pass, because
neither declares a locus.

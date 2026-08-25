---
tags:
  - '#exec'
  - '#dehu-notification-legal-effect'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:c13411aa6d858107599681b3b56a50a97541f5e98584c79160360e29c69df096'
step_id: 'S11'
related:
  - "[[2026-08-07-dehu-notification-legal-effect-plan]]"
---

# Add the catalogue-resolution grounding test asserting the DEHU_RECHAZO_TACITO_DIAS_NATURALES doc citation resolves against the operator-reviewed ley-39-2015 art-43.2 legal catalogue entry, following the existing test_external_constants_centralisation_part2.py pattern, and extend the constant's doc comment to name that entry id only once the entry exists on disk. This is the half of the original S04 row that genuinely depends on the human review gate, split out so the constant itself is not held behind it. Read the entry id off the COMMITTED registry TOML, never off external_constants.py. The constant's current comment cites only the provision and its BOE document id, so there is no id already present there to check a new one against, and an id copied from the wrong surface would resolve to nothing while reading as grounded. The corrected P01.S02 draft spells it ley-39-2015 colon art-43.2. Blocked on P01.S03

## Scope

- `src/cadrumo/core/external_constants.py`
- `src/cadrumo/core/tests/test_external_constants_centralisation_part2.py`

## Description

- Extend the constant's doc comment to name `ley-39-2015:art-43.2`, reading the
  id off the committed registry TOML rather than off any prose that describes
  it, and state that the quoted Spanish clause is the entry's own corpus text
  rather than a restatement of it.
- Add a grounding test that recovers the `#:` doc-comment block from the source
  text (doc comments are not AST nodes), extracts the backtick-quoted catalogue
  id, resolves it against the registry legal catalogue, and runs the same
  verification registry build applies.
- Bind the constant's VALUE to the provision by looking the value up in a
  Spanish-cardinal map and demanding the corpus state that cardinal, so the
  number cannot drift off the law it cites.

## Outcome

`DEHU_RECHAZO_TACITO_DIAS_NATURALES` is a bare `10` in source. What separates it
from a magic number is the provision its comment names, and until this Step that
naming was unchecked prose: the id could have been absent, wrong, or retired and
the constant would have read as grounded either way.

The test deliberately does not assert `10 == 10` against anything derived from
the constant. Its terminal assertion asks the CORPUS whether it states a "diez
dias naturales" window, with the cardinal chosen by the constant's own value.
Change the constant to 15 and the test asks the corpus for "quince dias
naturales", which Ley 39/2015 art. 43.2 does not say, and the gate reds. That is
the property the rule against tautological calculation tests is asking for: the
test fails when the code is wrong against the external authority, not when it
disagrees with itself.

The cardinal map is bounded and its absence is a hard failure with an
instructive message, so a future window length no map entry covers refuses
rather than silently skipping the grounding assertion.

## Verification

    uv run --no-sync pytest src/cadrumo/core/tests/test_external_constants_centralisation_part2.py -q -p no:randomly
    15 passed in 95.95s

Mutation proof, run from OUTSIDE the repository against scratch copies of the
source; no tracked file was edited.

    [id_removed]         RED as expected: must name exactly its legal-catalogue entry ...; found []
    [id_wrong]           RED as expected: ... found ['ley-39-2015:art-99.9']
    [quote_paraphrased]  RED as expected: the clause quoted in the doc comment is not present in the corpus
    [constant=10]  corpus states 'diez dias naturales':    True  -> grounded
    [constant=15]  corpus states 'quince dias naturales':  False -> RED (ungrounded)
    [constant=30]  corpus states 'treinta dias naturales': False -> RED (ungrounded)

    uv run --no-sync ruff check src/cadrumo/core/external_constants.py src/cadrumo/core/tests/test_external_constants_centralisation_part2.py
    All checks passed!

## Notes

The wrong-id mutation reds on the exact-id equality rather than on catalogue
resolution, because the test pins the single expected id instead of accepting
any resolvable one. That is the stronger contract for a constant with exactly
one governing provision, and it was kept deliberately: a test that accepted any
resolving id would pass on a citation to an unrelated article.

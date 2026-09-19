---
tags:
  - '#exec'
  - '#dehu-notification-legal-effect'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:44025624a04bc86f159a4a2117d1344cb3349625f1e131676737ef0c6c1286c0'
step_id: 'S04'
related:
  - "[[2026-08-07-dehu-notification-legal-effect-plan]]"
---

# Add DEHU_RECHAZO_TACITO_DIAS_NATURALES as a Final int equal to 10 to external_constants.py, doc-commented with the Ley 39/2015 art. 43.2 provision citation and its BOE-A-2015-10565 document id in the same style as every sibling leaf constant in that file, and deliberately NOT naming any legal-catalogue entry id, because an entry id cited before the catalogue file exists ships a dangling reference into production source. Verified by the constant importing cleanly and by the external-constants centralisation AST gates staying green

## Scope

- `src/cadrumo/core/external_constants.py`

## Description

- Pin the Ley 39/2015 art. 43.2 rechazo-tacito window as a `Final[int]` leaf
  constant beside its sibling statutory constants, doc-commented with the
  provision, its `BOE-A-2015-10565` document id, the operative clause quoted
  verbatim, and the dias-naturales-not-habiles caveat plus the direction of
  error a dias-habiles reading would produce.
- Deliberately cite no legal-catalogue entry id. The catalogue file does not
  exist yet, so naming its id would ship a dangling reference into production
  source; that citation belongs to the row that lands the grounding test after
  the human review.

## Outcome

`DEHU_RECHAZO_TACITO_DIAS_NATURALES: Final[int] = 10` is defined in
`src/cadrumo/core/external_constants.py`. The doc comment cites the provision
and the BOE document id only, at parity with every sibling leaf constant in
that file, none of which resolves a catalogue entry id either.

Independently of the bundled corpus, the figure was cross-checked against the
live BOE consolidated act page: all six bundled art. 43 paragraphs matched
verbatim after entity and whitespace normalisation, the window reads
"diez dias naturales", and the article contains neither "dias habiles" nor
"quince dias". The page carries seven per-block amendment annotations, none on
art. 43, but per-block annotation is demonstrably incomplete, so no claim that
art. 43 is unamended since 2015 is made or implied here.

## Verification

    uv run --no-sync python -c "from cadrumo.core.external_constants import DEHU_RECHAZO_TACITO_DIAS_NATURALES as d; print('constant', d, type(d).__name__)"
    constant 10 int

    uv run --no-sync pytest src/cadrumo/core/tests/test_external_constants_centralisation_part1.py src/cadrumo/core/tests/test_external_constants_centralisation_part2.py -n0 -q
    26 passed in 38.14s

    uv run --no-sync ruff format --check src/cadrumo/core/external_constants.py
    1 file already formatted

    uv run --no-sync ruff check src/cadrumo/core/external_constants.py
    All checks passed!

## Notes

The constant ships before any human has signed the provision behind it. That
is the deliberate consequence of the amendment splitting this row's original
form, and the amendment states beside itself what the original hard-blocking
formulation still asks for that the split excludes. The live-BOE cross-check
above narrows the exposure; it does not substitute for the review, which
remains required and unperformed.

---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S06'
related:
  - "[[2026-06-13-modelo-130-pagos-fraccionados-carry-plan]]"
---




# ground the casilla 05 binding and formula source_citations in the verbatim AEAT instrucciones casilla-05 definition with required_text drawn from the suma-de-las-cantidades-positivas-casilla-07-minorada-casilla-16 quote, per registry-calculation-legal-grounding

## Scope

- `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0001-bindings.toml`

## Description

- Grounded the binding `source_citations` in the verbatim AEAT Modelo 130 instrucciones casilla-05 definition with `required_text` covering the suma-de-cantidades-positivas-casilla-07, minorada-casilla-16, and no-se-computaran-cantidades-negativas quotes.
- Confirmed the quotes normalise (html unescape + NFKD mark-strip + lowercase) to the committed corpus text in `modelo-130-instrucciones.html`.

## Outcome

The casilla-05 binding clears the legal-grounding evidence gate (`test_catalogue_verification.py`, 35 passed). Landed in commit `a67b77c87`.

## Notes

The negative-cantidades quote uses ASCII computaran against the corpus computar&aacute;n; both normalise identically through `normalise_corpus_text`.

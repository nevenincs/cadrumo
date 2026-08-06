---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:b5485b5ce1192c16c96859b8ca293c794d132cca90a9a64cc6048b5a5daaeefd'
step_id: 'S10'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Confirm the autonomico aggregate and the anualidades eligibility flag are both corrected by the same predicate change

## Scope

- `src/cadrumo/application/modelo/tests/`

## Description

## Outcome

One predicate change corrects three consuming surfaces, and this Step made that explicit and
gated rather than leaving it as an observation.

The same ordinary-eligibility test feeds the estatal aggregate, the autonomico aggregate and
the anualidades separate-escala flag. All three were measured against the corrected
predicate: a descendant above the Art. 58.1 ceiling contributes zero to both aggregates
across every revision 2020-2025, and the anualidades flag reads sin derecho for that same
descendant where it previously read eligible.

The anualidades correction moves in the opposite direction from the other two and is worth
naming for that reason. The other surfaces over-granted, which under-declares tax. This one
denied a regime the filer was entitled to, which over-taxes. Both are defects and both are
closed by the same change, which is the argument for having fixed the predicate rather than
its three consumers.

Gates ran green across the corrected surface: the oracle module at nine, the contribuyente
suite at one hundred and ninety, locale parity and translation honesty at thirty-nine, and
the external-oracle enrolment gate at three.

Four failures in the broader sweep were correctly attributed rather than absorbed. The
executor proved they were pre-existing at the pinned head by showing the file they blamed
contains no reference to the removed emitter there, and that its own copy was byte-identical
to head. It declined to repair them on the grounds that the decision belonged to whoever
removed the emitter and guessing would undo in-flight work. That attribution was correct: the
removal was the coordinator's, and the four cases were repaired separately so each now pins
the per-child figure the injector reads and the aggregate's absence, rather than simply
dropping the assertion.

## Notes

---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:155694fd1bc720228835a07b62f74967f2e645f83de376a2153cd88fbc49b3d6'
step_id: 'S22'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Require Modelo 303 result_disposition before any filing persistence write

## Scope

- `src/cadrumo/application/modelo/_revision_persistence.py`

## Description

- Extract the existing Modelo 303 disposition requirement into a named callable.
- Call it as the first statement of the filing transition, ahead of every
  builder and every repository write.
- Retain the original downstream call, which other callers reach directly.

## Outcome

Landed in `69d130c`. Its proof is part of the sibling row, which was held at the
time and is recorded there.

The requirement was not missing. It existed, was correct, and ran too late: the
filing transition wrote the filing catalogue, advanced the WorkUnit pointer, and
wrote the participation index, any prorrata writeback and the filed events before
reaching the observation write where the check lived. A filing refused there had
already been filed. The row always said "before any filing persistence write",
which is exactly the ordering fix; what made it read like an absence row is that a
guard existed ELSEWHERE and looked like it satisfied the requirement.

That is worth generalising: the question a row asks is not always whether an
artefact exists. Here existence was never in doubt and position was the entire
defect.

The condition was extracted rather than copied. Two inline copies would be two
authorities on when a filing is under-declared, and they would drift. The
preflight is gated on the same observation-repository condition as the downstream
check, so the SET of filings required to carry a disposition is unchanged and
only the timing moves.

It remains a presence requirement and never a second derivation. The disposition
is a determined fact resolved once at the calculate/file boundary; recomputing it
at the write site would make a regulated determination answerable in two places,
which is how the fichero an operator submits and the carry a later period reads
come to disagree.

## Notes

Landed without its paired proof, deliberately and reported as such at the time:
the proof row was held pending a design ruling on its sibling, and part-proving it
would have asserted a contract whose scope was still unruled.

The owning package was carrying heavy peer work in progress; the commit used an
explicit pathspec and its file list was verified after the fact.

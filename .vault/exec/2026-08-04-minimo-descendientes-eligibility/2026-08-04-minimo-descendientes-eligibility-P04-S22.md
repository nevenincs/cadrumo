---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:1c454dd689f02494c0de7eb76105c8d598b5e8ad1700387687d1e4aa02d21d73'
step_id: 'S22'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Connect or retire the declared maternidad months, because an operator declaring MESES_TRABAJO through descendiente add or the guided flow gets nothing, the fact round-trips and rides the payload and is declared in the user-profile schema as a model selector while no formula targets casilla 0611 and no binding names the path, so a documented entry surface is today lying about what it does whichever way S21 resolves

## Scope

- `src/cadrumo/application/modelo/_calculate_input.py`
- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `src/cadrumo/entrypoints/cli/_config/_descendiente.py`

## Description

Add `maternidad_contributing_meses` to the descendant record, gating the declared
employment months on the Art. 81.1 population the record already computes.

Add `meses_maternidad_por_descendiente` to the family profile, pairing each
contributing descendant's index with its months so the deduccion's per-hijo cap
applies over pairs rather than a collapsed total.

Read those pairs on the calculate path, gated on the revision declaring the
maternidad semantic role, so no other modelo pays for a profile load it cannot use.

Refuse the calculate-time flag when the declared records already carry months,
with a translated refusal in all four catalogues.

Disclose months withheld on eligibility grounds as a non-blocking advisory.

Correct the flag help in all four catalogues, and the test docstring that recorded
the eligibility gap this Step closes.

## Outcome

The declared months reach the casilla. An operator who states MESES_TRABAJO through
the descendiente verb now changes a computed value, which is the criterion; the
surface no longer documents a record it discards.

The child-side condition is engine-derived and the employment months stay the
operator's, which is the split the authority draws rather than a preference between
two designs. Aggregation runs through the canonical family record, so this path
cannot acquire the second aggregation loop that broke the guarderia half.

Verified end to end through the real CLI in the integration lane against the AEAT
Renta 2024 manual's printed worked example for two mellizos with twelve qualifying
months each: 1.200 per hijo, 2.400 total. A mutation severing the connect drops the
casilla to zero and dissolves the refusal, so neither gate is keyed on a constant.
Domain, application and CLI conformance suites are green in both lanes.

## Notes

Two authorities now exist for one casilla only in the sense that either may act
alone; they are refused together. That is the guarderia annual-versus-monthly
precedent applied to a second value, and it is a narrower answer than retiring the
flag. Retirement remains the cleaner end state and is reported as a follow-up
rather than taken here, because it is a fifteen-file sweep across four catalogues
and does not belong inside a precondition Step.

The casilla stays an operator-supplied input rather than becoming registry-computed,
which leaves its sibling guarderia increase computed by a registry formula while
this one is computed in Python. That asymmetry is real and predates this Step. It is
reported rather than closed, because closing it forces the flag retirement above.

The full-tree import-linter gate is red at HEAD on two contracts, every broken chain
running from a `cadrumo.core.*.tests` module into the shared test package. No file in
this Step appears in the broken set, and the root module is clean in the working
tree, so the breakage is pre-existing and owned elsewhere.

A bundled AEAT worked example surfaced while grounding the test expectations and
carries a measured finding beyond this Step's scope: the month in which the mother
completes the thirty-day minimum contribution period adds 150 euros, and the
per-hijo limit in that case is 1.350 rather than 1.200. The shipped cap constant is
1.200 unconditionally. Direction is under-grant. Recorded for a Step of its own.

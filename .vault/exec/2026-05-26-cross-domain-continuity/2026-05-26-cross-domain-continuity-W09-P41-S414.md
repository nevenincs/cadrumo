---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-17'
body_hash: 'sha256:af84415e56e17f00cc6e4345d0cded23dc2edff39f015014e04e3edd41a428f4'
step_id: 'S414'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# add the non-blocking M100 omission advisory that fires when attribution_received facts exist for the filing year but the atribucion casillas resolve empty (and prompts capture when an SC-membership signal exists with no facts), with an anti-tautology test

## Scope

- `src/aeat/application/modelo/_attribution_received_advisory.py`
- `src/aeat/application/modelo/_verification_actions.py`
- `src/aeat/application/modelo/tests/test_attribution_received_advisory.py`
- `docs/how-to/review-calculation-values.md`

## Description

- Add `_attribution_received_advisory` following the per-concern advisory-module pattern (mirroring `_objective_estimation_advisory`): resolve the M100 atribución casilla structurally by its `semantic_role` (`irpf_rendimiento_act_eco_atribuido_rdto_neto`, unique in both the 2024 and 2025 revisions), load the active `UserProfileRecord`, and read the `attribution_received.N.*` facts filtered by filing year.
- Emit two symmetric non-blocking `ModeloVerificationFinding` warnings: captured-but-unfolded (facts declare a base for the year, casilla resolves empty) and declared-but-uncaptured (casilla carries a value, no facts back it — prompts profile capture). Ground both on LIRPF arts. 86-89.
- Wire the advisory into `_append_revision_advisory_findings` beside the reduction/objective-estimation advisories (no signature change — `work_unit` + `snapshot` + `target.casilla_values` already in scope).
- Add an anti-tautology test that flips exactly one input at a time (facts vs casilla) and asserts the finding count flips with it, plus scope-out and other-year cases.
- Document the manual `--binding` handoff for socios in `review-calculation-values.md` (inline code, reusing the documented `aeat app modelo work calculate` verb).

## Outcome

Committed via the S414 explicit-pathspec retry (SHA recorded on the coordinator STOP report). Gates green (-n0): 7 advisory tests + 315 verification/advisory suite (no regression from the composition wiring) + 60 documented-command conformance; ruff + ty clean. This is the `no-silent-under-declaration` guard for the manual cross-bucket socio-attribution handoff decided by the m184 ADR addendum (decision (a)): a forgotten transcription in either direction surfaces loudly.

## Notes

- Implements the m184 ADR addendum decision (a): casilla 1577 stays relation-canonical (no `source = "profile"` binding), the cross-bucket attributed value enters via manual `--binding`, and this advisory + the S413 handoff Notice keep the handoff non-silent.
- Trigger 2 reads an in-bucket "SC-membership signal" as a value on the atribución casilla with no backing `attribution_received` facts — the profile in the socio's own bucket carries no other cross-bucket membership signal (no cross-bucket read, per the addendum).
- The full Sphinx `-n -W` build (a tens-of-minutes gate) was not run for the one-paragraph how-to addition; the documented-command conformance gate is green and the note adds no new cross-references or directives.

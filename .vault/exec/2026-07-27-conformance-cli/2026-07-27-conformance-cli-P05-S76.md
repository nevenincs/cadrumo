---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:a3212466f2784e3bb0ce1b81731eccc15d0f1c7c11459a83f1ab899c39a11d3b'
step_id: 'S76'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# open a follow-up feature tracking the four measurement-audit recommendations so ninety unreviewed revisions, twenty-four classification divergences and five unused schema axes have an owner rather than living as prose

## Scope

- `.vault`

## Description

- Open a follow-up feature so the measurement's four recommendations have an
  owner rather than living as prose in an audit.
- Ground each one against what the tool actually reports, and state what must be
  decided before any of them can start.
- Enter the pipeline at Research rather than scaffolding a plan, because two of
  the four are decision work rather than execution.

## Outcome

The four recommendations are grounded as a `registry-governance-backlog`
research document. Grounding them changed their shape, which is why this was
worth doing rather than transcribing a list.

Exactly one is mechanical: the grounding sweep for casillas whose figure a
bundled oracle already states and the engine already reproduces. Those are free
enrolments needing no new evidence, and the campaign closed one as a worked
example.

Two cannot be batched at all. The 24 classification divergences are 24 per-modelo
judgements, because the two axes are not redundant labels — one is an enforced
posture and the other a bare label, so a mechanical alignment would either impose
an invariant a modelo cannot satisfy or strip one it should carry. The five
unused schema axes are five independent rulings, each either a gap in the data or
a surface that should not exist, and the report cannot distinguish those.

The fourth is blocked. A stamping pass moves the population-pinned governance
ceilings on every commit, and re-recording is refused without the flag that means
"I am weakening the ratchet" — so the campaign would assert a weakening on every
honest stamp until that Step lands.

## Notes

Written by the coordinator, and deliberately as Research rather than as a plan:
scaffolding a plan would have implied the work is understood well enough to
sequence, and two of the four items are decisions that have not been taken.

The stamping pass is constrained by a decision the conformance campaign already
made and should not be relitigated here: the CLI cannot write an operator
signoff, because an agent asserting that a human reviewed something is the
dishonesty the provenance feature exists to detect. So the pass splits into an
agent-tier campaign the tool can run and operator attestation that stays a hand
edit.

Two questions are named as uninvestigated rather than assumed: whether an
agent-tier stamp should record the campaign or the agent, and whether the
grounding sweep should prefer breadth or depth. Both belong in the follow-up
feature's ADR.

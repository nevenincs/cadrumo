---
tags:
  - '#exec'
  - '#evidence-revision-identity'
date: '2026-07-25'
modified: '2026-07-26'
body_hash: 'sha256:7b64f641c3078646b503bd47987d3874be5fc4500ef4a60b081c79045de2189f'
step_id: 'S03'
related:
  - "[[2026-07-25-evidence-revision-identity-plan]]"
  - "[[2026-07-25-evidence-revision-identity-supersede-implementation-findings-audit]]"
---

# BLOCKED ON OPERATOR, the supersede transition as specified cannot be built, it carries the same inputs so it re-derives the id it is escaping and hits the amendment path's existing no-op refusal, and the escape requires a discriminator inside revision identity which this ADR reserves for operator sign-off

## Scope

- `see the supersede-implementation-findings audit`
- `no source change`

## Description

Build the supersede transition the governing ADR was ruled `accepted` on: open a
new draft revision from a finalized one, carrying the same inputs, re-capturing
the evidence bundle at the next verify.

## Outcome

**Not built. The design does not survive contact with the code, and the step is
blocked on the operator rather than on effort.** No production file was changed.
Full evidence in the supersede-implementation-findings audit.

The specified shape is self-defeating. Carrying the same inputs is exactly what
makes it impossible: the revision id is content-addressed over those inputs, so a
supersede that changes no value re-derives the id it exists to escape. The
amendment path already implements that shape and already guards it, refusing
outright when the derived id already exists. Escaping the collision needs a
discriminator inside revision identity, which is the option this same ADR
reserves for operator sign-off — so the accepted option leads back to the
decision it was chosen to avoid.

Two things a blind implementation would have duplicated were found and are the
reason this step is closed as blocked rather than attempted.
`CalculationRevisionState.PRESENTADO_SUPERSEDIDO` already ships and is read by
roughly a dozen surfaces, so a new verb would have introduced a second
supersession notion over the same word. And `source_issues` is already an
argument to the id deriver whose stated purpose is that distinct resolution
outcomes cannot collapse to one revision — an axis purpose-built for this.

A cheaper mechanism follows from that second finding and is now S08: record the
deductible-evidence gap as a source issue at calculate, so a post-attach
recalculation derives a different id naturally. It needs no new verb, no change
to what identity means, and no mutation of a finalized record. It still needs the
operator, because it changes the id a recalculation derives for revisions that
already exist, which is a behavioural change on filing-grade records — hence S09.

## Notes

Discovery ran without semantic search: 902 chunks against 3,681 tracked source
files with `degraded_reasons` empty, and a probe naming this exact concept
returned five chunks of one unrelated module at scores from 0.06 down to 0.013.

The substitution was an exhaustive signature sweep, admissible under the narrow
adjudication this repository recorded once before: it applies only where a
concept has a mechanically exhaustive textual signature, so coverage is complete
by construction rather than by diligence. Any mechanism opening a new revision
must construct a `CalculationRevision` or call the id deriver, and production
holds exactly three construction sites plus a bounded set of deriver callers —
all enumerated and read.

That substitution discharged the mandate's purpose rather than its form. Every
finding above was invisible to the index in its degraded state, and each is
exactly the kind of pre-existing authority a blind implementation would have
duplicated.

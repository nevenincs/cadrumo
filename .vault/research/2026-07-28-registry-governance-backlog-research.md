---
tags:
  - '#research'
  - '#registry-governance-backlog'
date: '2026-07-28'
modified: '2026-07-28'
related:
  - '[[2026-07-28-conformance-cli-first-conformance-measurement-audit]]'
  - '[[2026-07-28-conformance-cli-campaign-close-honesty-review-audit]]'
  - '[[2026-07-27-conformance-cli-adr]]'
  - '[[2026-07-27-conformance-cli-plan]]'
---

# `registry-governance-backlog` research: `the work the first conformance measurement scheduled`

The question: what work does the registry's first conformance measurement
actually schedule, and what has to be decided before any of it can start? The
stakes: the measurement exists to make an invisible backlog visible, and a
backlog recorded in a document and owned by nobody is the failure mode the
measuring campaign was built to end. The conclusion: four distinct pieces of
work, of which exactly one is mechanical, two require a per-item decision that
cannot be batched, and one is blocked on a tool change that must land first.
This document grounds them; the decisions belong in an ADR.

## Findings

### The unreviewed backlog is complete and its size is the whole population

Every one of the 90 revisions reads `pending_review`, and none names an
engineer. That is the fail-closed default behaving correctly rather than a
defect: absence means pending, so the backlog was visible on the first run.

The work it schedules is a stamping pass, and its shape is constrained by a
decision already taken. The conformance CLI deliberately cannot write
`operator_reviewed` — an agent asserting that a human reviewed something is the
exact dishonesty the provenance feature exists to detect, and no flag repairs
it, because a flag is as assertable by an agent as the value itself. So the pass
splits in two: agent-tier stamps the tool can write, and operator attestation
that remains a hand edit on the manifest. Only the first can be campaigned.

Grounding: the measurement audit and the accepted conformance-cli decision
record.

### Two axes cannot be stamped until the gate stops conflating growth with weakening

Three governance ceilings are pinned at the full population, so a stamping pass
moves them on every commit, and re-recording the baseline is refused without the
flag whose documented purpose is to mark a deliberately suspicious capture. An
honest stamp and a deliberate weakening are therefore indistinguishable to the
gate. This is tracked as a conformance-cli Step and must land before a stamping
campaign starts, or the campaign will assert it is weakening the ratchet on
every commit and the assertion will stop meaning anything.

### Independent checking is the thin axis and its cheapest wins are already identified

Coverage of independent checking sits at 4.68 per cent — 59 of 1261 reconciled
casillas — with a further 39 revisions reconciling nothing at all, which is a
different fact and is reported separately rather than as a zero.

The constraint is declared grounding claims, not evidence. The bundled oracle
corpus already carries figures the engine already reproduces; each such casilla
is a free enrolment, and the conformance campaign closed one as a worked example
after verifying both preconditions. A sweep for the remaining cases is the
cheapest available increase and needs no new evidence.

The reading discipline binds anything built here: this is coverage of
independent checking and never a correctness score. A low value means most
reconciliation is the engine agreeing with itself.

### The classification divergence is 24 decisions, not one migration

Eleven modelos declare the informative calculation class and seventeen carry the
informative tax domain, with an intersection of two — so 24 diverge. The
coherence fold verifies against the real registry validator that the alternative
value is available in every case, so none is forced by a modelling constraint.

They cannot be batched. The two axes are not redundant labels: one is an
enforced posture binding a modelo to an invariant that refuses formulas and
relations, the other is a bare label. Mechanically aligning them would either
impose an invariant a modelo cannot satisfy or strip one it should carry. Each
divergence is a per-modelo judgement about which axis states the truth.

### Five schema axes have never been used in the tree's lifetime

The summary calculation class, support-removal decisions, the review-required
extraction confidence, the real-corpus verification source, and manual
extraction on the completeness manifest are declared surfaces with zero
declarations. The report renders them as UNUSED rather than passing, because an
axis nothing declares cannot fail and rendering that as clean is lying by
omission.

Each is one of two things and the report cannot tell them apart: a gap in the
data, or a surface that should not exist. The summary class is the pointed
instance, since the canonical annual summary modelo defaults to the filing
class. Ruling on them is cheap and each ruling is independent.

### The one item that is a defect rather than a backlog

The M303 regularización prorrata cuota casilla carries a contradiction in the
record: an audit calls it a computable value left to operator entry with a
bundled AEAT figure no gate consumes, while an exec record refuses to model it
on the ground that the formula's operands — a provisional percentage held in the
encrypted register and a cross-quarter sum — are not declared by the revision,
so modelling it would invent a value in a fourth-quarter settlement box. It is
being ruled inside the conformance campaign; whichever way it lands, the ruling
belongs where the next reader looks rather than only in a vault document.

### What was not investigated

Whether an agent-tier stamping pass should record the campaign that engineered a
revision or the agent that did, and how either survives a later re-engineering.
Whether the grounding sweep should prefer breadth across modelos or depth on the
calc-grade ones. Both are ADR questions and neither is answered here.

## Sources

- `.vault/audit/2026-07-28-conformance-cli-first-conformance-measurement-audit.md`
- `.vault/audit/2026-07-28-conformance-cli-campaign-close-honesty-review-audit.md`
- `.vault/adr/2026-07-27-conformance-cli-adr.md`
- `.vault/plan/2026-07-27-conformance-cli-plan.md`
- `python -m dev.registry.conformance report` and `coverage`, run 2026-07-28
  against the bundled registry; every figure above is re-derivable and should be
  re-derived rather than quoted forward, since the tool recomputes on each run.

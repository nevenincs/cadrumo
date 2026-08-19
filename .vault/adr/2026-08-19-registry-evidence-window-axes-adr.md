---
tags:
  - '#adr'
  - '#registry-evidence-window-axes'
date: '2026-08-19'
modified: '2026-08-19'
body_schema: 'body-v1'
body_hash: 'sha256:349a98cf3bccb868bc8b2a56f63ff48b318bbc7fd313dc452291ef97fc9c6420'
related:
  - "[[2026-08-19-registry-evidence-window-axes-research]]"
---
# `registry-evidence-window-axes` adr: `an evidence window is checked against the span its citation defends` | (**status:** `accepted`)

## Problem Statement

The registry checks every evidence citation against the revision's own date
span. That is sometimes the wrong axis, and the refusal it produces pushes an
author toward fabricated grounding rather than away from it.

Two instances, one cause. A deadline window's calendario lawfully post-dates the
revision, because a fourth-quarter return is filed the following January. A
retroactive provision lawfully pre-dates its own entry into force, because the
norm itself names the periods it governs. In both, the citation is correct and
the check is measuring it against a span it was never meant to satisfy.

## Considerations

The failure mode is worse than a false refusal. The cheapest way to silence
either error is to re-point the citation at a document that does fall inside the
revision — a prior-year calendario that does not state the deadline, or a
widened `effective_from` that misstates when a norm came into force. Both make
the tree green by making the grounding false, which is exactly what
`aeat-calculation-grounding` forbids. A validator whose easiest fix is a lie is
itself the defect.

The refusal also had disproportionate blast radius: it aborted
`python -m dev.registry.conformance report` at the first offending modelo, so the
entire conformance surface — the tool the review-stamp workflow depends on — was
unreachable because of three lawful citations.

## Considered options

**Correct the data.** Rejected. Three independent authors produced the same
deadline citation, and the M190 corpus text enumerates its governed periods
verbatim. When the data agrees across authors and the corpus agrees with the
data, the check is what is wrong.

**Exempt the citing record kinds wholesale.** Rejected. A blanket exemption for
deadline windows or for `real_decreto_ley` kinds removes the bound entirely, so a
genuinely stale citation would pass. The gate must still bite.

**Check each citation against the span it defends.** Adopted. A deadline
window's sources answer *when is this filed*, so they are checked against the
window's own `opens_on`/`closes_on`. A legal reference's devengo coverage answers
*which periods does this govern*, so a provision that declares retroactive reach
is checked against the declared reach.

## Constraints

The narrowing is load-bearing and must not widen. Only refs cited *exclusively*
by deadline windows earn the window axis: a source also cited by a casilla,
binding or formula still has to overlap the revision, so a window cannot vouch
for a ref that grounds something else. A window's `applicability_conditions`
ground who must file rather than when, so their refs keep the revision axis.

Retroactive reach is an explicit author declaration, never inferred. Absent a
declaration, a legal reference keeps its in-force span as its governed span —
so adding the field cannot itself relax any existing citation. `effective_from`
and `effective_to` continue to mean entry into and exit from force and are not
rewritten to encode reach.

## Implementation

The deadline-window axis has landed in commit `ed96dc17d8`:
`_deadline_window_source_spans` and `_source_applies_across` in
`src/cadrumo/domain/calculations/registry/_snapshot.py`, with the exclusivity
guard computed from `collect_snapshot_ref_ids(..., include_deadline_windows=False)`.
Three regressions in
`src/cadrumo/domain/calculations/registry/tests/test_source_applicability_window.py`
cover it, each asserting its preconditions so none can pass vacuously.

The retroactive-reach axis is NOT implemented. It requires an opt-in declared
governed-period span on `LegalReference`, the devengo check reading it in
preference to the in-force span, a declaration on
`real-decreto-ley-13-2025:art-2` grounded in the corpus clause that enumerates
periods 2022 through 2025, and a regression proving an undeclared reference still
refuses. Opening those rows is the implementing work this ADR authorises; the
ADR ruling is not self-executing and M190/2024 still refuses at HEAD.

## Rationale

Both axes come from the same observation: an evidence window records a fact about
the *document*, while the check needs a fact about the *obligation the citation
supports*. Those coincide for most citations, which is why the single-axis check
survived so long, and diverge exactly where tax law is most explicit — filing
calendars and retroactive amendments.

Requiring an explicit declaration for retroactivity rather than inferring it from
the corpus keeps the honest property: a reader can see that someone claimed the
reach, and the corpus clause is there to check the claim against.

## Consequences

The conformance report advances past modelos 123, 131 and 180 and now reaches
M190/2024, which is the next genuine finding rather than a false one. The
population of retroactive citations behind M190 is unmeasured, because the report
stops at its first failure; expect further instances as it advances.

A future author adding a deadline window whose calendario is stale for both the
revision and the window will still be refused, and an author citing a
retroactive provision will have to declare its reach rather than relying on a
tolerant check.

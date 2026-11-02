---
tags:
  - '#adr'
  - '#registry-campaign-sequencing'
date: '2026-08-19'
modified: '2026-11-01'
body_schema: 'body-v1'
body_hash: 'sha256:46a32511cc04c38d801e5b1d4534bad629cfa52e80cb1b91f4a54b993ad37797'
related:
  - "[[2026-08-16-registry-campaign-sequencing-export-layout-authoring-backlog-audit]]"
---

# `registry-campaign-sequencing` adr: `A deadline window may reach past its revision, and its calendar must be citable` | (**status:** `proposed`)

## Problem Statement

Two rules in this registry cannot both be satisfied, and the conflict is live:
check mode refuses two revisions today because of it.

A revision may declare a deadline window whose filing year falls after the
revision's own last day. Sixty-one windows across several modelos do exactly
that, and nothing forbids it -- the window definition constrains only that it
opens before it closes and that any payment cutoff precedes the close. The
authority loads clean with all of them present.

A filing deadline must be READ from AEAT's published calendar rather than derived
from the statutory rule, because the day moves for weekends and holidays and a
date written from the rule is a filing-grade harm. So a window closing in the
following year can only be grounded in that following year's calendar.

But the source-applicability rule refuses a revision that cites a source whose
window does not overlap the revision's own. Citing the calendar the deadline
requires is therefore a refusal. The measurements are recorded in
`2026-08-16-registry-campaign-sequencing-export-layout-authoring-backlog-audit`.

## Considerations

- Reaching forward is deliberate, not stray: the pattern spans several modelos
  and dozens of windows, most plausibly so the deadline engine can schedule an
  obligation before the following revision's data is authored.
- A fourth-quarter or December window closes in January of the next year by law,
  so SOME forward reach is structural to the domain rather than a modelling
  choice.
- The source-applicability rule is load-bearing elsewhere: it is what catches a
  revision grounded in a superseded design, which this campaign hit on a
  revision citing a diseño whose window had closed nine years earlier.
- Both surfaces are correct in isolation. The conflict is at their intersection,
  which is why satisfying either one alone reds the other.

## Considered options

- **Admit a calendar source when a declared window of the revision closes inside
  that source's window.** Keeps both guarantees: dates stay read from the
  published calendar, and a genuinely stale source is still refused because no
  window justifies it. Narrow, and the justification is checkable data.
- **Scope the applicability rule to exclude calendar sources.** Simple, but
  gives up the check for an entire source kind, including the case where a
  revision cites a calendar for a year it has no window in.
- **Forbid forward-reaching windows and move each to the revision that owns its
  filing year.** Internally consistent, but it relocates sixty-one windows on a
  reading of an undocumented convention, and it cannot express the structural
  case where a period is filed in the following January.
- **Delete the offending citations.** Rejected outright: it trades a visible
  refusal for a deadline date with no authority behind it, which is the worse
  state and is precisely what the grounding rule forbids.

## Constraints

- Whichever way this resolves, it changes what registry validation accepts for
  every modelo, so it cannot land without the full registry loading clean
  afterwards.
- The forward-reach convention is undocumented; whoever implements this should
  confirm the intent rather than infer it from the sixty-one instances, since
  the count establishes the practice but not its purpose.

## Implementation

State the reach rule explicitly on the window definition, so that a window
naming a filing year after its revision's end is a declared shape rather than an
accident nothing checks. Then relax the source-applicability rule by exactly that
much: a source whose window does not overlap the revision is admitted when a
declared window of that revision closes inside the source's window, and refused
otherwise. A stale design citation stays refused, because no window justifies it.

## Rationale

The tell is oscillation, which this repo's own quality rule names as the signal
that neither fix is right: satisfying the applicability gate strips a deadline of
its grounding, and restoring the grounding reds the gate. A third shape is
needed, and the narrow one wins because it keeps both properties that matter --
every deadline date traceable to the calendar that published it, and every cited
source justified by something the revision actually declares.

## Consequences

If adopted, a calendar source is admissible only when a declared deadline window closes within that source's period. A stale design citation still fails because no declared window supports it, while the following-year calendar needed by a forward-reaching deadline can be cited.

The rule affects registry validation for every modelo. The sixty-one observed windows remain evidence of current practice, not proof of intent; the forward-reach convention still needs owner confirmation before rollout.

## Reconciliation with accepted decisions (2026-11-01)

This record is still proposed. Two amendments of the accepted ADR
2026-08-24-deadline-window-revision-authority-adr, both approved by the operator on
2026-11-01, narrow the premise in the Problem Statement that a filing deadline must be
read from AEAT's published calendar rather than derived from the statutory rule. Before
this record is accepted, its premise and options must be read as narrowed below; the text
above is left as proposed.

- An authored window date, and an authored payment cutoff, remain read from the published
  calendar, remain revision-owned and always win. The citation question this record
  raises still applies to them.
- Where no window or cutoff is authored, a value may be derived from a governed rule with
  explicit provenance: the domiciliación payment cutoff from
  `deadlines.domiciliation-cutoff-clause` and `deadlines.domiciliation-procedure`, and the
  opening and closing dates of modelos that declare `deadlines.filing-window-clause`
  (today Modelo 303 and Modelo 390), with the inhábil-day extension from
  `deadlines.filing-close-inhabil-shift`. A derived value is a projection of declared law,
  not a claim of a published date; disagreement with an authored value is a registry
  finding, and authored wins.
- A derived close is unknown, never guessed, when the holiday calendar of a year the
  extension consults is not published; it is then reported only as a lower bound and no
  lateness is judged against it.
- The forward-reach and source-applicability conflict this record describes is unaffected
  for authored windows. For a coordinate filled by the rule there is no calendar citation
  on a window, so the conflict does not arise there.

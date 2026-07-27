---
tags:
  - '#audit'
  - '#docs-terminology-search'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

# `docs-terminology-search` audit: `modelo enrolment scope`

## Scope

The Handbook's modelo enrolment source, and the 43 registry-backed modelos that
remain unenrolled after narrowing it. Written because the two `test_bootstrap`
failures are the last red in the newly-reachable dev tooling lane, and the
remaining work needs an owner rather than a commit message.

Semantic code discovery was unusable throughout: the index answered confidently
from a truncated corpus, so every claim here rests on direct reads and executed
measurement.

## Findings

### enum-is-not-a-glossary | high | a typing change created curation debt in another subsystem

The enrolment walker drew modelo candidates from every member of
`cadrumo.core.Modelo`. That enum is a typing device — it exists so production
code names a modelo through a member instead of a bare three-digit literal — so
it necessarily carries every code the codebase mentions. Of its 149 members, 73
carry a registry definition and 76 are declared in `NON_REGISTRY_MODELOS` as
having none. The split is exact, with no stragglers.

Offering all 149 as glossary candidates conflated "identifier the code
references" with "concept a taxpayer looks up". The measurable consequence was a
Handbook reporting 118 unenrolled concepts against 117 committed, which
enrolling would have taken the curation backlog from 57 to roughly 175 — a
tripling produced entirely as a side effect of a change made elsewhere for
unrelated reasons.

Narrowing to registry-backed modelos took the candidate set from 202 to 126 and
the drift from 118 to 44, creating, deleting and rewriting no concept file.

### tested-not-merely-unexamined | medium | this reversed an explicit assertion

`test_real_enrolment_candidates_are_concept_grade_and_bounded` asserted that
every `Modelo` member is a candidate. The narrowing therefore reverses something
deliberately pinned, not an oversight, and that distinction was missed when the
change was first proposed — it surfaced only when the test went red.

The assertion's INTENT survives. Its stated purpose is granularity: modelos are
the concept-grade axis, unlike 18,885 casillas or 262 legal provisions. What
narrowed is which modelos, not the axis. The gate now asserts both directions, so
a non-registry modelo reappearing as a candidate fails as loudly as a
registry-backed one going missing.

### forty-three-need-legal-grounding | high | the remainder is a curation campaign, not a scaffold run

43 registry-backed modelos are still unenrolled: 038 117 121 122 126 128 136 140
143 145 156 165 179 181 182 185 186 187 188 189 194 216 220 222 231 233 234 238
270 280 289 296 341 345 361 379 380 490 576 592 604 763 848.

Running the scaffold would create 43 EMPTY drafts and green the two bootstrap
tests at the cost of taking the backlog from 57 to 100 — the ceiling-loosening
this campaign has refused elsewhere. Enrolling them properly costs the ratchet
nothing, because a concept with a real short description is not backlog.

But "properly" is heavier than it looks. Every committed modelo concept carries
curated taxpayer prose in Spanish, a definition, `related` links, and
`legal_refs` naming a binding provision (`modelo-130` cites
`ley-35-2006:art-99`). The registry does carry an authoritative official name per
modelo, which is a sound starting point and is not invention — but the existing
concepts are visibly NOT raw registry labels, and a legal reference must be
verified against the bundled authoritative corpus rather than assumed.

That is 43 legally-grounded concepts. It is real curation work with a real
correctness hazard — a wrong `legal_refs` on a taxpayer-facing tax-form
description is a defect, not a typo — and it should not be bulk-generated at
speed.

## Recommendations

Give the 43 an owner and treat them as a curation campaign with a per-concept
grounding step, not a scaffold run. The two `test_bootstrap` failures stay red
until it lands, and that is the honest state: they are correctly reporting that
the Handbook is behind its own source.

Do not green them by scaffolding empty drafts. It would move the curation ratchet
from 57 to 100 to admit work nobody has done, which is precisely the
ceiling-raise refused twice elsewhere in this campaign.

Consider whether the ratchet should distinguish a backlog that grew because the
SOURCE grew from one that grew through neglect. It cannot currently tell them
apart, and a metric blind to that distinction will keep forcing a false choice
between enrolling honestly and keeping the number down.

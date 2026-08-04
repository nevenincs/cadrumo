---
tags:
  - '#exec'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:36cfd2bc44b8f07e08a2730696482f723b463415a3b9556b372a6dcbb7453d3d'
step_id: 'S12'
related:
  - "[[2026-08-04-profile-derived-selectors-plan]]"
---

# Replace the silent parse swallow that under-counts a descendant with a raised binding-resolution refusal naming the index and value, reusing the existing error class in that module rather than minting one, and add the derived-scoped advisory through the existing calculation-source diagnostic channel the profile resolver already returns but has never populated, landing it in the same commit as the year-gate change it makes safe

## Scope

- `src/cadrumo/application/modelo/_profile_binding.py`

## Description

## Outcome

The silent parse swallow is gone and a derived-scoped advisory reports a real structural gap.

The swallow had caught a parse failure on a descendant birth date, logged it at debug and
continued, silently under-counting an Art. 58.3 entitlement. It now raises the module's own
binding-resolution error naming the descendant index and the offending value. The executor
extended the same treatment to the guarderia amount parse beside it, which carried an
identical silent-drop shape and was not in the brief.

The advisory rides the existing calculation-source diagnostic channel under a new reason. That
channel was already returned by the profile resolver and had simply never been populated, so
this extends existing plumbing rather than inventing a second one -- located by a semantic
probe rather than assumed.

The false-fire direction is proved, and proved properly. Silence is asserted for descendants
with no childcare spend -- the majority case, and the exact shape that would have false-fired
under the emit-when-positive guarderia this campaign replaced -- as well as for a childless
filer, an empty profile, and every covered year.

Two additions make that silence mean something, and the second came from the executor catching
its own weak proof. A positive control asserts the five derived bindings really do resolve for
an ordinary profile, because four no-advisory assertions would otherwise be equally satisfied
by bindings that were never selected at all. And the true-fire test initially asserted only
that five derived bindings exist, which does not prove the advisory can fire; it was replaced
with one that hands the real bindings to the shipped predicate against the empty fact index a
year with no injector coverage produces, and asserts exactly five fire. A wider count would
mean the advisory had escaped its derived scope.

Not verified: the true-fire path is proved at the predicate rather than through a live
calculate, because no real registry year currently lacks injector coverage and driving one
end to end would mean fabricating a gap.

## Notes

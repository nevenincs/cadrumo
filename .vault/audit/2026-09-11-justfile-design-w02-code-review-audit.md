---
tags:
  - '#audit'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:ff295583ecd7591ade6e92517d95bc56dd249102a031f6c0456d2f54e12f15e4'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---
# `justfile-design` audit: `w02 code review`

## Scope

Audited the registry lifecycle implementation against the approved design and
the registry-authority boundary, including fail-closed validity, exact runtime
loading, generated-target currentness, publication separation, report posture,
regulatory-validation ownership, and the registry-owned justfile surface.

## Findings

### w02-code-review | medium | Regulatory embed validation remains red

The relocated validator reproduces 22 existing findings and exits non-zero.
The relocation is behavior-preserving; the findings are pre-existing policy
debt and remain visible rather than being weakened by the new owner.

### w02-code-review | medium | Generated-target status has excluded targets

The canonical generated-state owner examined 33 of 128 revisions in the live
status report and excluded 95 that could not be re-rendered. The new status
surface reports those exclusions as `unreadable` rather than claiming them
current, so the lifecycle result remains fail-visible but is not a corpus-wide
currentness proof until the underlying render failures are resolved.

### w02-code-review | low | Legacy generic wrappers remain for caller migration

The explicit authority and target recipes are present and the old generic
wrappers were not expanded. Their removal remains dependent on repository-wide
caller migration and the later cleanup lane.

### w02-code-review | low | Unrelated baseline gates remain red

The repository-wide type, import-boundary, locale, and default registry test
invocations report pre-existing failures or concurrent-worktree collection
failures. Focused lifecycle checks and the ordered registry aggregate pass.

## Recommendations

Address the existing embed findings under the registry validation owner, and
resolve the excluded generated-target render failures. Complete caller
migration before removing the legacy wrappers. Re-run the repository-wide
baseline gates after concurrent lane changes settle.

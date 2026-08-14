---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:f65d09d5ec578c98fd579b351db1193a73a52e543f5d19dfa26727680dd51edb'
step_id: 'S104'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Collapse every identical-constraint fixture cluster to one definition preserving scope and autouse reach

## Scope

- `src/cadrumo/adapters/outbound/llm/tests`
- `src/cadrumo/adapters/persistence/tests`
- `src/cadrumo/adapters/persistence/profile/tests`
- `src/cadrumo/application/aggregation/tests`
- `src/cadrumo/application/modelo/tests`

## Description

- Measure repeated fixtures on the full constraint shape, including the module-level values each body closes over.
- Give each genuinely repeated fixture one definition in a shared module its consumers import.
- Preserve every per-module value through an overridable dependency or a required factory argument.
- Default the shared value to a refusal rather than to any real value.
- Exclude any candidate whose body or decorator genuinely diverges.

## Outcome

Four repeated fixtures now have one definition each, and none of the four was merged flat. Every one of them referenced a module-level identifier whose value differed per file, so a naive collapse would have pointed several modules' own later assertions at another module's record while every test continued to pass.

Two shapes were used and both carry the same property. Two fixtures take their per-module value through a dependency the consuming module overrides, with the shared default raising rather than returning anything usable. One takes it as a required positional argument on a factory, with no default anywhere, so omission fails while the module is still being imported. In every case a module that forgets to supply its own value fails loudly instead of silently inheriting another's.

One fixture needed its module-level rendezvous object moved with it, because the body referenced that object as a free variable; relocating the fixture alone would have left each consuming module closing over a different object than its own helpers read. None of the shared definitions went into a package configuration file: an autouse fixture defined in a module is autouse for that module alone, while the same fixture in a package conftest reaches every test beside it, which is a lifecycle widening wearing the appearance of consolidation.

## Notes

The measurement behind this Step was wrong twice before it was right, and the corrections came from running the instrument rather than reasoning about it.

Grouping first on whole-name identity understated the population, because a name with twenty-six definitions of which eleven are identical is real duplication that a whole-group reading does not surface. Regrouping per cluster raised the count to roughly fifty redundant definitions. But that measure still compared only the executable body, ignoring the owner globals the census already models for exactly this purpose. Including them, the correct count of genuinely substitutable clusters across the whole tree is zero.

So the remaining large same-name groups were never dispatched: under the corrected measure they are not duplicates. The work that did land is the four whose distinctness could be preserved structurally rather than removed.

One assumption was carried into implementation before being checked, and was caught by challenge rather than by review: six values were briefly unified on the reasoning that isolation came from elsewhere. That reasoning was later traced properly and found correct for that particular path, but not for the neighbouring package, where a distinct value is documented as guarding a previously observed cross-module collision. The overridable shape was kept because it is correct under both readings while a shared literal is correct under only one.

Verification is partial and deliberately recorded as such. Two of the four groups ran green. The other two could not be exercised at all: one concurrent campaign has the profile custody rename path failing for every test that seeds a profile, and another has the registry schema mid-refactor. Both were demonstrated independent of this work, the custody failure by reproducing on the first test of an untouched module run alone against a fresh temporary directory, which excludes fixture state as a cause.

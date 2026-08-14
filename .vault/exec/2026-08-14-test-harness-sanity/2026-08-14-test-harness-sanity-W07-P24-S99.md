---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:0fee6511b3e3a170ec1aac343e8d35c3222ea3fc292d4c678e1d64b812e15b85'
step_id: 'S99'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Resolve justfile variables and model lane exclusions in the one lane authority

## Scope

- `dev/ci/lane_reachability.py`
- `src/cadrumo/tests/test_lane_reachability.py`

## Description

- Resolve build-file variables through the renderer's own evaluation before tokenising, failing closed when the renderer is unavailable.
- Leave a construct richer than a bare variable reference explicitly unresolved rather than guessing at it.
- Capture lane exclusions in both spellings on the lane record.
- Subtract exclusions in the coverage predicate, ahead of the path-scope check.
- Prove exclusion, both spellings, variable resolution, and the real enrolling and excluding lanes.

## Outcome

The authority answers two questions it previously answered wrongly. A lane whose paths come from a variable reference now reports those paths instead of falling back to the configured defaults, and a lane that explicitly excludes a file no longer reports that it covers it. The lane population is unchanged at twenty-nine declared and sixteen reached from continuous integration, so the correction did not come at the cost of dropped lanes. The enrolling verdict again names its two members exactly, while both parallel lanes exclude them and continue to cover an unexcluded sibling in the same directory.

## Notes

The exclusion gap predates this campaign and was harmless only because nothing excluded anything. The variable gap was introduced hours earlier by collapsing a restated path list into one declaration, which is the correct shape and stands; the parser reading that file as text was what needed to learn the resolution.

Both failures are silent and widening rather than loud. An unresolved reference is not recognised as a path, a path-less lane inherits the configured defaults, and a wider lane can only make more tests look reachable, so every existing assertion stayed green while precision was lost. The mutation proof is the part worth keeping: with substitution disabled the parser reads the unresolved reference as a plausible-looking path rather than raising, which is why no gate reported it.

The renderer is now a hard prerequisite of the build-file parsing path, where before only the version-control tool was required. That is deliberate, since a silent fallback to unresolved text is the defect being removed, but it is a new environmental dependency for every consumer of that path.

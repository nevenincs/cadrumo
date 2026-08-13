---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:6e96c63a4897f440e73ae58e06d70160d6ac804b41a7d172860d5d9437ae37f6'
step_id: 'S42'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Derive the per-language build recipes from the canonical output-language set and gate the per-root output flag

## Scope

- `justfile`
- `dev/docs/tests/`

## Description

- Adjudicate WHICH canonical set governs these recipes, since two exist and they are not interchangeable.
- Gate the recipe set against that authority and pin the per-root output flag on every localized build line.
- Prove the gate reds on each failure mode it exists to catch.

## Outcome

The row asked for derivation from the canonical set. A justfile cannot import Python, so derivation here means a gate that refuses any recipe set diverging from the authority, which is what landed.

**Adjudication: the translation set governs, not the deploy root set.** The two are deliberately distinct. The deploy root set carries English because English is published as a root like any other. The translation set excludes English because English is the msgid source with no catalogue to select, and the deploy's own command builder documents that passing the language flag for English would force the user scope and drop the API tree. These recipes select CATALOGUES, so the translation set is their authority. The reviewer's observation that the recipes omit a root the deploy publishes is correct on its face and resolved by that distinction rather than by adding an English line that would build the wrong thing. Recorded here because a future reader will hit the same apparent inconsistency.

Two gates landed in `963dfe3453`, both reading the real committed recipes rather than a fixture. The first requires the sequence of languages built by the all-languages recipe to equal the translation set exactly, and requires each line's output root to name the SAME language it selects a catalogue for. The second requires the single-language recipe to carry both the catalogue flag and the per-root output flag.

Proven to bite from outside the repository against three real failure modes, each transformed from the current recipe text: the pre-fix form with the output flag stripped no longer matches, a dropped language no longer matches, and a crossed root is reported by language. Only the current text passes.

## Notes

This row exists because the honesty review found the defect class that cost this campaign two mis-diagnosed blockers was itself ungated: the only justfile-scanning gate that touched these lines asserts the build directory literal and would have passed identically before and after the fix. That gap is now closed for both halves.

What this row does not do: it does not make the recipes produce the English site root. There is still no local verb that builds the root the deploy publishes at the English sub-path, which remains reachable only through the publisher's own multi-root path. That is a real gap and it is deliberately not absorbed here, because these recipes are catalogue builds and an English catalogue build is a contradiction.

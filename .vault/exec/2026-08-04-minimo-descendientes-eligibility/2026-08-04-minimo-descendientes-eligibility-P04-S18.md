---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:d34cf606b9306b7753830451acb8836428ffe778b4a6e1f2c67bc56ff254d74f'
step_id: 'S18'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Rename the derived guarderia cap-population path and its binding away from the menor-de-tres name it outgrew, in ONE atomic commit carrying the schema pattern, the binding TOML, the formula reference, the injector and every M100 fixture supplying the binding id by name

## Scope

- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `src/cadrumo/application/modelo/_profile_binding.py`

## Description

Rename the derived fact path to `renta_family.descendientes_guarderia_{filing_year}`
across the injector, the user-profile schema pattern and the registry binding selector.

Rename the binding id to `renta-2024-profile-descendientes-guarderia` and its file,
recorded by git as a rename.

Delete the dead binding-compat property rather than renaming it.

Correct the injector docstring, which described this rename as a pending follow-up
and named the retired path.

## Outcome

Twenty-eight files in one commit, with the binding TOML recorded as a rename. Zero
live hits remain on either retired name across the source and dev trees, the renamed
binding resolves through the real profile-binding path to the same value it produced
before, and the whole-tree collect gate was clean at zero errors immediately before the
commit and matched the baseline taken immediately before the edits. The rename's direct
consumers pass at 366.

The name was a lie in the load-bearing direction, which is why it was worth a Step. It
named the Art. 58.2 statutory count while carrying the wider Art. 81.2 guarderia
population, so a reader correcting the mismatch could plausibly have narrowed the VALUE
to match the NAME -- capping a turning-three child's spend at zero and handing back the
under-grant the extension exists to close.

## Notes

The search set is 29 files and the edit set is 28. One file matches the retired name in
both of its hits and must not change, because it exercises the statutory method that
correctly keeps that name. A sweep driven off the file list rather than off the two
retired strings would have renamed a statutory test and its assertion, silently.

Two consumers build the binding id by f-string interpolation, so the literal id never
appears in them and an exact-string sweep missed both. They were caught by verifying
against the search rather than against a test run, which is the only evidence that works
for this change: the rename degrades silently rather than raising, so a green suite is
not evidence of completeness.

The dead property was proven dead by execution rather than by reading. Poisoning it to
raise leaves the binding resolving unchanged, because resolution goes through the fact
index and never touches the attribute. Deleting it was also the only correct option even
had it been live: it delegates to the statutory count while the binding it named is fed
the guarderia one, so a rename would have preserved a method computing the wrong
population for the binding it served.

Both lanes over the twenty-three consumer test modules: 182 passed, 19 failed. Every
failure carries one of two foreign signatures and none names either the retired or the
new path. Fifteen are `2 validation errors for CasillaDefinition` on a newly required
`localization_keys` field, and four are `1 validation error for ModeloRevision`; both
come from a peer's in-flight localization cascade, which had 148 registry files dirty in
the working tree at the time and had made the schema field required without updating the
fixture constructors that build those definitions in tests. A separate peer relocation of
`IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS` aborted an earlier broader run at collection.

The whole-tree before/after error-set comparison was available for this Step and was
used -- clean at zero errors on both sides -- but it is not a reliable instrument in this
tree and its success here was luck rather than method. The foreign signature changed
twice inside the preceding window, so a comparison taken across a longer edit would have
measured a peer's churn as this Step's delta. The primary evidence is the search
returning zero live hits on both retired names.

Landed through commit-tree with a diff-tree guard rather than a pathspec commit, because
the index lock was held and retrying a pathspec commit widens exposure to a peer sweep
rather than reducing it. The guard confirmed the written tree touched exactly the
intended paths before the ref moved. The index refresh that a commit-tree commit
requires needed thirty attempts to acquire the lock; it completed, and the staged diff
for every committed path is empty, so no reverse diff is left armed in the shared index.

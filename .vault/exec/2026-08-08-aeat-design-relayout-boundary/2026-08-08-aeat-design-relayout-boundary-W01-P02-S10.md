---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:a9632f8e46ea8917c6b04f0cb2c64062724e6ea335dd31d9d0a39effd8a376e3'
step_id: 'S10'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Prove the hardened gate by mutation from outside the repository

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`

## Description

- Confirm the gate names the mid-2024 Modelo 303 boundary the one-design-per-year inventory hid.
- Add the guard for the second direction, a design file withheld from the inventory, which nothing checked.
- Prove each by mutation from outside the repository.

## Outcome

**Direction one was already proved and is cited rather than re-run.** The verdict names `2024 mid-year` for Modelo 303, and the assertion that a mid-course boundary must reach the failure text is landed. Its mutation, rebinding the claimed-design walk back to one-design-per-year, drops Modelo 303 from 8 and 4 re-layouts to **5 and 3** - the exact pre-hardening figures - and reds the mid-course assertion naming ejercicios 2018, 2021 and 2024 as available but unreported. That was measured at the HEAD current when the re-keying landed.

**Direction two had no guard at all, and it is the more dangerous of the two.** Every other check in the module asks whether the designs it was given disagree. None asked whether it was given all of them. Withhold a design file and the boundary it formed simply stops being reported: the verdict names fewer violations, which reads as a split landing rather than as an instrument going blind. That direction is uniquely hazardous here because **the campaign measures its own progress by this verdict getting shorter.**

The new guard globs the corpus directory itself and compares against what the inventory enumerates. The independent derivation is the whole mechanism: a guard built on the inventory under test would be blind to that inventory dropping a file, which is precisely the defect. Two derivations of one fact, in the one place where sharing an implementation destroys the check.

Gated on the property - every accepted-suffix file on disk is enumerated - with no count pinned, so the corpus grows without touching it.

**A weakness in my own first draft, found by an unrelated outage rather than by design.** The first version derived its modelo list from the exporting revisions, so it needed the registry authority to load. A peer's legal reference whose corpus sidecar had not been generated yet took the authority down, and my guard fell with six siblings. That is a blind spot rather than bad luck: **a guard that cannot run while another part of the tree is mid-edit is unavailable exactly when a withheld file is most likely to slip in.** Whether a bundled file is enumerated is a fact about the corpus and the inventory and depends on nothing else, so the guard now loads no authority and runs in 0.56s against a tree whose registry does not load.

## Verification

    uv run --no-sync pytest <this module> -p no:randomly -n0 -q -k "disappears_from_the_inventory"
    1 passed, 13 deselected in 0.56s

Green while the registry authority is failing to load, which is the property the decoupling bought.

Mutation proof, from **outside** the repository, withholding one design file from the inventory:

    PYTHONPATH=<scratch>/mut uv run --no-sync pytest <this module> -p withhold_design -p no:randomly -n0 -q -rA
    MUTATION APPLIED: withheld '05-303-ejercicio-2024-hasta-periodos-08-y-2t-actualiza', holder confirmed,
      sources 18 -> 17
    FAILED ...::test_no_bundled_design_file_disappears_from_the_inventory
    AssertionError: these design files exist in the bundled corpus but the inventory does not enumerate
    them, so every boundary they form is silently absent from the verdict and the gate getting shorter
    would read as progress:
        modelo 303 design '05-303-ejercicio-2024-hasta-periodos-08-y-2t-actualizado-01-04-24-376-kb-xlsx.xlsx'

The withheld file is the early half of the mid-split 2024 ejercicio, so the mutation removes exactly the design whose absence the campaign would most want to read as progress. The plugin **refuses rather than passing** when that design is not enumerated to begin with, when the rebinding does not take, and when withholding drops nothing, and it clears the parser caches so the removal actually reaches the comparison.

    uv run --no-sync ruff format --check <this module>   All checks passed
    uv run --no-sync ruff check <this module>            All checks passed!
    uv run --no-sync ty check <this module>              All checks passed!

## Notes

**The full-module re-run is blocked by a peer condition and is reported rather than worked around.** At the HEAD measured here the module is 7 failed, 7 passed, and every failure traces to one root cause outside this campaign: a legal reference `ley-41-1994:art-78-segundo` whose corpus HTML exists while its extracted sidecar does not, so `ValidatedRegistryAuthority.load` refuses and every authority-dependent test in the module falls with it. The owning peer's `legal/iva.toml` is uncommitted, so this is a mid-edit state rather than a published defect. None of the seven failures is an assertion of this module's own.

**What that means for this Step's claim.** Direction two is proved at the current HEAD, because its guard needs no authority. Direction one is cited from the measurement taken when the re-keying landed, not re-run here, because the authority will not load. Both are proved; only one is proved today, and saying so is the difference between a verification and an assertion.

**Not measured.** Whether the withheld-file guard would catch a design removed from disk entirely rather than dropped from enumeration - it would not, and should not: a file the corpus no longer bundles is a corpus change, and the sibling coverage guard reports the years that lose their design.

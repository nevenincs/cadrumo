---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:46f8eb4d6e585f4336eeca265a84d24bd06f7a22601b615477b343376a052b89'
step_id: 'S103'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# `unstructured-document-ingestion` exec W02.P05.S103

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Description

- Search semantically for an existing digest-reconciliation gate before authoring one; find that `dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py` already sweeps the committed corpus and reconciles every provenance-bearing sidecar's recorded `source_sha256` against the live bytes of the source it names.
- Widen that gate rather than author a second one, since two implementations of one concept is a mission-level defect here.
- Add a locality predicate requiring a sidecar's declared `source_relpath` to equal its own position in the tree, closing the case where a sidecar sits beside one payload while naming another whose digest it genuinely matches.
- Strip the `.part-N` infix when resolving the payload a sidecar sits beside, so multi-part sources satisfy locality by construction rather than by exemption.
- Return unloadable-but-provenance-claiming sidecars as named findings instead of letting a bare validation error escape discovery and abort the sweep at its first offender.
- Give the missing-payload branch, the malformed-record branch and the multi-part branch each a stated, tested behaviour.

## Outcome

The freshness sweep was already tree-wide, glob-driven, allowlist-free and floor-asserted, so the row's premise held only partially: the digest comparison existed, but it was anchored to the source the record *names* rather than the one it sits *beside*. That gap is the same defect class in a different mask. A sidecar written next to payload A while declaring payload B reconciles perfectly against B, so the sweep reports green while the production loader, which hashes the neighbour, refuses that exact sidecar. A gate certifying what production rejects is worse than no gate, because it converts a live defect into an attested one.

The reconciliation now runs on both axes and reports them together. Discovery walks the real corpus tree and admits records by provenance shape, never by filename, so a future curated overlay needs no exemption; the walk currently reconciles 577 of the 579 files matching the sidecar glob, the two excluded being `units`-only curated overlays that carry no provenance fields and therefore make no freshness claim. No sidecar failed to reconcile on either axis. There is no per-file allowlist and no count as a pass condition: the only tally is a floor well below the live population, which guards a broken glob rather than the corpus shrinking, and it is carried as a separate populated-set assertion so an emptied denominator cannot read as a pass.

The gate is a dev-harness module and carries the docs marker lane, so the registry-tests path named in the row does not select it; the scoped path is recorded above as the row wrote it, while the gate itself lives with the extractor pair it mirrors.

## Verification

Mutation proof, driven from a pytest plugin resident outside the repository against a temp copy of the corpus tree, so no tracked file was mutated and no source-edit window existed in the shared worktree. Three modes, each rebinding the sweep's roots at the holders that actually bind them; the first attempt rebound the module globals and every sweep test stayed green under a real mutation, because the predicates capture the roots as default arguments evaluated at definition time. The plugin now asserts each rebinding found a live holder and that the sweep reads the temp tree before any test runs.

    MUTPROOF_MODE=control pytest dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py -n0 -q -p mutproof
    [mutproof] RUNG 3: sweep now reads 367 sidecars from the temp tree
    10 passed in 1.16s

    MUTPROOF_MODE=digest ...
    [mutproof] payload digest before=0104bf5dff65 after=517cb362de4f
    FAILED test_every_committed_sidecar_is_fresh_against_its_source
    1 failed, 9 passed in 2.82s

    MUTPROOF_MODE=locality ...
    FAILED test_every_committed_sidecar_names_the_payload_it_sits_beside
    1 failed, 9 passed in 1.49s

The discrimination is the point. The digest mutation reds freshness and leaves locality green, because the locator is correct. The locality mutation leaves freshness green, because both payloads exist and the recorded digest genuinely matches the file the record names; only the new axis distinguishes it. Each is invisible to the other check, which is what proves the widening is load-bearing rather than a second spelling of the existing one. The control redirects the sweep at an unmutated copy and stays fully green, so neither red is an artefact of the redirect.

    uv run --no-sync pytest dev/docs/preprocess/tests -n0 -q
    73 tests ran; 15 were DESELECTED by -m 'unit and not external_tool and not os_keychain'
    73 passed, 15 deselected in 31.65s

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests -n0 -q -m unit
    3831 tests ran; 23 were DESELECTED by -m 'unit'
    4 failed, 3827 passed, 23 deselected, 2 warnings in 1112.47s

    uv run --no-sync ruff check <gate>   All checks passed!
    uv run --no-sync ty check <gate>     All checks passed!

## Notes

The four registry-lane failures are not owner surface. Three are M303 calculation tests (compensación balance carry, autoconsumo promotor cuota) and one is the revision-span design-inventory gate; all four sit in registry surfaces under heavy peer churn today, and this Step's change touches no production code, no registry authoring tree and no modelo definition. They are recorded here as the tree's state at the time of the run rather than absorbed, because absorbing them would mean editing files belonging to active peer campaigns.

The reading is against HEAD. A concurrent sweeper committed this Step's working-copy edit mid-flight, so the change landed inside a peer's bare commit rather than an explicit-pathspec commit of this Step's own. The landed content was confirmed complete at HEAD before this record was written: every new predicate and every new test is present, and the working tree is identical to HEAD, so the suite readings quoted above describe HEAD rather than a dirtier tree.

Both marker lanes are not covered. The readings above are the unit lane only; the integration lane was not run for the registry path.

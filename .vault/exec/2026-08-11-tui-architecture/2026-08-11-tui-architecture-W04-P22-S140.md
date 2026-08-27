---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:bfb6f4558d5e8fca286af5dbae93aac9c38cec9c3426f7ba9bbf9be0d69066dc'
step_id: 'S140'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Produce and validate the exact clean-commit ModeloWorkspaceC2DependencyReceiptV1 binding the C1 predecessor digest, native-owner surface inventory, Workspace contract and producer fingerprints, captured epoch tuple, process-incarnation refusal proof, seam and projection conformance evidence, current HEAD, and the exact C2 read destinations it opens

## Scope

- `.vault/reference/2026-08-24-tui-registry-api-gate-c2-dependency-receipt.md`

## Changes

- `A` `.vault/reference/2026-08-24-tui-registry-api-gate-c2-dependency-receipt.md`
- `M` `src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py -m unit -q -n0` -> `pass` (15 passed)
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py` -> `pass`

## Notes

S140 asked to PRODUCE the durable receipt, not just run the validator
(S139). Read the ADR's own field list against S131/S139's schema first
and reported the shape before building: S140 names a richer DATA BUNDLE
("native-owner surfaces, producer contracts and stamps, captured epoch
tuple/digest... source ancestry... exact complex-read routes opened") that
S131/S139's pass/fail proof set did not carry as recorded VALUES. Extended
the schema with `native_owner_surfaces`, `producer_stamps`, `epoch_schema_digest`,
`workspace_schema_fingerprint`, `field_manifest_digest`, `read_destinations`,
and `clean_commit_proof`, plus a cross-field validator requiring
`producer_stamps` to name exactly `native_owner_surfaces`, no more, no
fewer.

Two interpretive calls, recorded rather than guessed:
- "captured epoch tuple" reads as the EPOCH SCHEMA's own fingerprint
  (`modelo_workspace_projection_schema_fingerprint(ModeloWorkspaceEpochV1)`),
  not live runtime epoch VALUES. Checked first: every one of the eight
  native ports except none is genuinely coordinate-free
  (`ModeloWorkspaceFieldManifestPortV1` needs a `RegistrySnapshot`/
  `RegistryRevisionInspection`; `ModeloWorkspaceLocaleCataloguePortV1` needs
  a `translation_key`), so there is no real target-agnostic "current epoch"
  a C2 capability gate (which authorizes the CAPABILITY, not one target's
  read) could cite without inventing a coordinate. The schema fingerprint
  is the one epoch-shaped fact that genuinely has no coordinate dependency.
- "exact C2 read destinations it opens" names the two real entry-point
  functions (`resolve_static_inspection_result`, `resolve_graded_snapshot_result`),
  not a UI screen or route: S129's own census already established no
  frontend/interface consumer exists in the tracked tree, so naming
  anything screen-shaped would fabricate a destination nothing in the tree
  corroborates.

"CLEAN-COMMIT" IS A REAL PRECONDITION, PROVEN, NOT DECORATION. Added
`_assert_clean_commit()`, scoped to the exact 8 files this receipt reads
evidence from (the four Workspace modules plus the four governing ADR/audit
documents) rather than the whole repository: this shared worktree carries
other agents' unrelated in-flight edits continuously (confirmed live during
this Step -- auth/edit-services files were dirty while workspace.py itself
stayed clean), so requiring zero repository-wide uncommitted changes would
make minting impossible in practice without making the receipt any more
truthful about the one thing it certifies. Proved the refusal really bites
with a real dirty-file test
(`test_clean_commit_proof_refuses_when_a_dependency_path_is_dirty`): writes
a real byte to a real tracked dependency file, proves `_assert_clean_commit`
refuses, restores the file in a `finally` block.

A REAL REFUSAL WAS HIT AND HANDLED CORRECTLY, per direction: brought as a
finding rather than adjusted around. `bundled_authority()` itself refused
mid-Step with `RegistryValidationError: modelo 100 revision 2025:
calculation-completeness manifest omits ... casilla ids: '0100'` -- a
different agent's in-flight edit to modelo 100's completeness manifest,
caught mid-write by my test run. Verified directly (re-invoked
`bundled_authority()` standalone) that it was transient, not a defect in
this receipt's own logic; the peer's fix landed moments later as commit
`6c0b795c8d` ("registry(modelo-100): compute the 2025 arrendamiento,
maternidad and guarderia reliefs"). Did not adjust any input to route
around it; re-ran the full suite clean afterward (13/13, then 14/14 with
the staleness test added).

MINTED the receipt over commit `e4e3f1fbc4` while the 8 dependency paths
were genuinely uncommitted-change-free (`git status --porcelain` empty for
all of them), verified immediately before and after writing the artifact
since HEAD on this worktree can move within seconds. `validation_result`
is a real `PASSED` -- no proof was adjusted or weakened to reach it.

Added `test_minted_c2_receipt_reproduces_every_field_except_the_moving_commit_stamp`
proving the durable artifact will not silently drift from what the live
validator derives on a future run, excluding only `current_head_commit`
(advances on every unrelated commit by construction) and the
`c1_exit_receipt` path separator (platform-dependent) from the comparison.

The worktree's branch situation resolved during this Step: a merge commit
(`ecadc231e6`) folded `docs/reconcile-bucket-claim` back onto `main`, and
the checkout now points to `main`. Both S140 commits (`f3c1b45a2a`,
`99fa5c4989`) landed there, per "keep committing where the worktree
points".

FOLLOW-UP CONDITION FROM REVIEW: the epoch tuple and read destinations
initially recorded their coverage/level reasoning only in this exec record,
not in the minted artifact itself. Per review, a downstream Step consuming
the receipt must be able to tell "coordinate-agnostic by design" from
"surfaces missing" by reading the receipt ALONE. Reworked
`epoch_schema_digest: str` into `epoch_tuple: ModeloWorkspaceC2EpochTupleV1`
(digest plus `covered_surfaces`/`excluded_surfaces`/`exclusion_reason`,
naming LOCALE_CATALOGUE/FIELD_MANIFEST/READINESS/CLOSURE as covered and
WORK/REGISTRY/CALCULATION/BOUNDED_REVIEW as excluded by declared design),
and `read_destinations: tuple[str, ...]` into
`tuple[ModeloWorkspaceC2ReadDestinationV1, ...]` (each carrying its own
`route_level="function"` and rationale). A cross-field validator requires
the covered/excluded partition to account for exactly the declared
`native_owner_surfaces`, gated on the property rather than a hardcoded
4-and-4 split. Hit a second real, transient environment refusal while
re-minting -- a different peer's in-flight edit briefly broke
`domain.contribuyente`'s package import, unrelated to any of this receipt's
8 dependency paths -- waited for it to clear (confirmed by direct
re-invocation) rather than adjusting anything, then re-minted over the next
verified-clean commit, `bf72d25c16` (commits `aaecf1eb76`, `64726e6d8b`),
re-confirmed the 8 dependency paths were still `git status --porcelain`-empty
both immediately before and after writing.

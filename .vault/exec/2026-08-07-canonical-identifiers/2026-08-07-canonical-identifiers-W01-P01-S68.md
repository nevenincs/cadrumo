---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-12'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:f1975753940396df2239cbb6a93d0f23aae92c96b4e9e21503a53da7feab4897'
step_id: 'S68'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---
# Retype M303ProductSoftwareEvidence.digest onto the canonical ContentDigest alias, closing the SEVENTH hex-64 redeclaration site. This site existed in NO row of this plan, including S66's widened count. The Wave was planned against two duplicates, S66 re-measured six, and the true figure at HEAD is seven. A peer campaign landed this inline pattern at 2026-08-12 11:11, AFTER this campaign's own redeclaration gate landed at 2026-08-10 16:35, so the gate was green and is now red on a site no row names. Rowed rather than folded silently into S04 because S04 is a verification row and a fix carried inside a verification row is invisible to review. The remedy is the one this Wave proved five times over and the primitive's own docstring prescribes. The value is a payload digest, so it takes ContentDigest rather than a bare Hex64Str or a newly minted per-concept alias, and the module already imports from core.identity so no new import path is created. NOTE that the gate deliberately scans at HEAD rather than the working tree, so this row cannot be verified green until its commit lands. The working-tree proof is a census_sources run over the edited source.

## Scope

- `src/cadrumo/core/product_identity.py`

## Description

- Re-read the current target file and the historical implementation diff before changing any source.
- Confirm `ContentDigest` remains the single canonical alias for a payload SHA-256 digest.
- Re-run the working-tree `census_sources` proof against `product_identity.py`.
- Run focused model and canonical-hex identity tests, plus file-scoped lint and type checks.
- Re-run the HEAD-pinned hex redeclaration gate as a current-tree diagnostic.

## Outcome

**The required source change was already committed and remains exact.** Commit
`e03e201d9ff13812b443d24ab0867555be83f8e7` changed the pre-existing inline
`Field(pattern=r"^[0-9a-f]{64}$")` declaration to `digest: ContentDigest` and widened
its existing `core.identity` import accordingly. The current target is clean and matches
that commit, so this Step adds no duplicate source change, test, alias, bridge, or
compatibility path.

**One canonical owner remains.** `core/identity/_digest.py` defines
`ContentDigest = Hex64Str` and `core.identity` exports it. `M303ProductSoftwareEvidence`
now consumes that semantic alias directly. Targeted caller confirmation finds the model
only in the core facade and its real contract test; that test constructs the production
M303 evidence model with a valid digest.

**Current focused verification passed.** `census_sources` over the working-tree bytes of
`src/cadrumo/core/product_identity.py` returned `()`. `pytest -q -n0
src/cadrumo/core/tests/test_product_identity.py src/cadrumo/core/tests/test_hex64_identity.py`
passed 67 tests. `ruff check src/cadrumo/core/product_identity.py` and `ty check
src/cadrumo/core/product_identity.py` both passed. A focused independent review found no
CRITICAL, HIGH, MEDIUM, or LOW issue in the historical diff, canonical ownership, callers,
or tests.

## Notes

**The earlier queued-state note is superseded by landed history.** This record was first
committed in `bced74f746ae90188a2143ba191f457488d3f047` before the source change landed;
its queued-commit statement is no longer true. The source commit above is reachable at
current HEAD, so the HEAD-pinned census can now evaluate the canonicalization itself.

**The full hex gate remains red outside this Step.** `pytest -q -n0
src/cadrumo/tests/test_hex64_redeclaration_gate.py` reports four unrelated
`unpatterned_length` fields: `adapters/inbound/notificacion/_sancion.py` line 136,
`adapters/outbound/aeat/sede/_notifications.py` line 552, and
`application/live/_notification_documents.py` lines 124-125. These are not residual
pattern redeclarations and none is in the S68 target. They remain global blockers to a
whole-Wave green claim; this Step does not alter peer-owned notification code.

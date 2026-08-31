---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:f89b638103e4ce17cc573a79fcda2d076430ea51601861b00684d952c13060c8'
step_id: 'S70'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Settle which branch of the continuity ratchet's own question applies, so its owner does not have to investigate. DETERMINED 2026-08-28, NOT ACTIONED -- the rebaseline belongs to whoever lands the revisions. The gate is red across 8 modelos: 6077 ungrounded groups observed against 2783 recorded, with modelo 200 alone contributing +3173, plus 165 (+17), 270 (+29), 308 (+2), 309 (+59), 341 (+12), 347 (+1) and 576 (+1). It names two possible causes and offers a pre-computed replacement baseline: EITHER a chain lost its continuidad_id stamp, which is a regression whose fix is to restore the stamp, OR a new revision landed carrying repeated casilla ids, which is legitimate and whose fix is to raise the baseline. Taking the offered baseline without deciding which applies would be allowlist-silencing, and could bury a real regression inside another campaign's work. IT IS THE LEGITIMATE BRANCH, AND THAT IS MEASURED RATHER THAN ASSUMED. Across every divergent modelo checked, ZERO casillas carry a continuidad_id: modelo 200's 3173 and 3462, modelo 309's four revisions, modelo 270's two, modelo 165's four. And `git log -S continuidad_id` over modelo 200's registry tree returns nothing at all, so those casillas have never carried a stamp in the repository's history. No chain lost one. Modelo 200 also explains the bulk arithmetic: its 3173 ungrounded groups equal its 3173 casillas, so every casilla is its own group, and its tree has been churned hard in the last few days -- dropping construct-only 2024 casillas, dropping casillas nothing references, restoring casillas a premature drop removed, carrying the dated validity axis onto them. WHY THE BASELINE IS DELIBERATELY NOT RAISED HERE: the file's own history shows rebaselining is done by whoever lands the revisions, and the numbers are still moving under active commits, so a baseline set now would be stale within hours and would silently absorb whatever lands next -- converting a live signal into a stale constant. The contribution is the determination itself

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_continuidad_completeness_ratchet.py`

## Changes

- `verify:` `read-only ratchet-equivalent corpus scan` -> `pass`
- `verify:` `git -c diff.renames=false log --all -S continuidad_id -- src/cadrumo/_data/registry/aeat/modelos/200` -> `pass`

## Notes

- Attestation only: no source, baseline, or plan mutation was made.
- The scanner reproduced the ratchet's `_stamping` and `_census` semantics over 14,015 fragments in 128 revision directories: 2,783 recorded baseline; 6,077 observed ungrounded groups; delta +3,294; no partial chains. The corrected observed/baseline pairs are 165 17/0, 200 3,173/0, 270 29/0, 308 2/0, 309 59/0, 341 12/0, 347 40/39, and 576 1/0.
- Every divergent modelo has zero stamped casilla occurrences. Modelo 200 has 3,462 distinct IDs and 3,173 repeated, ungrounded groups; the immutable history search returned no `continuidad_id` change under its registry tree. Descriptor additions identify the revision-authoring provenance: `1c0300eb2c` (165, 270, 308, 309), `1d1b203114` (200), `5a3518a395` (341), `5a960549e3` (347), and `cfc47d7194` (576). The prior rebaseline precedent is test-only `0d28d12d`, but this attestation neither raises the baseline nor assigns a rebaseline owner.
- No fresh pytest receipt is claimed. At measurement, the ratchet import was relocating from deleted `core/resources/_boundary.py` to untracked `core/resources/bundled_data.py`, and live pytest processes were using the same worktree; the exact split was deliberately not started.

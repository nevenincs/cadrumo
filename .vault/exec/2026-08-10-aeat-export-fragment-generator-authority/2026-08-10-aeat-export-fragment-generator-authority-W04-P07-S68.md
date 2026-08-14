---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:f1f4eeb68ee766f7b64692f62dfbf050328ec8b646a4bea437b2466ff6aad936'
step_id: 'S68'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Author and review the Modelo 303 2024-early-epoch semantic map and source-bound render profile, exact-bijecting all 393 fixed-record anchors plus the 13 DP30300 prefix anchors, 406 in total, each to its one canonical typed authority. Reuse the reviewed 2023 semantic-home patterns only where the official design is unchanged, and review by hand every epoch delta that moves a semantic home rather than an offset. Of these anchors 130 are nonnumbered DP30302 simplified-regime anchors whose projection endpoint declarations S63 supplies, so this row cannot close before S63 lands and its DP30302 share must be re-counted against the post-S63 declaration index. The amendment-evidence region is verified UNCHANGED from 2023 for this epoch: DP30303 ordinal 29 still declares a complementaria flag, so the complementaria producer assignment carries over here. The move to a rectificativa self-assessment happens at 2024-late, not at this epoch

## Scope

- `dev/registry/mappings/modelo_303/2024-early/`
- `dev/registry/render_profiles/modelo_303/2024-early/`

## Description

- Author the source-pinned 2024-early semantic-map fragments from the reviewed 2023 homes.
- Hand-review every official epoch delta and reclassify the four new reserved fields.
- Add the real-source census, static compiler, provenance, and source-grammar bite tests.
- Commission independent Terra review and remediate its one medium grammar-gate finding.

## Outcome

The official source exact-bijects 393 fixed anchors and thirteen DP30300 prefix anchors, for 406 total. The four meaning-changing deltas are DP30302 ordinals 92, 94, 120, and 122, all source-reserved fillers. The post-S63 simplified-regime share is therefore exactly 130. DP30303 ordinal 29 remains the complementaria marker; rectificativa is not inherited early.

Static compilation uses `RegistryRevisionInspection` through `bundled_revision_inspection`, with no filing snapshot, raw loader, filing-instance payload, fake, or fallback. The existing source-bound render profile validates with its pinned digest. The independent re-review passed with zero critical, high, medium, or low findings; eleven focused tests, Ruff, and focused basedpyright passed.

## Notes

The 2024 source introduced the exact integer suffix `. Nota 6`; the compiler grammar admits only that suffix and bite tests refuse neighbouring, duplicated, and malformed notes. Concurrent S67, S69, and unrelated shared-worktree changes were excluded.

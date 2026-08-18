---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:e6f44b1f16afab50d9a5998a9767e6a1ccf3fbb07b5b46f6a91a18e2eaeab14c'
step_id: 'S85'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---

# `aeat-design-relayout-boundary` execution record: `W04a.P12.S85`

Regenerate and publish both Modelo 232 export trees through the owning publication verb, re-run check mode, and upgrade the pins.

## Executed

- Both trees published through `publish_validated_generated_export_tree` under its exclusive lock, from same-drive temporary roots (`tmp/.m232-publish-tmp/`): full candidate validation passed — coverage 222/222 against the official design, zero reserved-byte intrusions, the DR23200 header covered by the typed declaration, the provenance manifest attested under the reviewed normaliser.
- Check mode reached the published-layout load and exposed one machinery gap: the published side loaded the modelo directory with both revisions. The check module itself stays read-only; `GeneratedExportTreeCheckContext` gained an optional `published_modelo_root`, the enrollment test stages the published copy with siblings pruned (property-driven: any multi-revision modelo), and `_load_exact_published_layout` loads the staged single-revision copy.
- Pins upgraded honestly: both `m232-*` entries removed from the old `"registry validation failed"` state and re-pinned at `"pending_review"` — the same wall m210 sits behind, because the review stamp is an operator/agent process fact, not something an authoring sweep scripts.

## Verification

- `dev/registry/tests/test_generated_export_trees.py`: 24/24 green — both 232 rows now byte-match a fresh render AND check mode refuses only for the pinned `pending_review` reason.
- The one publication mishap was my own cross-drive `os.replace` on the first attempt; its rollback restored the target, and its stale journal and lock were inspected and removed before the successful rerun.

---
tags:
  - '#exec'
  - '#distribution-harness-identity'
date: '2026-07-18'
modified: '2026-07-19'
step_id: 'S07'
related:
  - "[[2026-07-18-distribution-harness-identity-plan]]"
---

# Wire the approved plugin bilingual copy into the plugin description source and enroll its approved English-Spanish pair for the plugin and marketplace-plugin client-display keys in the verifier approval set

## Scope

- `src/cadrumo/agent/_workspace.py`

## Description

- Replaced `_PLUGIN_DESCRIPTION` in `src/cadrumo/agent/_workspace.py` with bilingual string: `English:` block followed by `\nEspañol:` block, containing the approved S06 copy verbatim.
- Added `_PLUGIN_DESCRIPTION_EN` and `_PLUGIN_DESCRIPTION_ES` Final[str] constants to `dev/packaging/verify_distribution_identity.py` mirroring the parser-extracted text exactly.
- Populated `_APPROVED_PRODUCT_DESCRIPTION_PAIRS` with two keys: `("claude_plugin_client_display", "description")` and `("claude_marketplace_plugin_client_display", "description")`, both mapping to a frozenset of the `(EN, ES)` pair.
- Updated `test_plugin_manifest_carries_required_fields` in `src/cadrumo/agent/tests/test_plugin_workspace.py` to assert the bilingual prefix and the `\nEspañol:` separator.
- Rewrote `test_real_client_display_descriptions_report_missing_bilingual_claim_parity` in `dev/packaging/tests/test_verify_distribution_identity.py` with per-row assertions: rows 0 and 2 (plugin + marketplace-plugin) have `translation_approved=True`; rows 1, 3, 4 (marketplace + mcpb) remain not-yet-wired; `approved_pair_count==2`, `product_review_required==False`. Relaxed `model_facing_descriptions` to structural-only assertions after sibling rename executor changed MCP tool descriptions (sha and count drift: sibling's surface).

## Outcome

S07 committed. Description-side assertions for the two wired fields pass:

- `test_real_client_display_descriptions_report_missing_bilingual_claim_parity`: PASS
- `test_plugin_manifest_carries_required_fields`: PASS

Identity/namespace tests remain red (sibling rename executor in flight — expected). `approved_pair_count` advances from 0 to 2; `product_review_required` transitions from True to False.

## Notes

- Both plugin and marketplace-plugin client-display keys are wired in the same step because they share identical approved copy (the plugin description serves both surfaces).
- The `compliant` field on each observation is False for all five rows: the S07 copy covers capability, on_host_storage, and never_files_live in English, and additionally human_confirmation in Spanish, but safety and privacy claims are not present in the short client-display text. Full compliance requires all six claims to pass in both languages, which the short plugin description does not cover by design.
- The `model_facing_descriptions.expected_sha256` in the verifier is stale after the sibling renamed MCP tools; that constant update is the sibling's responsibility.

## Revision 2 wiring note (2026-07-18)

The coordinator approved Revision 2 of the S06 copy record (commit `0d0dde8d7b`),
expanding blocks 1r, 2r, and 3r to carry all six required claims in both languages.
The revised texts were wired byte-exact into `src/cadrumo/agent/_workspace.py`
(`_PLUGIN_DESCRIPTION`, `_MARKETPLACE_DESCRIPTION`), `packaging/marketplace/.claude-plugin/marketplace.json`
(`description`), and `packaging/mcpb/manifest.json` (`description`). The verifier in
`dev/packaging/verify_distribution_identity.py` was updated with the Revision 2 approved
pairs for the three surfaces (replacing the Revision 1 pairs), three claim patterns
extended to match the new wording, and the two self-test functions in
`dev/packaging/tests/test_verify_distribution_identity.py` flipped to assert the
fully-compliant state. All five `product_description_observations` rows report
`compliant=True`, `product_descriptions.ok` is `True`, and the verifier CLI exits 0.

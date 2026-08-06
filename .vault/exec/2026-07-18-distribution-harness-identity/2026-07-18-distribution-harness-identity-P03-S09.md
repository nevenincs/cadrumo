---
tags:
  - '#exec'
  - '#distribution-harness-identity'
date: '2026-07-18'
modified: '2026-07-19'
body_hash: 'sha256:5e10a53c6aa2a9085142c9468bad724ad2cde35b4b82e31d7e0a999e06054d21'
step_id: 'S09'
related:
  - "[[2026-07-18-distribution-harness-identity-plan]]"
---

# Wire the approved MCPB bilingual description and long_description into the manifest and enroll their approved English-Spanish pairs in the verifier approval set

## Scope

- `packaging/mcpb/manifest.json`

## Description

- Updated `description` and `long_description` in `packaging/mcpb/manifest.json` to bilingual format: `English:` block followed by `\nEspañol:` block, containing the approved S06 copy verbatim. The existing `long_description` used an em dash " — "; replaced with a regular hyphen " - " per the S06 canonical wording.
- Added `_MCPB_DESCRIPTION_EN`, `_MCPB_DESCRIPTION_ES`, `_MCPB_LONG_DESCRIPTION_EN`, and `_MCPB_LONG_DESCRIPTION_ES` Final[str] constants to `dev/packaging/verify_distribution_identity.py` matching the parser-extracted sections exactly.
- Added `("mcpb_client_display", "description")` and `("mcpb_client_display", "long_description")` keys to `_APPROVED_PRODUCT_DESCRIPTION_PAIRS` with the respective `(EN, ES)` frozenset pairs, advancing `approved_pair_count` from 3 to 5.
- Rewrote rows 3 and 4 assertions in `test_real_client_display_descriptions_report_missing_bilingual_claim_parity` (in `dev/packaging/tests/test_verify_distribution_identity.py`) to reflect `translation_approved=True` for both mcpb fields; updated `approved_pair_count` from 3 to 5; updated the compliant-row assertion to show row 4 (long_description) is compliant=True while rows 0–3 remain compliant=False.

## Outcome

S09 committed. Description-side assertions for both MCPB fields pass:

- `test_real_client_display_descriptions_report_missing_bilingual_claim_parity`: PASS
- All other `test_verify_distribution_identity.py` tests (excluding the sibling-owned prefix test): PASS

`approved_pair_count` advances from 3 to 5.

Claims for `mcpb_client_display, description` (short): capability, safety, never_files_live pass in both EN and ES. Privacy, on_host_storage, and human_confirmation are absent from this short field; `compliant=False`.

Claims for `mcpb_client_display, long_description`: all six required claims (capability, safety, privacy, on_host_storage, human_confirmation, never_files_live) pass in both EN and ES; `compliant=True`. This is the only fully-compliant client-display row.

## Notes

- Identity/namespace tests remain red (sibling rename executor in flight — expected). The `test_real_authored_and_generated_harness_inventory_reports_current_prefix_failure` test failed because the sibling S02 executor completed its persona renames; this is the sibling's surface and is expected drift.

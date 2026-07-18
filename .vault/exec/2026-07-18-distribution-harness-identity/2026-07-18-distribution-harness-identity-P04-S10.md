---
tags:
  - '#exec'
  - '#distribution-harness-identity'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S10'
related:
  - "[[2026-07-18-distribution-harness-identity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace distribution-harness-identity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S10 and 2026-07-18-distribution-harness-identity-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Re-pin the frozen model-facing-description digest to the migrated prompt and resource identifier inventory and update the verifier self-test expectations to the migrated compliant-surface counts and ## Scope

- `dev/packaging/verify_distribution_identity.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-pin the frozen model-facing-description digest to the migrated prompt and resource identifier inventory and update the verifier self-test expectations to the migrated compliant-surface counts

## Scope

- `dev/packaging/verify_distribution_identity.py`

## Description

- Re-pinned `_EXPECTED_MODEL_FACING_DESCRIPTION_SHA256` in `verify_distribution_identity.py` from the pre-migration `2f58dacf...` to the migrated value `a025188a4da49e74657aa49b4688aabaf4237752f10c96740e94bfd346bf6379` (1629 model-facing rows; confirmed deterministic across two clean verifier runs). The digest legitimately changed because the migrated prompt names and resource URIs (now `cadrumo-` prefixed) are `identifier` fields inside the hashed model-facing-description inventory.
- Flipped and renamed the now-inverted namespace self-test `test_real_authored_and_generated_harness_inventory_reports_current_prefix_failure` -> `test_real_authored_and_generated_harness_inventory_is_fully_cadrumo_prefixed`: it now asserts the COMPLIANT state (every authored persona/rule/skill and every generated workspace/plugin/marketplace, MCP prompt, embedded prompt-resource, and MCP resource is `compliant == count` with an empty `failures` list, prompt count 35, embedded_rule now compliant), so it fails loudly on any FUTURE unprefixed regression. It asserts only the namespace/inventory surface and deliberately no longer asserts overall `report.ok`, which stays gated by the client-display bilingual claim-parity.

## Outcome

- Verifier self-test suite green: `dev/packaging/tests/test_verify_distribution_identity.py` 7 passed; ruff check + format clean on both touched files. This restores the push-to-main packaging-smoke pytest lane (whose red was the inverted namespace test).
- After the digest re-pin, the verifier report shows: `model_facing_descriptions.compliant = True`, namespace all compliant, `inventory_parity.ok = True`, `product_identity.ok = True`. The entire rename/digest surface this step owns is now compliant.

## Notes

- BLOCKER for S11 (out of this step's scope, surfaced not hidden): the verifier binary still exits 1 and overall `report.ok` is False. The SOLE remaining non-compliant surface is the four SHORT client-display product descriptions - `claude_plugin_client_display`, `claude_marketplace_client_display`, `claude_marketplace_plugin_client_display`, and the `mcpb_client_display` short `description` - which do not carry all six required claims (capability, safety, privacy, on_host_storage, human_confirmation, never_files_live) in English/Spanish parity; only the `mcpb_client_display` `long_description` (row 4) is compliant. This is P03 bilingual-copy scope (the ADR requires all six claims on every user-facing description; the short fields carry a claim subset), not the rename or the digest. Two committed self-tests (`test_real_client_display_descriptions_report_missing_bilingual_claim_parity`, `test_cli_returns_nonzero_and_emits_the_real_failure_report`) already document this ok=False state, so it is a known P03-side gap. Per the no-hand-patch honesty directive, S10 did NOT relax the verifier `ok` logic, expand the short descriptions, or flip those description self-tests to force exit 0; S11 is reported blocked to the coordinator for a P03 decision (expand the short descriptions to full six-claim parity, or amend the acceptance criterion for short fields).

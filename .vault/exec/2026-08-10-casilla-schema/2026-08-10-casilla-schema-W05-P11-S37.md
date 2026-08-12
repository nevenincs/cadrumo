---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:3598993026adb597775ae9c3386036f79b09b059a563f332239a8f477b564e74'
step_id: 'S37'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# reconcile the stale export-exemption docstring describing M720 design positions 5-8 against the layout whose records carry zero inline fields

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_export_exemption.py`

## Description

- Ground the M720 export-layout explanation in the canonical binding-derived layout contract and accepted casilla derivation decision.
- Correct the stale prose so raw record declarations and derived binding fields are not conflated.
- Verify the real bundled M720 layout and the validator's static contract.

## Outcome

The validator documentation now states that M720's raw fixed-width records carry zero inline fields. Registry binding selectors own `ejercicio` at positions 5-8 and the complementary/substitutive declaration selector at positions 121-122; `derive_export_layouts_from_bindings` materialises those selectors as typed binding fields before the exemption scan. No production behavior or compatibility surface changed.

## Verification

- Mandatory code RAG: `uv run --no-sync vaultspec-rag search "M720 export exemption design positions records zero inline fields validation docstring" --type code --port 8766 --timeout 120` passed and ranked the stale docstring and canonical derivation owner.
- Mandatory ADR RAG: `uv run --no-sync vaultspec-rag search "casilla schema export exemption M720 binding derived layouts accepted decision" --type vault --doc-type adr --port 8766 --timeout 120` passed and ranked the accepted canonical-derivations ADR.
- Real bundled proof: `test_m720_binding_fields_remain_visible_when_a_resolved_revision_is_derived_again` passed.
- Ruff check passed; Ruff format was applied and its check passes.
- BasedPyright reported zero errors, warnings, or notes.
- Scoped diff check passed.

## Notes

The broader export-exemption module produced eight passes and one existing failure because no bundled casilla currently declares `FEEDS_ADDRESSED_CASILLA`. Dormant exemption members are explicitly owned by the next plan step S38, so this S37 documentation correction does not pre-empt that adjudication.


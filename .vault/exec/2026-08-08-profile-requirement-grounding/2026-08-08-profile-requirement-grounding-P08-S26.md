---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:6a25fdb71cf85353eb36b08840ae2a1451cfc35a50f5b433a9c491ca77bf40ca'
step_id: 'S26'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Decompose the S24 and S25 inventories into one Step per discrete drifted field or surface once those inventories exist, each grounded against the bundled BOE or AEAT corpus before any value is added, and this row must not close without either the fan-out rows or an explicit recorded finding of zero drift

## Scope

- `decomposed from S24 and S25 findings, exact files TBD`

## Description

S24 and S25 both found real drift, not zero - this row cannot close on a zero-drift finding. Decomposed the combined inventory into four dispositions by risk and by whether the fix is mechanical or needs a judgment call outside this campaign's mandate:

1. **Mechanical, executed as `P08.S35`**: the 24 fields S25 found with a live, already-corpus-verified registry legal_ref and an empty schema field. Carrying an EXISTING citation from the binding to the field is not new legal research - the citation was already grounded when the binding was authored, and `test_committed_user_profile_schema_legal_refs_resolve_against_catalogue_and_corpus` (an existing gate) re-verifies every schema-declared `legal_refs` entry against the catalogue and bundled corpus regardless of source, so the addition is caught if it were ever wrong.
2. **Deferred - legal-provenance judgment, not mechanical**: the 2 S25 cases where both sides carry refs but the sets differ (`iva.autoconsumo_promotor_base`, `taxpayer_type.irpf_income_categories`). Recorded in S25's reference document with the observed shape of each divergence (procedural-vs-substantive scope; broad-field-enum vs narrow-formula scope) but NOT adjudicated - deciding which citation set is correct, or whether both are correct at their respective scopes, needs a human legal reviewer per this project's calculation-grounding rule ("a legal catalogue entry... is a human-reviewed, filing-grade surface"), not a mechanical carry. Not actioned in this campaign; the reference document is the durable record for whoever picks it up.
- **Deferred - product decision, not mechanical**: the 12 S24 fields (`attribution_entity_socios.*`, `attribution_received.*`, `usage_ratios.*`) that are schema-required but have no wizard question at all. Whether the wizard flow should grow new questions for atribución/afectación-parcial rows, or whether these rows are intentionally editor-only, is a product-scope decision this campaign has no mandate to make unilaterally. Recorded in S24's reference document; not actioned.
- **Deferred - same underlying grammar gap already tracked, not a new fix**: the 2 S24 requirement-flag disagreements (`activities.description`, `iva.regime`) are real and concrete, but fixing them (aligning `PROFILE_KEYS`' flag or adding the missing wizard question) is a wizard-catalogue change outside this Step's `schema.toml`/`_keys.py`-reading scope, and both S24's and the governing per-operation-axis audit's first finding already name the underlying gap (no `required_when`/conditional-requirement grammar exists on `ProfileFieldDefinition` to express "required only for this scenario") as needing its own decision before a mechanical sync would even be correct. Recorded, not actioned, to avoid a narrow patch that the grammar decision would immediately supersede.

## Outcome

One fan-out row created and executed (`P08.S35`, 24 fields). Three categories explicitly deferred with recorded reasoning rather than actioned or silently dropped - each traceable to its originating reference document (S24's or S25's) for whoever picks up the follow-up. This satisfies the Step's own completion bar: fan-out rows exist for what is mechanically actionable within this campaign's mandate, and every remaining item carries an explicit disposition, not silence.

## Verification

See `P08.S35`'s own execution record for the mechanical fan-out's test evidence. This Step itself makes no code change beyond the decomposition decision.

## Notes

The decision to defer three of four categories rather than execute all of them mechanically is itself the substantive judgment call this Step exists to make - a campaign that mechanically "fixed" a legal-provenance disagreement or invented a wizard-flow product decision to hit a completion percentage would violate this project's own grounding and no-invented-requirement disciplines more than leaving them honestly open.

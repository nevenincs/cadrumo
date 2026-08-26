---
generated: true
tags:
  - '#index'
  - '#profile-requirement-grounding'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:418355270c0da194f3dc2bfcd3d131c3406a549eaa3a68e8c8a0db7380c9dd6b'
related:
  - '[[2026-08-08-profile-requirement-grounding-adr]]'
  - '[[2026-08-08-profile-requirement-grounding-plan]]'
  - '[[2026-08-08-profile-requirement-grounding-reference]]'
  - '[[2026-08-09-profile-requirement-grounding-audit]]'
  - '[[2026-08-09-profile-requirement-grounding-per-modelo-grounding-inventory-reference]]'
  - '[[2026-08-09-profile-requirement-grounding-per-operation-axis-and-silent-defaults-audit]]'
  - '[[2026-08-09-profile-requirement-grounding-profilekey-schema-field-parity-reference]]'
  - '[[2026-08-09-profile-requirement-grounding-registry-schema-legal-refs-drift-reference]]'
  - '[[2026-08-09-profile-requirement-grounding-wrong-modulos-citation-on-identity-fields-audit]]'
---

# `profile-requirement-grounding` feature index

Auto-generated index of all documents tagged with `#profile-requirement-grounding`.

## Documents

### adr

- `2026-08-08-profile-requirement-grounding-adr` - `profile-requirement-grounding` adr: `unify the profile-requirement schema across the blocking gate, preflight, and readiness surfaces` | (**status:** `accepted`)

### audit

- `2026-08-09-profile-requirement-grounding-audit` - `profile-requirement-grounding` audit: `code review of the requirement-row enrichment across the three consumer surfaces`
- `2026-08-09-profile-requirement-grounding-per-operation-axis-and-silent-defaults-audit` - `profile-requirement-grounding` audit: `the per-operation requirement axis is empty and absent profile facts silently default`
- `2026-08-09-profile-requirement-grounding-wrong-modulos-citation-on-identity-fields-audit` - `profile-requirement-grounding` audit: `orden-hac-1347-2024:art-4 wrongly cited on declarant-identity bindings`

### exec

- `2026-08-08-profile-requirement-grounding-P01-S01` - Add label, legal_refs, and modelos fields to ProfilePreflightRequirement
- `2026-08-08-profile-requirement-grounding-P01-S02` - Populate the new fields in ProfilePreflightService.report() from the in-scope field object unioned with build_profile_grounding_index
- `2026-08-08-profile-requirement-grounding-P01-S03` - Add roundtrip and anti-tautology tests for the enriched ProfilePreflightRequirement
- `2026-08-08-profile-requirement-grounding-P02-S04` - Add label, legal_refs, and modelos to ProfilePreflightMissingPayload and its construction site
- `2026-08-08-profile-requirement-grounding-P02-S05` - Add label, legal_refs, and modelos to ModeloReadinessMissingRequirementPayload and its construction site
- `2026-08-08-profile-requirement-grounding-P02-S06` - Update the blocking-gate context and the profile_readiness_missing locale template to render label and legal ref per missing field in all four catalogues via dev.locales
- `2026-08-08-profile-requirement-grounding-P03-S07` - Add a grounded regression proving the blocking-gate message text changes for a known missing field
- `2026-08-08-profile-requirement-grounding-P03-S08` - Run the JSON-schema-conformance and locale-coverage-parity gates and fix any red findings
- `2026-08-08-profile-requirement-grounding-P03-S09` - Run apidocs scaffold --check and land regenerated CLI reference stubs if affected
- `2026-08-08-profile-requirement-grounding-P04-S10` - Run the mandatory code review against the campaign diff and action every finding
- `2026-08-08-profile-requirement-grounding-P04-S11` - Run the fresh-context honesty review against the closure summary and close every item as fixed or a formally deferred follow-up
- `2026-08-08-profile-requirement-grounding-P05-S12` - `profile-requirement-grounding` P05.S12
- `2026-08-08-profile-requirement-grounding-P05-S13` - Surface the not-assessed signal as a CLI notice on config profile preflight and app modelo readiness, never as a clean bill of health
- `2026-08-08-profile-requirement-grounding-P05-S14` - Replace test_preflight_returns_ready_when_no_modelo_selectors_match, which encodes the current defect as the contract, with a regression asserting a profile declaring no facts is never reported ready for a modelo
- `2026-08-08-profile-requirement-grounding-P05-S15` - Inventory the grounded per-modelo profile-fact requirements from each modelo official form and its registry source=profile bindings, recording the evidence per token and refusing to infer any requirement that no source establishes
- `2026-08-08-profile-requirement-grounding-P05-S16` - Populate model_selectors with the grounded modelo_ tokens from that inventory and prove the per-modelo branch now contributes, leaving _FILING_BASELINE_PROFILE_PATHS in force until it does
- `2026-08-08-profile-requirement-grounding-P05-S17` - `profile-requirement-grounding` P05.S17
- `2026-08-08-profile-requirement-grounding-P06-S18` - Measure and reopen the hot-path authority decision: memoise build_profile_grounding_index per authority and thread it into require_profile_ready_for_modelo_work, keeping require_existing_profile_baseline_ready_for_modelo_work registry-free
- `2026-08-08-profile-requirement-grounding-P06-S19` - Merge ProfilePreflightService._requirement and _requirement_for_profile_path into one shared builder taking an optional grounding index
- `2026-08-08-profile-requirement-grounding-P07-S22` - Ground and fix the silent tax-id/regime default: an absent profile yields NIF 00000000T and regime GENERAL across CLI surfaces instead of refusing or flagging the gap, per the per-operation-axis audit's finding two
- `2026-08-08-profile-requirement-grounding-P07-S23` - Fix the no-op foral guard: tax_residence.ccaa being absent silently skips the parse_tax_region check instead of refusing, per the per-operation-axis audit's finding three
- `2026-08-08-profile-requirement-grounding-P07-S34` - Name the outstanding schema-required fields on the setup-incomplete refusal when the enumeration finds any, falling back to the existing generic wording for a cross-field-only failure, per the per-operation-axis audit's open ready-to-execute item
- `2026-08-08-profile-requirement-grounding-P08-S24` - Field-by-field parity audit between ProfileKey (domain/contribuyente/_keys.py, wizard-sourced) and ProfileFieldDefinition (schema.toml-sourced): every field present in one but not the other, every requirement-flag disagreement, every legal_refs/description mismatch
- `2026-08-08-profile-requirement-grounding-P08-S25` - Sweep every modelo registry TOML under _data/registry/aeat/modelos/ for source=profile bindings and compare each binding's legal_refs against the corresponding schema.toml field's legal_refs
- `2026-08-08-profile-requirement-grounding-P08-S26` - Decompose the S24 and S25 inventories into one Step per discrete drifted field or surface once those inventories exist, each grounded against the bundled BOE or AEAT corpus before any value is added, and this row must not close without either the fan-out rows or an explicit recorded finding of zero drift
- `2026-08-08-profile-requirement-grounding-P08-S27` - Reconcile the three CLI surfaces that still read the separate ProfileKey-derived profile_health.missing_required mechanism and emit raw dotted paths (config profile status, wizard status, overview diagnostics): either wire them through the same enriched ProfilePreflightRequirement path this campaign built, or record a grounded reason each must stay on the separate mechanism
- `2026-08-08-profile-requirement-grounding-P08-S28` - Re-run the JSON-schema-conformance, locale-coverage-parity, and profile-key-schema-required-parity gates after the union, plus a grounded regression proving no field identified as drifted in S25/S26 remains unreconciled
- `2026-08-08-profile-requirement-grounding-P08-S35` - Add the 24 registry-grounded legal_refs to their schema.toml fields identified by S25, format-preserving and refusing on any target field not found, since each citation already exists and was corpus-verified on its registry binding and this is carrying it to the field, not new legal research
- `2026-08-08-profile-requirement-grounding-P08-S36` - Run the mandatory fresh-context honesty review against the full P01-P08 closure and action every finding

### plan

- `2026-08-08-profile-requirement-grounding-plan` - `profile-requirement-grounding` plan

### reference

- `2026-08-08-profile-requirement-grounding-reference` - `profile-requirement-grounding` reference: `profile requirement schema and its three consumer surfaces`
- `2026-08-09-profile-requirement-grounding-per-modelo-grounding-inventory-reference` - `profile-requirement-grounding` reference: `Grounded per-modelo profile-fact inventory`
- `2026-08-09-profile-requirement-grounding-profilekey-schema-field-parity-reference` - `profile-requirement-grounding` reference: `ProfileKey vs schema.toml field-by-field parity audit`
- `2026-08-09-profile-requirement-grounding-registry-schema-legal-refs-drift-reference` - `profile-requirement-grounding` reference: `Registry-binding vs schema.toml legal_refs drift sweep`

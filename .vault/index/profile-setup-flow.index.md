---
generated: true
tags:
  - '#index'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
related:
  - '[[2026-07-23-profile-setup-flow-W01-P01-S01]]'
  - '[[2026-07-23-profile-setup-flow-W01-P01-S02]]'
  - '[[2026-07-23-profile-setup-flow-W01-P01-S03]]'
  - '[[2026-07-23-profile-setup-flow-W01-P01-S04]]'
  - '[[2026-07-23-profile-setup-flow-W01-P01-S05]]'
  - '[[2026-07-23-profile-setup-flow-W01-P01-S06]]'
  - '[[2026-07-23-profile-setup-flow-W01-P02-S07]]'
  - '[[2026-07-23-profile-setup-flow-W01-P02-S08]]'
  - '[[2026-07-23-profile-setup-flow-W01-P02-S09]]'
  - '[[2026-07-23-profile-setup-flow-W01-P03-S10]]'
  - '[[2026-07-23-profile-setup-flow-W01-P03-S11]]'
  - '[[2026-07-23-profile-setup-flow-W01-P03-S12]]'
  - '[[2026-07-23-profile-setup-flow-W02-P04-S13]]'
  - '[[2026-07-23-profile-setup-flow-W02-P04-S14]]'
  - '[[2026-07-23-profile-setup-flow-W02-P04-S15]]'
  - '[[2026-07-23-profile-setup-flow-adr]]'
  - '[[2026-07-23-profile-setup-flow-integration-shape-audit]]'
  - '[[2026-07-23-profile-setup-flow-page-catalogue-mapping-reference]]'
  - '[[2026-07-23-profile-setup-flow-plan]]'
  - '[[2026-07-23-profile-setup-flow-setup-flow-design-hypothesis-research]]'
---

# `profile-setup-flow` feature index

Auto-generated index of all documents tagged with `#profile-setup-flow`.

## Documents

### adr

- `2026-07-23-profile-setup-flow-adr` - `profile-setup-flow` adr: `paged profile setup flow with dynamic copy assembly and cotejo censal` | (**status:** `accepted`)

### audit

- `2026-07-23-profile-setup-flow-integration-shape-audit` - `profile-setup-flow` audit: `taxpayer profile integration shape and ADR grounding audit`

### exec

- `2026-07-23-profile-setup-flow-W01-P01-S01` - Reconcile the dual TaxpayerProfile derivation paths with a side-by-side read of load_active_taxpayer_profile versus taxpayer_profile_from_mapping, consolidating or documenting the layering before any commit-path wiring
- `2026-07-23-profile-setup-flow-W01-P01-S02` - Introduce the setup-incomplete lifecycle marker on the persisted profile record with schema and typed-model plumbing
- `2026-07-23-profile-setup-flow-W01-P01-S03` - Teach the lifecycle authority early-mint registration in setup-incomplete state, duplicate-tax-id refusal firing at mint, and discard-erase of an abandoned incomplete profile
- `2026-07-23-profile-setup-flow-W01-P01-S04` - Refuse modelo work on setup-incomplete profiles in the readiness gate with an instructive refusal naming the resume path
- `2026-07-23-profile-setup-flow-W01-P01-S05` - Surface setup-incomplete status in profile listings and the overview calendar
- `2026-07-23-profile-setup-flow-W01-P01-S06` - Delete CENSO_REFRESHED and reconcile every CENSO_APPLIED consumer per the retired-enum-member discipline
- `2026-07-23-profile-setup-flow-W01-P02-S07` - Build the profile-key to consuming-bindings legal-refs reverse index as a compiled-snapshot projection honoring the registry authority flow
- `2026-07-23-profile-setup-flow-W01-P02-S08` - Extend the Translatable-prefix validator into a reference-only copy gate that rejects literal copy strings at flow construction
- `2026-07-23-profile-setup-flow-W01-P02-S09` - Promote the profile-domain terminology concepts the pages will cite from draft to approved through the Handbook lifecycle
- `2026-07-23-profile-setup-flow-W01-P03-S10` - Pin the post-2025 M036 casilla ids and the official G313 certificate field list against primary sources, recording the addendum in the feature research
- `2026-07-23-profile-setup-flow-W01-P03-S11` - Implement the G313 certificate parser producing typed censal facts stamped with the artefact-origin non-official provenance token
- `2026-07-23-profile-setup-flow-W01-P03-S12` - Add the censal file --file ingestion sub-command routing parsed facts through the manual enrolment path
- `2026-07-23-profile-setup-flow-W02-P04-S13` - Re-sequence SETUP_FLOW sections into the eight-phase spine order with stable question ids, keeping both core registration slots fed and visible_when targets resolving to earlier questions
- `2026-07-23-profile-setup-flow-W02-P04-S14` - Run the locales scaffold and scaffold --check plus parity and honesty gates over the re-sequenced catalogue
- `2026-07-23-profile-setup-flow-W02-P04-S15` - Regenerate the api reference stubs and re-verify documented-command conformance after the re-sequence

### plan

- `2026-07-23-profile-setup-flow-plan` - `profile-setup-flow` plan

### reference

- `2026-07-23-profile-setup-flow-page-catalogue-mapping-reference` - `profile-setup-flow` reference: `page catalogue mapping`

### research

- `2026-07-23-profile-setup-flow-setup-flow-design-hypothesis-research` - `profile-setup-flow` research: `setup flow design hypothesis`

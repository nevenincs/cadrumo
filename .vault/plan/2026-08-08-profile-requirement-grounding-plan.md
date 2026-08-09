---
tags:
  - '#plan'
  - '#profile-requirement-grounding'
date: '2026-08-08'
modified: '2026-08-09'
body_hash: 'sha256:794cfde4c33a291b27ae84f436020cac947f96a04a11e841ad7e7a5b515c0f80'
tier: L2
related:
  - '[[2026-08-08-profile-requirement-grounding-adr]]'
  - '[[2026-08-08-profile-requirement-grounding-reference]]'
---

# `profile-requirement-grounding` plan

## Description

Executes `2026-08-08-profile-requirement-grounding-adr` (accepted). Grounded in `2026-08-08-profile-requirement-grounding-reference`. Enriches the existing `ProfilePreflightRequirement` model with a human label, legal grounding, and the consuming modelo set, all sourced from data already loaded (`ProfileFieldDefinition` and `build_profile_grounding_index`), and threads the enrichment through the three surfaces that already share this model: the blocking readiness gate, `config profile preflight`, and `app modelo readiness`. No new schema or registry authority is introduced. Reconciling the separate `ProfileKey` and `_DEADLINE_RELEVANT_FIELDS` mechanisms against this canonical schema is explicitly out of scope for this plan and is deferred to a follow-up.

## Steps

### Phase `P01` - Enrich the requirement row and grounding union

Extend ProfilePreflightRequirement with label, legal_refs, and modelos; populate them in ProfilePreflightService.report() from the field object already in scope unioned with build_profile_grounding_index; cover with roundtrip and anti-tautology tests.

- [x] `P01.S01` - Add label, legal_refs, and modelos fields to ProfilePreflightRequirement; `src/cadrumo/application/user_profile/_commands.py`.
- [x] `P01.S02` - Populate the new fields in ProfilePreflightService.report() from the in-scope field object unioned with build_profile_grounding_index; `src/cadrumo/application/user_profile/_preflight.py`.
- [x] `P01.S03` - Add roundtrip and anti-tautology tests for the enriched ProfilePreflightRequirement; `src/cadrumo/application/user_profile/tests/`.

### Phase `P02` - Wire the three consumer surfaces

Thread the enriched requirement through the blocking-gate locale template (all four catalogues via dev.locales), ProfilePreflightMissingPayload, and ModeloReadinessMissingRequirementPayload.

- [x] `P02.S04` - Add label, legal_refs, and modelos to ProfilePreflightMissingPayload and its construction site; `src/cadrumo/entrypoints/cli/_config_payloads.py`.
- [x] `P02.S05` - Add label, legal_refs, and modelos to ModeloReadinessMissingRequirementPayload and its construction site; `src/cadrumo/entrypoints/cli/_modelo_payloads.py`.
- [x] `P02.S06` - Update the blocking-gate context and the profile_readiness_missing locale template to render label and legal ref per missing field in all four catalogues via dev.locales; `src/cadrumo/application/modelo/_profile_readiness_gate.py, src/cadrumo/locales/{en,es,ca,hu}.yml`.

### Phase `P03` - Verify

Prove the enrichment with grounded regression tests, keep the JSON-schema-conformance and locale-parity gates green, and regenerate any affected generated CLI reference stubs.

- [x] `P03.S07` - Add a grounded regression proving the blocking-gate message text changes for a known missing field; `src/cadrumo/application/modelo/tests/`.
- [x] `P03.S08` - Run the JSON-schema-conformance and locale-coverage-parity gates and fix any red findings; `src/cadrumo/entrypoints/cli/tests/, src/cadrumo/tests/`.
- [x] `P03.S09` - Run apidocs scaffold --check and land regenerated CLI reference stubs if affected; `docs/api/`.

### Phase `P04` - Close out

Run mandatory code review and a fresh-context honesty review against this campaign's closure summary; action every finding as a fix, a recorded wontfix, or a linked follow-up before declaring the campaign complete.

- [ ] `P04.S10` - Run the mandatory code review against the campaign diff and action every finding; `.vault/audit/`.
- [ ] `P04.S11` - Run the fresh-context honesty review against the closure summary and close every item as fixed or a formally deferred follow-up; `.vault/audit/`.

### Phase `P05` - Execute the 2026-08-09 amendment: stop granting unassessed readiness

Implements the accepted 2026-08-09 amendment. The per-operation model_selectors axis carries zero modelo_ tokens, so the schema-required branch of ProfilePreflightService.report() is unreachable and the report returns ready=True for a profile declaring nothing. Make the unevaluated case distinguishable from a passing one, ground any axis population against official sources rather than inference, and open a detector for the deferred ProfileKey divergence.

- [x] `P05.S12` - Make the unevaluated per-modelo case distinguishable from a passing one on ProfilePreflightReport, so a modelo matching no schema-required field reports not-assessed rather than ready; `src/cadrumo/application/user_profile/_preflight.py, src/cadrumo/application/user_profile/_commands.py`.
- [ ] `P05.S13` - Surface the not-assessed signal as a CLI notice on config profile preflight and app modelo readiness, never as a clean bill of health; `src/cadrumo/entrypoints/cli/_config_payloads.py, src/cadrumo/entrypoints/cli/_modelo_payloads.py`.
- [ ] `P05.S14` - Replace test_preflight_returns_ready_when_no_modelo_selectors_match, which encodes the current defect as the contract, with a regression asserting a profile declaring no facts is never reported ready for a modelo; `src/cadrumo/application/user_profile/tests/test_services.py`.
- [ ] `P05.S15` - Inventory the grounded per-modelo profile-fact requirements from each modelo official form and its registry source=profile bindings, recording the evidence per token and refusing to infer any requirement that no source establishes; `.vault/reference/, src/cadrumo/domain/calculations/registry/_profile_grounding.py`.
- [ ] `P05.S16` - Populate model_selectors with the grounded modelo_ tokens from that inventory and prove the per-modelo branch now contributes, leaving _FILING_BASELINE_PROFILE_PATHS in force until it does; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`.
- [x] `P05.S17` - Add a parity gate failing with the field-level delta when the schema-required set and the PROFILE_KEYS-required set disagree, giving the deferred ProfileKey divergence a detector; `src/cadrumo/application/user_profile/tests/`.

## Parallelization

P01 is a hard prerequisite for P02 (the consumer surfaces cannot carry fields the row does not yet expose) and for P03. Within P01, S01 (model fields) must land before S02 (population logic); S03 (tests) follows S02. Within P02, S04, S05, and S06 touch independent files and may proceed in parallel once P01 is closed. P03 depends on all of P02 closing. P04 depends on P03 closing and reviews the full campaign diff, so it runs last and alone.

## Verification

The plan is complete when every Step is closed (`- [x]`) with a matching execution record, the new roundtrip/anti-tautology tests in P01.S03 and the grounded regression in P03.S01 pass under a real (non-mocked) test run, the JSON-schema-conformance and locale-coverage-parity gates are green, and the P04 code-review and fresh-context honesty review close with zero outstanding unactioned findings.

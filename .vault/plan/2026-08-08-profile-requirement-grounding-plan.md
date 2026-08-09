---
tags:
  - '#plan'
  - '#profile-requirement-grounding'
date: '2026-08-08'
modified: '2026-08-08'
body_hash: 'sha256:0fa88c7cef54d7b02261748ff67d21a2fdccec1721cda60d98d905929f3d7ba9'
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

- [ ] `P01.S01` - Add label, legal_refs, and modelos fields to ProfilePreflightRequirement; `src/cadrumo/application/user_profile/_commands.py`.
- [ ] `P01.S02` - Populate the new fields in ProfilePreflightService.report() from the in-scope field object unioned with build_profile_grounding_index; `src/cadrumo/application/user_profile/_preflight.py`.
- [ ] `P01.S03` - Add roundtrip and anti-tautology tests for the enriched ProfilePreflightRequirement; `src/cadrumo/application/user_profile/tests/`.

### Phase `P02` - Wire the three consumer surfaces

Thread the enriched requirement through the blocking-gate locale template (all four catalogues via dev.locales), ProfilePreflightMissingPayload, and ModeloReadinessMissingRequirementPayload.

- [ ] `P02.S04` - Add label, legal_refs, and modelos to ProfilePreflightMissingPayload and its construction site; `src/cadrumo/entrypoints/cli/_config_payloads.py`.
- [ ] `P02.S05` - Add label, legal_refs, and modelos to ModeloReadinessMissingRequirementPayload and its construction site; `src/cadrumo/entrypoints/cli/_modelo_payloads.py`.
- [ ] `P02.S06` - Update the blocking-gate context and the profile_readiness_missing locale template to render label and legal ref per missing field in all four catalogues via dev.locales; `src/cadrumo/application/modelo/_profile_readiness_gate.py, src/cadrumo/locales/{en,es,ca,hu}.yml`.

### Phase `P03` - Verify

Prove the enrichment with grounded regression tests, keep the JSON-schema-conformance and locale-parity gates green, and regenerate any affected generated CLI reference stubs.

- [ ] `P03.S07` - Add a grounded regression proving the blocking-gate message text changes for a known missing field; `src/cadrumo/application/modelo/tests/`.
- [ ] `P03.S08` - Run the JSON-schema-conformance and locale-coverage-parity gates and fix any red findings; `src/cadrumo/entrypoints/cli/tests/, src/cadrumo/tests/`.
- [ ] `P03.S09` - Run apidocs scaffold --check and land regenerated CLI reference stubs if affected; `docs/api/`.

### Phase `P04` - Close out

Run mandatory code review and a fresh-context honesty review against this campaign's closure summary; action every finding as a fix, a recorded wontfix, or a linked follow-up before declaring the campaign complete.

- [ ] `P04.S10` - Run the mandatory code review against the campaign diff and action every finding; `.vault/audit/`.
- [ ] `P04.S11` - Run the fresh-context honesty review against the closure summary and close every item as fixed or a formally deferred follow-up; `.vault/audit/`.

## Parallelization

P01 is a hard prerequisite for P02 (the consumer surfaces cannot carry fields the row does not yet expose) and for P03. Within P01, S01 (model fields) must land before S02 (population logic); S03 (tests) follows S02. Within P02, S04, S05, and S06 touch independent files and may proceed in parallel once P01 is closed. P03 depends on all of P02 closing. P04 depends on P03 closing and reviews the full campaign diff, so it runs last and alone.

## Verification

The plan is complete when every Step is closed (`- [x]`) with a matching execution record, the new roundtrip/anti-tautology tests in P01.S03 and the grounded regression in P03.S01 pass under a real (non-mocked) test run, the JSON-schema-conformance and locale-coverage-parity gates are green, and the P04 code-review and fresh-context honesty review close with zero outstanding unactioned findings.

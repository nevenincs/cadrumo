---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-08'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:5645640178ad595d28f9b22b82b84480347dd1eec65fab835f30a78b83c8e4b9'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# `profile-requirement-grounding` ledger

## Changes

- `S01` `T` `src/cadrumo/application/user_profile/_commands.py`
- `S02` `T` `src/cadrumo/application/user_profile/_preflight.py`
- `S03` `T` `src/cadrumo/application/user_profile/tests/`
- `S04` `T` `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `S05` `T` `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
- `S06` `T` `src/cadrumo/application/modelo/_profile_readiness_gate.py`
- `S06` `T` `src/cadrumo/locales/{en`
- `S06` `T` `es`
- `S06` `T` `ca`
- `S06` `T` `hu}.yml`
- `S07` `T` `src/cadrumo/application/modelo/tests/`
- `S08` `T` `src/cadrumo/entrypoints/cli/tests/`
- `S08` `T` `src/cadrumo/tests/`
- `S09` `T` `docs/api/`
- `S10` `T` `.vault/audit/`
- `S11` `T` `.vault/audit/`
- `S12` `T` `src/cadrumo/application/user_profile/_commands.py`
- `S12` `T` `src/cadrumo/application/user_profile/_preflight.py`
- `S12` `T` `src/cadrumo/application/user_profile/tests/test_preflight_reports_unassessed_axis.py`
- `S13` `T` `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `S13` `T` `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
- `S14` `T` `src/cadrumo/application/user_profile/tests/test_services.py`
- `S15` `T` `correct the reference document's falsified model_selectors claim in the same action rather than leaving it standing beside the new inventory`
- `S15` `T` `.vault/reference/`
- `S15` `T` `src/cadrumo/domain/calculations/registry/_profile_grounding.py`
- `S16` `T` `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `S17` `T` `src/cadrumo/application/user_profile/tests/test_profile_key_schema_required_parity.py`
- `S18` `T` `fold in removing config profile preflight's duplicate report build on the ready path`
- `S18` `T` `verification gate: a grounded regression asserting the blocking-gate refusal carries legal_refs for a field the grounding index covers, and a benchmark assertion bounding the added per-call cost`
- `S18` `T` `src/cadrumo/application/modelo/_profile_readiness_gate.py`
- `S18` `T` `src/cadrumo/entrypoints/cli/_config/_profile_inspect.py`
- `S19` `T` `verification gate: a parity test proving the merged builder's output is unchanged for every case the two prior functions covered`
- `S19` `T` `src/cadrumo/application/user_profile/_preflight.py`
- `S19` `T` `src/cadrumo/application/modelo/_profile_readiness_gate.py`
- `S22` `T` `src/cadrumo/application/user_profile/_projections.py`
- `S23` `T` `src/cadrumo/application/modelo/_work_create_policy.py`
- `S24` `T` `persist as a dated reference document, no code changes in this step`
- `S24` `T` `src/cadrumo/domain/contribuyente/_keys.py`
- `S24` `T` `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `S24` `T` `.vault/reference/`
- `S25` `T` `record every field where one side carries grounding the other lacks, across the full registry not a sample; persist as a dated reference document, no code changes in this step`
- `S25` `T` `src/cadrumo/_data/registry/aeat/modelos/`
- `S25` `T` `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `S25` `T` `.vault/reference/`
- `S26` `T` `decomposed from S24 and S25 findings, exact files TBD`
- `S27` `T` `src/cadrumo/entrypoints/cli/_config/_status_rendering.py`
- `S27` `T` `src/cadrumo/application/wizard/_status.py`
- `S27` `T` `src/cadrumo/application/diagnostics.py`
- `S28` `T` `src/cadrumo/entrypoints/cli/tests/`
- `S28` `T` `src/cadrumo/tests/`
- `S28` `T` `src/cadrumo/application/user_profile/tests/`
- `S34` `T` `src/cadrumo/application/modelo/_profile_readiness_gate.py`
- `S34` `T` `src/cadrumo/locales/{en,es,ca,hu}.yml`
- `S35` `T` `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `S36` `T` `.vault/audit/`
- `S36` `T` `src/cadrumo/application/user_profile/_preflight.py`
- `S36` `T` `src/cadrumo/application/modelo/_profile_readiness_gate.py`

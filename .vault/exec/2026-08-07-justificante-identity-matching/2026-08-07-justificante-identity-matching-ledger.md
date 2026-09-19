---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:80a40d383543201697ca616bc58825670a97c318ddca5617175be53831038b57'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---

# `justificante-identity-matching` ledger

## Changes

- `S01` `T` `src/cadrumo/application/live/_filed_observation_persistence.py`
- `S02` `T` `src/cadrumo/application/live/_justificante.py (_justificante_matches_capture_axis)`
- `S03` `T` `src/cadrumo/application/live/_justificante.py (register_capture_as_filing_evidence)`
- `S04` `T` `src/cadrumo/domain/justificante/_schema.py`
- `S04` `T` `src/cadrumo/application/live/_justificante.py`
- `S04` `T` `and src/cadrumo/application/live/_filed_observation_persistence.py`
- `S05` `T` `src/cadrumo/domain/justificante/tests/test_filing_target.py`
- `S06` `T` `src/cadrumo/application/live/tests/_filed_capture_history_support.py and a new or existing test in src/cadrumo/application/live/tests`
- `S07` `T` `src/cadrumo/domain/justificante/tests and src/cadrumo/application/live/tests`
- `S08` `T` `src/cadrumo/application/live/_filed_observation_persistence.py (_parse_matching_filed_justificante)`
- `S09` `T` `src/cadrumo/application/live/_filed_observation_persistence.py (persist_filed_justificante_metadata and enroll_filed_justificante_evidence)`
- `S10` `T` `src/cadrumo/application/live/tests and src/cadrumo/entrypoints/cli/tests`
- `S11` `T` `src/cadrumo/adapters/outbound/aeat/sede/__init__.py`
- `S12` `T` `src/cadrumo/application/live/tests`
- `S13` `T` `src/cadrumo/adapters/outbound/aeat/sede/_declarations.py (_row_locator_for_expediente)`
- `S14` `T` `src/cadrumo/application/live/tests/test_filed_history_onboarding.py`

---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:e25537c695068b9782f7df16879af730d88bea420dc7ba3501a212de931a8fd7'
step_id: 'S24'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Field-by-field parity audit between ProfileKey (domain/contribuyente/_keys.py, wizard-sourced) and ProfileFieldDefinition (schema.toml-sourced): every field present in one but not the other, every requirement-flag disagreement, every legal_refs/description mismatch

## Scope

- `persist as a dated reference document, no code changes in this step`
- `src/cadrumo/domain/contribuyente/_keys.py`
- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `.vault/reference/`

## Description

- Ran `PROFILE_KEYS` (real, registered wizard catalogue via `ensure_profile_keys_registered()`) against `load_user_profile_schema()` (real, loaded schema) in-process, computing set differences and requirement-flag agreement per path.
- Measured: `PROFILE_KEYS` 75 keys (1 required), schema 161 fields (15 required) - reproducing and refining the governing audit's prose measurement with the exact field-level breakdown.
- Found ZERO keys present in `PROFILE_KEYS` but absent from schema (the wizard catalogue's key coverage is a strict subset of the schema).
- Found exactly two requirement-flag disagreements where both sides declare the field: `activities.description` and `iva.regime`, both schema-required but wizard-optional - the concrete mechanism behind the audit's "opposite verdicts on the same record" finding.
- Found twelve schema-required fields with NO `PROFILE_KEYS` entry at all (not mismatched - structurally invisible to the wizard flow): `attribution_entity_socios.*` (5), `attribution_received.*` (5), `usage_ratios.*` (2) - all repeatable-row constructs for atribución de rentas / afectación parcial regimes the main wizard flow does not walk.
- Enumerated and grouped by section the remaining 74 optional-only schema fields absent from `PROFILE_KEYS`, per this project's no-silent-under-declaration discipline (a count without the underlying list would itself be a silent truncation).
- Confirmed `legal_refs` is a structural asymmetry, not a per-field mismatch to enumerate: `ProfileKey` has no `legal_refs` field at all (`_keys.py:43-52`), so any surface still reading `PROFILE_KEYS` for grounding carries zero legal_refs by construction. Noted `description` is likewise not directly comparable (a locale KEY on one side, literal prose on the other) and scoped a semantic prose diff out of this no-code-changes step.

## Outcome

`.vault/reference/2026-08-09-profile-requirement-grounding-profilekey-schema-field-parity-reference.md` persisted with the complete measured comparison. No code changed. Feeds P08.S26's decomposition: the two requirement-flag disagreements are flagged as the highest-value fan-out candidate, the twelve wizard-invisible required fields as a distinct product-decision candidate, and the 74 optional-only fields as NOT a to-do list absent a confirmed downstream consumer expecting `PROFILE_KEYS` completeness.

## Verification

No test-affecting change; verification is the grounded computation itself, reproduced live:

```
uv run --no-sync python -c "from cadrumo.application.wizard import ensure_profile_keys_registered; ensure_profile_keys_registered(); from cadrumo.domain.contribuyente import PROFILE_KEYS; from cadrumo.domain.user_profile import load_user_profile_schema; schema = load_user_profile_schema(); print(len(PROFILE_KEYS), sum(1 for pk in PROFILE_KEYS if pk.requirement.value=='required'))"
75 1
```

`vaultspec-core vault check --fix` run after creation to strip leftover scaffold comment blocks the `create` tool's content-injection left behind (the same known pitfall recorded in prior Steps of this campaign) - confirmed clean on re-check.

## Notes

None. Straightforward measurement step; no incidents.

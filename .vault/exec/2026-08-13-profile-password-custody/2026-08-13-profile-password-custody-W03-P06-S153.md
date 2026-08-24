---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e5e518d509a7a9a181e51c5b2902c180040e7bef6633fa34bb72ff8326f99933'
step_id: 'S153'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule whether a legal entity may be registered with no legal form, since the retired creation path enforced that requirement while no surviving surface enforces it and the registry schema declares the field not required, and the field's own description says it drives the corporate tax rate schedule under the cited article so an entity can now be established with no selector for its rate schedule

## Scope

- `src/cadrumo/_data/registry/ and src/cadrumo/application/user_profile/`

## Description

Rule legal form conditionally required for legal entities, enforce that condition through profile completeness, and preserve registration's incomplete-profile behavior.

## Outcome

Ruled: registry `required=true` on the legal-form field is wrong — the requirement is conditional on `entity_type == legal_entity`. Enforcement now lives in `conditional_profile_required_paths` (`application/user_profile/_completeness.py`): a profile declaring the legal-entity type owes `taxpayer_type.legal_entity_form`, propagating to fact-write keys, conditional issues and the filing baseline (whose explicit legal-form branch stays for the legal-name companion). Registration remains permissive by design — a profile is born INCOMPLETE.

## Notes

The contemporaneous execution record reported no additional incident beyond the ruling and implementation evidence retained above.

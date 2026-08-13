---
tags:
  - '#exec'
  - '#iva-art-69-dos-services'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:9bc98cbbf4f78f47b575b328c02c912e35a457d7256bd3d21726fe970434bdbb'
step_id: 'S03'
related:
  - "[[2026-08-12-iva-art-69-dos-services-plan]]"
---

# Follow the split through the rate-tier demand so the excepted branch is not asked for a tier it never uses, and add the registry grounding row for the new rule in the SAME change - the decision table and the place-of-supply table are held in parity in both directions, so a rule without its row cannot be committed separately

## Scope

- `src/cadrumo/domain/iva/_classification.py`
- `src/cadrumo/_data/registry/aeat/iva/place_of_supply/2025.toml`

## Description

- Made the rate-tier demand consult the same exception predicate, so the
  excepted branch is not asked for a tier it never uses.
- Added the registry grounding row for the new rule in the same change, and
  corrected the sibling row's notes now that the two split the population
  between them.

## Outcome

Done. The place-of-supply parity gate passes, which is what proves the registry
row landed: it holds the decision table and the grounding table equal in both
directions, so a rule without a row and a row without a rule both fail.

## Notes

The step said the registry row could not be committed separately, and the gate
is why that is a fact rather than a preference. It is also why the row's notes
are worth writing carefully: they are the only place the exception's own limit
is stated in the registry, and a reader who reaches the table without the code
will take them as the grounding.

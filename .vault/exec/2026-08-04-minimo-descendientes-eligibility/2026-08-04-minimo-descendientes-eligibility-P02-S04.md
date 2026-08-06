---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:19974f6384f6e66fea0fa3f25580b72e2038775b292e984314f35215ba9065b9'
step_id: 'S04'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Add the annual-rentas-excluding-exempt and own-return-filed facts to the descendiente axis in the profile schema and the descendant model

## Scope

- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `src/cadrumo/domain/contribuyente/family.py`

## Description

## Outcome

The two per-descendant factual inputs ship on the descendiente axis: the annual rentas
excluding exempt income, and whether the descendant files their own return. A third field
carrying an explicit proration answer landed alongside them for the sibling Steps.

All three are ordinary declared fields on the existing descendiente object, reached through
model selectors. The derived-selector namespace the sibling campaign added to the same file
is confirmed untouched, so the two campaigns coexist in one schema without interference.

The executor also edited the descendant fact projection, which the Step's file list did not
name. That was necessary rather than optional: without it the new facts never reach the
predicate and the phase gate cannot pass end to end. The scope extension was disclosed
rather than absorbed silently, which is the correct handling.

Two CLI files were touched for the same reason, and the reason is worth recording because it
is a good sign rather than a bad one. A payload-parity gate requires every descendant field
to appear on the wire, and it caught the new fields being dropped from the JSON projection.
The executor counted that as its own failure in the broad sweep rather than attributing it
elsewhere. The interactive flow, the prompts and the renderer were deliberately left alone
for the entry-surface Step that owns them.

## Notes

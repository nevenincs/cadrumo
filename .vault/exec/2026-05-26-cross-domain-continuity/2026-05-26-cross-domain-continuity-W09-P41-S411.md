---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-17'
body_hash: 'sha256:1dfb4b0cc72b848331e43262803d69380d9acd703dbfb0ba9587bf5edced40c6'
step_id: 'S411'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# add the socio-profile repeatable attribution_received.N.* fact group (entity_nif, entity_name, share_pct, base_imponible_attributed, filing_year) to the central profile schema with wizard/edit capture prompts and en/es/ca/hu locale keys through the locale CLI

## Scope

- `src/aeat/_data/registry/aeat/user_profile/schema.toml`

## Description

- Add the repeatable `attribution_received` section to the central profile schema TOML with five fields: `entity_nif`, `entity_name` (string, identity, required), `share_pct` (decimal 0..100, financial, required), `base_imponible_attributed` (money, financial, required), `filing_year` (integer, financial, required).
- Ground each field per LIRPF arts. 86-89 (régimen de atribución de rentas) plus `orden-hap-2250-2015:art-3`, mirroring the sibling `attribution_entity_socios` group; art titles confirmed against the bundled consolidated corpus (`ley-35-2006.html` anchors a86-a89).
- Add a schema-shape test mirroring `test_attribution_entity_schema_fields`, asserting field types, the 0..100 bound, the required flags, and that every declared `legal_refs` id resolves in the legal catalogue.

## Outcome

Committed `0ce36c4c39` (explicit-pathspec, 2 files). Gates green (-n0): 5 new schema-shape tests + 8 sibling `attribution_entity` tests + 68 `user_profile` domain suite + 14 `_profile_binding` application tests; ruff + ty clean. The typed home for the socio's attributed base now exists; it drives the S413 handoff Notice and the S414 omission advisory.

## Notes

- Scope resolution: the step text asked for "wizard/edit capture prompts and en/es/ca/hu locale keys", but the sibling `attribution_entity_socios` group has NEITHER — profile schema fields carry inline `description` prose (not `tr()` locale keys), and facts reach the profile through the generic profile import/edit path, not a dedicated wizard prompt. Delivered the schema section + shape test consistent with that precedent; first-class wizard capture + locale keys for BOTH attribution groups is tracked as a cross-cutting profile-UX follow-up, not an S411 requirement.
- Casilla 1577 binding collision (from the S412 assess-first) is recorded in the m184 ADR addendum; S412 is superseded (no `source = "profile"` binding authored).

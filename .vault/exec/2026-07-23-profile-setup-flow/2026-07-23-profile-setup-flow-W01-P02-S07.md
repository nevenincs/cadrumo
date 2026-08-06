---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
body_hash: 'sha256:d069132d2bf56a34478bc0c32b4ac071c95bce48ffb943628c14fff2ccdfeeb3'
step_id: 'S07'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Build the profile-key to consuming-bindings legal-refs reverse index as a compiled-snapshot projection honoring the registry authority flow

## Scope

- `src/cadrumo/domain/calculations/registry/`

## Description

- Add `_profile_grounding.py` to the registry package: the
  `ProfileKeyGrounding` frozen model and
  `build_profile_grounding_index(authority)`, inverting every
  `source = "profile"` binding across all modelos and revisions into a
  per-profile-key union of consuming modelos (typed `Modelo` members),
  `legal_refs`, and `source_refs`.
- Count only value-consuming selector members (`profile_key`,
  `profile_keys`); a `required_when_profile_key` gate is deliberately
  excluded so grounding never over-claims a gated key's legal basis.
- Export both symbols through the registry package facade.
- Pin with four wiring tests against the bundled validated registry:
  `censo.status` inverts to M036 under RD 1065/2007 / Orden
  EHA/1274/2007; entries are sorted unions; unconsumed keys are absent
  (never empty-invented); consumption spans multiple modelos.

## Outcome

Committed as `9929ea5dc1` (explicit pathspec). Grounding tests 4/4;
smoke run over the bundled authority indexes 52 profile keys. The
docstring core-struct-links gate passes for the new module.

## Notes

Two pre-existing docstring-gate offenders remain in
`application/calculations/_per_grupo_member_keys` - peer-owned, not
touched by this Step (owner triage per the full-tree-gate discipline).
The schema.toml per-field `legal_refs` are the complementary grounding
source; the flow-layer copy assembler merges both when it renders the
legal zone (a W03 Step).

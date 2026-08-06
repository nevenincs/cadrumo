---
tags:
  - '#exec'
  - '#declaracion-profile-printed-box-scope'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:4b52955c393fe11cb7850c8a35f4c39fcdbfbb30f6bba21f63374b5ab4a9621c'
step_id: 'S08'
related:
  - "[[2026-07-25-declaracion-profile-printed-box-scope-plan]]"
---

# Confirm the 24 Python modules carrying the six ids stay unaffected, 16 tests and 7 registry and 1 fixture with zero production application modules, since the engine reaches these ids through registry TOML rather than through Python

## Scope

- `src/cadrumo/`
- `dev/`

## Description

- Run the id-carrying Python modules and confirm they pass unchanged.
- Confirm the engine reaches these ids through registry TOML rather than through Python.

## Outcome

Confirmed. The id-carrying modules run green with no edit: 140 passed across the application, domain-registry and CLI test modules that reference the six ids, using an explicit marker selection so the run genuinely collected rather than silently selecting nothing.

The characterisation holds and is sharper than stated: there are zero production application modules in the footprint. Every Python reference is a test, a registry test-support module or a fixture generator. The engine reaches these ids through registry TOML, which is why an extraction-scope change leaves the calculate path untouched.

The declaración suite itself passes 180, and the manual-annex provenance gate passes 29 after the sidecar prose repair.

## Notes

The recorded figure of 24 modules re-measures to 22 at HEAD; the two absent are those whose only reference was through the generator helpers deleted in S03, so the reduction is this change's own effect rather than tree drift.

A bare path invocation would have selected nothing here, because the repository default restricts to the unit marker. The runs were widened explicitly and the collected counts confirmed non-zero.

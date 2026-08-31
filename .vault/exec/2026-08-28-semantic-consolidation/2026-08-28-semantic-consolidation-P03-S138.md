---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:91d164657a1a9bbfda60d528357508bea8cb08f0adef53a3bbfc98d601450efa'
step_id: 'S138'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Promote the retention-floor erase decision to one domain function both destructive surfaces reach, as the CLI verb's own docstring asked

## Scope

- `src/cadrumo/domain/retention/`
- `src/cadrumo/application/config_reset.py`
- `src/cadrumo/entrypoints/cli/_config/_profile_delete.py`

## Changes

- `M` `src/cadrumo/domain/retention/_floor.py`
- `M` `src/cadrumo/domain/retention/__init__.py`
- `M` `src/cadrumo/application/config_reset.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_profile_delete.py`
- `verify:` truth-tabled the replacement over all four (blocks_erase, override_approved) pairs -> identical
- `verify:` `pytest src/cadrumo/domain/retention + 5 reset suites -n 0 -m ""` -> pass (51)

## Notes

A confessed duplication. The CLI verb docstring said the DECISION was written
twice -- the all-profile reset testing the blocking flag together with a recorded
override, this verb testing the flag alone -- that a third condition added to the
retention contract would reach one site and not the other, and that fixing it
meant promoting the decision to a shared application function. This does that.

The shared function takes the two FACTS rather than an assessment, because the
callers hold different types: the reset works from a resolved
ConfigResetRetentionDecision, the delete from a RetentionFloorAssessment off the
maintenance authority. Taking facts serves both without forcing either into the
other model. override_approved defaults to false so a surface offering no
override does not have to say so -- the delete verb passes nothing, which is the
accurate statement rather than a value withheld.

This is a destructive path, so the equivalence was checked by enumeration rather
than by De Morgan on paper: all four input pairs, before and after, identical.

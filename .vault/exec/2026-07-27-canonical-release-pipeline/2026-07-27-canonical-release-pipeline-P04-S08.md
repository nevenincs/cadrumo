---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S08'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

# Declare the superseded-names axis in the generated cohort marketplace manifest, seeded with the retired aeat plugin identity, gate: uv run --no-sync pytest dev/packaging/tests -q -k marketplace passes with the generator test asserting the declaration is emitted in every generated manifest

## Scope

- `dev/packaging/release_cohort.py`
- `dev/packaging/cohort_manifest.py`
- `dev/packaging/tests/`

## Description

- Add a superseded-names declaration to the cohort marketplace manifest.
- Seed the shipped cohort manifest with the retired product identity.
- Pin the shipped declaration with a test.

## Outcome

Landed under the commit subject `feat(packaging): retire a superseded plugin
identity by declaration, not delete authority`.

Supersession is declared by the cohort rather than held as a delete list in the
publishing tool, for two reasons. A standing delete authority decoupled from any
release is the shape of the incident that made the ownership rule necessary in
the first place. And a declaration ships in every later cohort, so retirement
becomes an enforced invariant rather than a one-time act.

A malformed declaration refuses rather than reading as retire-nothing, because
an unreadable declaration that parses to an empty set cannot be told apart from
a cohort that retires nothing at all.

Gate: the marketplace suite passes, including a test that the shipped cohort
manifest actually carries the declaration. A mechanism whose declaration does
not ship protects nothing.

## Notes

The retired identity is claimable by anyone today: its published entry records
no publisher, because it predates ownership tracking.

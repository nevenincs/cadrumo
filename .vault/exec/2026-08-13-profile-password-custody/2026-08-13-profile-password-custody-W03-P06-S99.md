---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:c555e949ff1adea99f89af94eec2ee7e7adc329d60343c36e790e467b423f704'
step_id: 'S99'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh converge the twenty-seven per-module profile-creation helpers onto the canonical registration helpers that one hundred and five other modules already use, treating any helper that genuinely cannot convert as a finding to state rather than a conversion to force, and searching by meaning first because a name-stem sweep structurally cannot find the duplicate that carries a different name

## Scope

- `src/cadrumo/entrypoints/cli/tests/ and src/cadrumo/tests/`

## Description

- Search by meaning rather than by name stem for duplicated seeding helpers.
- Measure how many genuinely bypass the canonical registration door.
- Delete the duplicate found; state the rest as a finding rather than force a
  conversion.

## Outcome

**The Step's premise is largely already satisfied, and the measurement says
so: of the thirty-one per-module seeding helpers present, twenty-nine already
delegate to the canonical registration door.**

They are not duplication. Each is a thin wrapper carrying the fact set its own
test needs — a natural person here, a legal entity with a turnover figure
there, different jurisdictions — over one shared implementation. Converging
them would relocate that per-test data without removing any logic, which is
the conversion the Step explicitly says to state as a finding rather than
force.

Two genuinely bypassed the canonical door. One of those was a real duplicate
and only a search by MEANING could have found it: a helper claiming to create a
profile and import a statement, beside a sibling that imports one transaction —
same file header, same import verb, same identifier extraction, and no shared
name stem at all. The claiming name was also false; it never created a profile.
Its body is deleted, its call sites route to the canonical helper, and what
remains local is the scenario data under an honest name.

The second is the command-line surface that drives the retired creation verb,
which belongs to the separate row on that verb rather than to this one.

## Notes

The name-stem sweep the Step warns about would have found neither: the
duplicate pair shared no common identifier, which is precisely how they drifted
apart. The count in the row's text (twenty-seven) is also stale; the population
is thirty-one and has grown while the campaign ran.

---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S01'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Declare the auth section in the user-profile schema with provider, dni_nie and numero_soporte at identity sensitivity, and pin its shape with a schema test

## Scope

- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`

## Description

- Adopt the auth section already declared in the profile schema rather than re-declaring it; it carries `provider`, `dni_nie` and `numero_soporte` at identity sensitivity and landed in an earlier commit on this feature.
- Add the shape test beside the other profile schema tests, following their fixture and assertion style.
- Pin identity sensitivity on the section and on every field, since these are credential inputs and the classification is what routes them into ciphertext at rest.
- Pin the field set to exactly the provider choice plus the two Cl@ve credential halves, and both credential fields as string.
- Pin the provider enum against the core provider-kind catalogue rather than a hand-listed copy, so a provider added in code without a schema value fails here instead of becoming silently unselectable.
- Pin that no field is unconditionally required, because requirement is conditional on the mode and a blanket requirement would refuse every certificate profile at write time.
- Pin that the section is not effective-dated, since a credential is current state rather than a dated fiscal fact.

## Outcome

Five tests in `src/cadrumo/domain/user_profile/tests/test_auth_schema_fields.py`, all passing.

`uv run --no-sync pytest src/cadrumo/domain/user_profile/tests/ -q --no-header -p no:randomly -n0` reported `90 passed in 30.29s`, and the same file re-ran green at the committed HEAD inside `43 passed in 153.00s`.

`uv run --no-sync ruff check` and `uv run --no-sync ty check` both reported `All checks passed!` for the file.

## Notes

The schema declares only `numero_soporte` as the second Cl@ve credential, but the AEAT non-QR Cl@ve Movil form asks a NIE holder for the numero de soporte and a DNI holder for the document validity date. A DNI holder therefore has no profile field for their half and must still supply it through the environment. The decision record states a Cl@ve provider needs both declared fields, which holds only for a NIE holder. The gap is reported to the coordinator rather than closed here, because adding a field is a schema decision outside this Step.

The provider-enum assertion couples the schema to the core catalogue deliberately. If a provider kind is ever added that a profile must not be able to select, that assertion is where the exception has to be made explicit.

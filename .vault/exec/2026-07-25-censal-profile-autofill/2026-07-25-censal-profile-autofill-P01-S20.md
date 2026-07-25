---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S20'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Retire the dead censo-derived provenance token and make its gate enumerate the published set rather than naming one member

## Scope

- `src/cadrumo/application/user_profile`

## Description

- Confirm the target files were free before editing, since another campaign had been landing in the module that declared the token.
- Delete the token's re-exports from the package facade, which the declaring module's owner had already retired at source.
- Drop the token from the overview's verified-source set, where it was unreachable because no fact could carry it.
- Re-point the test helper that stamped it at the verified censo token those cases actually mean.
- Derive the gate's token set from the package's own exports rather than naming a member.
- Add a discovery check, so renaming the export convention fails loudly instead of quietly emptying the gate.
- Prove the gate by publishing an undeclared token locally and watching it fail with the offending name, then restoring.
- Sequence the deletion ahead of the enumeration, so no revision in between is red.

## Outcome

Three tests in `src/cadrumo/application/user_profile/tests/test_application_provenance_tokens_declared.py`, and five files cleared of the retired token.

`uv run --no-sync pytest` over the profile application tests and the overview calendar verb reported `232 passed in 54.16s`. An earlier run adding the profile domain reported `327 passed in 45.54s`.

With an undeclared token published locally, the gate failed naming it; the injection was then removed and the file confirmed free of it.

`uv run --no-sync ruff check` and `uv run --no-sync ty check` reported `All checks passed!`, and the import gate names the new test file zero times.

## Notes

The gap was in a gate written earlier in this campaign, which is the part worth recording. It named one provenance token and asserted that one was declared, so a sibling published beside it passed unremarked. An instrument that measures a named instance rather than the property it claims to check will always miss the second instance, and the second instance is the one nobody is looking at.

Deriving the set from the package exports introduces its own failure mode, which is why the discovery check exists. A gate that asserts an empty violation list proves nothing if the discovery silently matches nothing, so the convention it depends on is asserted separately rather than assumed.

The first attempt at that discovery reached the package through its parent, which the type checker flagged as a submodule that might not have been imported. Retargeting at the package module directly removed the diagnostic; the alternative of importing the parent and hoping the submodule was already loaded would have been a latent ordering dependency.

Sequencing mattered again and inverted from the earlier provenance work. There, the declared set had to widen before enforcement could land without reddening a live path. Here the token is dead, so deletion comes first and the enumeration finds nothing to complain about, which means no revision between the two is red.

Six type-checker diagnostics in the same package belong to another campaign's bundle-export and custody tests. They are clean at the committed revision and were not touched.

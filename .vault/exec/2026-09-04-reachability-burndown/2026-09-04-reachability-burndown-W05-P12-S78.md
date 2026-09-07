---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:eb4caf3947aa7fb47415cec7221366665de00045a05c6b5313eaeb5ded33f8b8'
step_id: 'S78'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove the module-level lazy attribute hook from the profile-key registry and the alias beside it: the hook resolved a PROFILE_KEYS attribute declared only under TYPE_CHECKING, no shipped module imported it, and its four test importers were racing the wizard registration the hook fires against, which the registry's own docstring already warned about; all four now call the call-time function production already used. The alias was a pure module-level restatement of the canonical classmethod. Keep the required half of the symmetric filtered view, whose optional half is live.

## Scope

- `src/cadrumo/domain/contribuyente/keys.py`
- `src/cadrumo/domain/contribuyente/__init__.py`
- `src/cadrumo/application/user_profile/keys_validation.py`
- `src/cadrumo/application/wizard/compiler.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/domain/contribuyente/keys.py`
- `M` `src/cadrumo/domain/contribuyente/__init__.py`
- `M` `src/cadrumo/application/user_profile/keys_validation.py`
- `M` `src/cadrumo/application/wizard/compiler.py`
- `M` four test modules under `contribuyente`, `user_profile`, `wizard`, `registry`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `python -m dev.audit.unreachable_code` unused 1044 -> 1040,
  exact 413 -> 411; neither removed symbol reported
- `verify:` `python -m dev.quality.unreachable_module_ratchet` and
  `... docstring_reference_ratchet` both exit 0
- `verify:` `pytest` on the four repointed modules, 70 passed
- `verify:` `ruff check` and `ty check` clean

## Notes

The hook was not merely unused, it was hurting the only callers it had. `from
... import PROFILE_KEYS` fires a module `__getattr__` at the IMPORTER's import
time, which is precisely the race `profile_keys()` was written to avoid and
which that function's own docstring describes. Two of the four importers bound
it at module level. They now call the function production already used.

Deleting an attribute that exists only through a hook has a long tail the
compiler cannot see. `__all__` advertised it, a `TYPE_CHECKING` block declared
it, the package docstring called the lazy resolution a deliberate ordering
contract, and five `:data:` references across three modules named it. The
ordering contract is real -- reading before registration raises -- but it lives
in the registration check, not in the lazy attribute. The docstring-reference
ratchet caught the dangling prose; nothing else would have.

`required_profile_keys` is reached only by tests and is deliberately kept. It is
the REQUIRED half of a symmetric pair whose OPTIONAL half is consumed in
production. Deleting one side leaves a registry that can report its optional
keys and not its required ones, which is a worse surface than an unused
function.

Renaming `PROFILE_KEYS` to `profile_keys()` collided with local variables of
that name in two of the four test modules, silently producing
`TypeError: 'set' object is not callable`. Imported under
`registered_profile_keys` there. A rename that turns a CONSTANT into a call has
to check for locals holding the lowercase form.

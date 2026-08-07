---
tags:
  - '#exec'
  - '#m200-export-nif-misbinding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:21d60fa11758ef57a6aec416f3236fc2e99f6268fe68377dee312fba8cbf6f03'
step_id: 'S05'
related:
  - "[[2026-08-07-m200-export-nif-misbinding-plan]]"
---

# Add a fixture-anchor test mutating a scratch export field's profile_tax_id length away from 9 and asserting RegistryValidationError, then restore

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_export.py`

## Description

- Add a fixture-anchor test widening a committed, correct declarant-NIF declaration and asserting the real validator refuses it.
- Add the accept control at the identifier width, so a validator refusing every such field cannot read as a working gate.
- Pin the width constant against the identifier validator's own behaviour.
- Assert the width ruling stays total over every declarable draft attribute.
- Add a real-site regression restoring the Modelo 200 misbinding in memory against the real loaded registry.

## Outcome

Five tests landed in
`src/cadrumo/domain/calculations/registry/tests/test_registry_schema_part1.py`,
which is where the sibling literal-length refusal test lives and where the helpers
that drive the real registry validator over a real committed revision already
exist. The Step row scopes the registry package's export-helper test module, but
that module tests the pure helpers inside the resolution module and has no access
to the validator harness; using it would have required duplicating that harness.

The anchor locates its subject by PROPERTY, draft kind plus the attribute, rather
than by a pinned field id, so renaming or renumbering the committed declaration
cannot make it pass vacuously. It also asserts the declaration starts at the
identifier width before widening it, so the mutation is known to be a change.

The real-site regression is the one that matters most. The other refusal tests
widen a declaration the test itself shaped, and a detector can be correct on
shaped input while still missing the site that motivated it. This one restores the
defect exactly as it shipped, the committed Modelo 200 field at its AEAT-correct
15-byte width re-bound to the declarant's NIF, and drives the real validator over
the real loaded revision. It refuses by name. It also stands as the permanent
regression against the misbinding being re-authored.

The constant pin closes the last vacuity route. The width assertions mean nothing
if the constant stops describing the identifier contract, so one test drives the
identifier validator directly: a canonical identifier of that width validates, and
one character more or fewer is refused. It compares against the validator's
behaviour, never against a second copy of the number.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_registry_schema_part1.py -n0 -p no:randomly -k "draft_attribute_width or declarant_nif or grupo_mercantil_parent_tin or spanish_tax_id_width or literal_export_field"
    5 passed, 45 deselected in 7.52s

Proven load-bearing by abstaining from the declarant-identifier width ruling from
a pytest plugin loaded from outside the repository, so nothing under the source
tree changed and a crashed run left no residue. Serialised explicitly:

    PYTHONPATH=<scratch> uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_registry_schema_part1.py -n0 -p no:randomly -p mutate_width_ruling -k "draft_attribute_width or declarant_nif or grupo_mercantil_parent_tin or spanish_tax_id_width"
    [mutation] profile_tax_id width ruling 9 -> None (width gate disabled)
    3 failed, 2 passed, 45 deselected in 9.87s

The three reds are the totality assertion, the widened-slot refusal, and the
real-site refusal. The two that stayed green are the ones that must not depend on
the ruling: the accept control and the identifier-contract pin. So the mutation
discriminates rather than merely reddening the file. Restored and re-confirmed
green at 5 passed.

## Notes

The mutation sets the ruling to an explicit abstention rather than deleting the
key. Deleting it would also raise, via the totality check, and the refusal tests
would still pass on a different message, which would have looked like a
successful proof while isolating nothing.

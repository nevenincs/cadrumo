---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S21'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P05.S21`

Added an anti-tautology proof for the `(segmento, number)` casilla
identity gate: a real registry fragment is mutated on disk to collide two
casilla identities, reloaded through the real loader, and the uniqueness
gate is asserted to hard-fail.

- Modified: `src/aeat/domain/calculations/registry/test_tautology_gate.py`

## Description

Two paired tests prove the `(segmento, number)` uniqueness gate is
load-bearing — it accepts a sound registry and rejects a deliberately
broken one:

`test_committed_modelo_200_clears_the_segmento_number_identity_gate`
loads the committed Modelo 200 and asserts `RegistryValidator` raises
nothing. Modelo 200 declares casilla `00562` twice — the ECPN-segment
occurrence with `segmento` unset and the Liquidación-segment occurrence
under `segmento = "DP200014"` — so the committed tree exercises the
multi-segment identity model and must validate clean.

`test_dropping_segmento_to_collide_casilla_identity_hard_fails_the_gate`
copies the Modelo 200 fragment tree to a `tmp_path` directory, deletes
the `segmento = "DP200014"` line from the Liquidación `00562` casilla
fragment, reloads the mutated tree through the real `load_modelo_directory`
loader, and runs the real `RegistryValidator`. Dropping `segmento`
collapses the Liquidación occurrence's identity from `("DP200014",
"00562")` to `(None, "00562")`, colliding with the unset-segmento ECPN
occurrence. Both casillas keep distinct `id` values, so the
duplicate-`id` check cannot fire — only the generalised `(segmento,
number)` uniqueness gate can catch the collision, which is exactly what
makes this a non-tautological proof of that gate specifically. The test
asserts `RegistryValidationError` matching `duplicate casilla number
'00562'`.

The new tests mutate on-disk fragments and reload; they construct no
schema-authority objects, so `test_tautology_gate.py` stays clear of the
`test_schema_hygiene.py` schema-authority-constructor gate and needs no
`_VALIDATOR_TEST_ALLOWLIST` entry. The `shutil` import and the
`RegistryValidationError` / `RegistryValidator` / `load_registry_tree`
re-exports were added to the module import block.

## Tests

`pytest test_tautology_gate.py test_schema_hygiene.py` — 15 tests pass,
including both new identity-gate proofs; `ruff check` on the touched file
is clean. No mocks, skips, xfail markers, or tautological assertions: the
proof reloads a real registry through the real validator.

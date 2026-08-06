---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:23baaab89180e51eb945d4b18c7a2c2869762ebfac3b634cd61fcdc9143ed83e'
step_id: 'S283'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Give every set-asserting gate an anti-vacuity floor, asserting the subject count is non-zero before asserting the property, across the write-guard parity, namespace-adoption and tree-walk gates

## Scope

- `src/cadrumo/`

## Description

- Add an anti-vacuity floor and a discrimination probe to the write-guard parity gate `test_every_write_policy_verb_is_in_a_mutating_family` in `test_write_policy_mutability_parity.py`: assert the catalogue holds at least 40 entries, and inject a genuinely read-only command (`registry.inspect`) into the same read-only screen and assert it is flagged, proving the screen is not vacuously empty because nothing can classify read-only.
- Floor the namespace-adoption gate in `test_namespace_registry_adoption.py` (executed in full under `S278`): non-zero scanned-literal floor, hostile-input probe, and prefix-coherence probe.
- Verify the tree-walk gate already carries its floor: `test_every_guarded_write_path_names_a_live_command` in `test_root_fallback_write_guard.py` materialises the lazy tree and asserts `len(leaves) > 100`, with anti-tautology `test_live_command_check_rejects_a_stale_catalogue_entry` proving a pre-collapse invoice spelling is rejected; the operator-surface drift gate `test_operator_surface_contract_covers_the_live_tree` likewise floors family and sub-verb totals. No edit needed to either; both landed earlier in the campaign.

## Outcome

Verified at HEAD `1437055950f5b8f4082d323578294fc32ad1d9fe`.

Write-guard parity gate: `uv run --no-sync pytest -p no:randomly -m "unit or integration" -n0 -q --no-header src/cadrumo/entrypoints/mcp/tests/test_write_policy_mutability_parity.py` — `3 passed in 5.96s`.

Tree-walk gate (already floored, re-verified): `uv run --no-sync pytest -p no:randomly -m "unit or integration" -n0 -q --no-header src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py` — `11 passed in 95.28s (0:01:35)`.

Namespace-adoption gate floor: see the `S278` record — `3 passed in 19.79s`.

Mutation-check per added assertion (throwaway rebind probe; real passes, defect fails):

- write-guard floor `len(WRITE_PATHS) >= 40`: real_passes=True, collapsed-catalogue defect_fails=True.
- write-guard discrimination `injected == ["registry.inspect"]`: real_passes=True, always-False read-only screen defect_fails=True.

Both write-guard mutation probes reported OK. `ruff check` and `ruff format --check` clean on the touched file.

## Notes

The tree-walk gate portion required no code change: the write-guard catalogue gate and the operator-surface drift gate already carried leaf-count / family-count floors and anti-tautology proofs from earlier campaign steps, so the three named gate families (write-guard parity, namespace-adoption, tree-walk) all now carry floors. Only the write-guard parity gate and the namespace gate lacked one.

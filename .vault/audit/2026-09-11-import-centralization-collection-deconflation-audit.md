---
tags:
  - '#audit'
  - '#import-centralization'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:eeac8149003e733da1507606c5356f4bb6ae4b166cd2ffc4dbe1bd367ebf5f31'
related: []
---
# `import-centralization` audit: `collection deconflation`

## Scope

Reviewed the collection-deconflation working-tree changes against the accepted canonical-defining-module ADR and its reopened plan. The review covered the exact successful `pytest --collect-only` run, package initializer inertness, canonical ownership, the governed `src` boundary, shared registry test support, deleted registry tests, and unrelated-change risk in the dirty concurrent worktree.

## Findings

### src-root-leaks | high | governed source tests still import repository-only development support

The green collection result does not close the amended ADR's source boundary. A direct census finds 198 Python files below `src` importing `test_support`, and `src/cadrumo/application/filing/tests/test_m303_did_account_wire_isolated_authority.py` now imports `dev.registry.compiler.record_design` directly. The collection repair in `src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py` similarly replaces an illegal package-facade import with `test_support.registry_authoring`, moving the error without satisfying the architecture. Tests inherit their nearest owner lane and have no exemption; these edges remain explicit deconflation remnants.

### neutral-test-support-layering | high | relocated registry helpers violate the core-only `cadrumo.tests` contract

The new canonical-looking modules `src/cadrumo/tests/registry_observations.py` and `src/cadrumo/tests/registry_tree.py` import domain registry definitions, while `src/cadrumo/tests/storage_path_grammar.py` imports persistence-adapter definitions at call time. The accepted ADR classifies `cadrumo.tests` as neutral core-only test support and states that local or deferred imports do not change the edge. Moving shared helpers there makes outer and application tests collect, but creates an unauthorized inward-to-outward dependency and is not a valid canonical-home relocation.

### deletion-proof | high | registry test deletions are not backed by an auditable atomic relocation

The diff deletes 142 files below the registry test package. Only 51 deleted basenames have a counterpart below `dev`; 91 do not, including substantive authority, legal-grounding, export, historical-model, record-design, and cache tests. Some may have been consolidated or deliberately retired, but neither the current diff nor the collection-only evidence proves preservation or justified redundancy. Collection success cannot substitute for the ADR's requirement to move owning tests atomically or the quality rule requiring distinct behavioral gates to remain.

### post-correction-ownership | low | resolved: helpers now occupy their nearest owning test packages

Post-review correction resolves `neutral-test-support-layering` for the collection repair. `registry_tree.py` and `registry_observations.py` are restored byte-for-byte to `src/cadrumo/domain/calculations/registry/tests`, their consumers name that defining module directly, and `storage_path_grammar.py` now lives under `src/cadrumo/adapters/persistence/storage/tests` with its two owning tests using a relative defining-module import. The affected package initializers remain inert. Existing domain-aware modules already located under `cadrumo.tests`, including `cross_period_seeding.py`, remain broader architecture debt but were present before this repair and are not a regression introduced here.

### post-correction-src-root | high | narrowed: direct development import is gone, but one repair still selects root support

Post-review correction removes every direct `src` import of `dev`, and adding `extract_record_design` to the already-used `test_support.registry_authoring` import in the M303 test does not add a new root dependency edge. However, `test_export_layout_join_ratchet.py` newly resolves its former package-facade symbol through root `test_support.registry_authoring`. That makes collection pass but still contradicts the amended ADR's unconditional prohibition on `src` depending on repository-only roots. The original 198-file census is therefore broader pre-existing debt; this one newly selected boundary remains attributable to the collection repair.

### post-correction-deletion-scope | low | narrowed: deletion proof is broader worktree debt, not a collection-repair regression

The 142 registry-test deletions remain insufficiently mapped in the aggregate dirty diff, so `deletion-proof` remains valid for accepting that broader relocation campaign. Re-review found no evidence that the post-review collection corrections themselves delete additional tests: they restore two exact test-support files to their original owner and relocate the storage helper with its owning tests. The deletion-ledger requirement should block the broader merge/relocation closeout, not the narrowly scoped collection repair.

### final-export-ratchet-relocation | low | resolved: no collection-repair-specific finding remains

The export-layout ratchet now lives in `dev/registry/tests/test_export_layout_join_ratchet.py`, imports its owning development compiler module directly, and the former `src` test is deleted. No governed `src` module references `_validate_export_layout_coverage` or imports the ratchet's `coverage` binding from root test support. This resolves `post-correction-src-root` for the collection repair. The exact final full collection run `20260911T122735.248877Z-pytest-38908-ab356306` finished with exit status zero; focused development collection and Ruff were also reported green. No repair-specific finding remains. Broader pre-existing root-support and deletion-ledger debt recorded above retains its separate disposition.
## Recommendations

- Eliminate every `src` import of `dev` and root `test_support`; relocate authoring-only tests and fixtures into the development lane, and keep runtime-facing tests on published product authorities.
- Split registry-aware fixtures by their nearest legal owner instead of using `cadrumo.tests` as a domain/adapter umbrella. Keep `cadrumo.tests` core-only and keep all package initializers inert.
- Produce a deletion ledger mapping each of the 142 removed tests to an exact relocated test, a superseding gate with equivalent detection value, or a reviewed stale/duplicate rationale; restore or relocate any test without one before accepting the change.
- Re-run the exact collection signal after these boundary corrections and retain its exit status and complete failure identity as evidence.

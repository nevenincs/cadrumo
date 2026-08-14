---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:788800885a8c288632e9c807cca838b4791e3c2deb14ad570ca473581c7c1155'
step_id: 'S09'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Build and run a one-shot migrator transcribing the applicability rule literals into authoring-tree fragments for every modelo outside the campaign-owned 303 and 390 trees, prove hydrated rules compare equal to the literals, then delete the migrated literals outright

## Scope

- `dev/`
- `src/cadrumo/_data/registry/aeat/`
- `src/cadrumo/domain/calculations/registry/_applicability.py`

## Description

- Build one-shot migrator `dev/registry_authoring/migrate_applicability_fragments.py`, in a new `dev/registry_authoring/` package distinct from `dev/registry/` (owned by a concurrent campaign; no prior one-shot-migrator home existed outside it).
- Read every rule through the public `iter_modelo_applicability_rules()` accessor, never the private `_MODELO_APPLICABILITY_RULES` dict directly.
- Exclude modelo ids `"303"`/`"390"` (export-fragment-generator-authority campaign owns those authoring trees).
- Render each fragment via `tomlkit` for correct escaping of the Spanish reason prose; write `applicability/0001-applicability.toml` per revision directory; refuse to overwrite an existing fragment.
- After writing, reload the modelo through the real `load_modelo_directory`, hydrate the written fragment via `hydrate_applicability_rule`, assert equality against the original literal, per revision.
- `--dry-run` default, `--apply` performs the writes and proof, `--json` writes a machine-readable outcome report.
- Ran `--apply` to completion: 25 modelos, 39 revision directories, every one `[OK]`, exit 0, zero mismatches.
- Built the runtime cutover mechanism in `_applicability.py`: `resolve_applicability_rule_from_authority(authority, modelo)` (the real logic, authority passed as a parameter, testable against a scratch authority with no mocks) and `_resolve_registry_applicability_rule(modelo)` (the production wrapper; function-local import of `bundled_authority` is required, not stylistic -- `_authority` transitively imports `_applicability` through the S08 build-validation dispatch chain, so a module-level import would close a real cycle). Deliberately no `@cache`: `bundled_authority()` is already fingerprint-bounded (`W01.P02.S28`), so the resolver costs one O(1) cache-key hash per call and never serves stale data.
- `_modelo_applicability_rule(modelo: str)` is the single seam `derive_modelo_applicability`, `has_applicability_rule`, `iter_modelo_applicability_rules` all read through.
- Add `tests/test_applicability_registry_cutover.py` (3 tests): function-level equivalence (registry-resolved rule vs. the literal it transcribes, evaluated for 3 representative profiles hitting APPLICABLE/NOT_APPLICABLE/INCOMPLETE, with a companion control proving the profile set is not trivially uniform), and staleness (a fresh authority sees a tree mutation; the original authority instance does not mutate in place).
- Empirically proved the no-cache decision out-of-repo: wrapped the exact modelo-only resolver shape in `functools.cache` inside a throwaway subprocess and showed it served the stale value forever after a mutation, while the shipped uncached resolver correctly returned the mutation.
- Flipped the cutover: set `REGISTRY_RESOLVED_APPLICABILITY_MODELOS` to the 25 migrated modelo ids and deleted their 25 entries from `_MODELO_APPLICABILITY_RULES` in the same edit (only `"303"`/`"390"` remain literal), via a script-driven extraction rather than manual line-numbered transcription, then verified by direct inspection of both collections.

## Outcome

Migration: 25/25 modelos, 39/39 revision directories, every one hydration-equals-literal, exit 0. Cutover mechanism: 3/3 new tests pass; both required conditions (function-level equivalence and staleness) proven with real behaviour, no mocks -- staleness proven twice, once in-suite and once via the out-of-repo `functools.cache` counter-demonstration. Post-flip: `ruff check` and `ruff format --check` clean; `pytest --collect-only -q` shows the same 18 pre-existing, unrelated collection errors present at session start, no new ones; the full applicability regression suite (`test_applicability_fragment_family.py` + `test_applicability_registry_cutover.py` + `test_applicability_canonical.py` + `test_modelo_applicability.py` + `test_cross_reference_applicability.py` + `test_source_applicability_window.py`) is 61/61 green.

Investigated and diagnosed a suite difference before accepting it, per explicit instruction to stop and report rather than adjust: 2 tests (`test_seed_modelo_applicability_legal_refs_resolve_in_registry`, `test_impatriado_in_window_routes_annual_irpf_to_modelo_151`) that failed immediately post-`--apply` on the export-layout completeness gate passed on the post-flip run. Traced both line-by-line: each touches `resources().modelos.authority` at exactly one assertion; every applicability verdict, reason and legal_ref either test checks is computed through hardcoded impatriado-routing branches in `derive_modelo_applicability` that run before the rule-table lookup and never reach the code this Step changed. Confirmed with the coordinating agent: an unrelated, operator-directed relocation of the export-layout refusal (registry-build validation to the filing boundary, in progress by other agents at the time) is what flipped `resources().modelos.authority`'s load/refuse state between the two runs, not this Step. No applicability verdict, reason, or legal_ref differs anywhere in the suite.

## Notes

**Mixed-surface disclosure, landed state.** `_MODELO_APPLICABILITY_RULES` is now a mixed surface. `REGISTRY_RESOLVED_APPLICABILITY_MODELOS` names the 25 modelos (100, 111, 115, 117, 123, 126, 128, 130, 131, 180, 184, 187, 188, 190, 193, 194, 200, 202, 322, 347, 349, 353, 369, 720, 721) resolved live from the registry authoring tree through `resolve_applicability_rule_from_authority`. `"303"` and `"390"` remain Python literals in `_MODELO_APPLICABILITY_RULES` -- not unplaced by omission, but because their authoring trees are owned by the export-fragment-generator-authority campaign. `_modelo_applicability_rule` is the single seam deciding which surface answers for a given modelo. The end state is the registry authority as sole source: once the export-fragment campaign closes the 303/390 trees and they are migrated the same way, `_MODELO_APPLICABILITY_RULES` retires outright and this module stops authoring applicability data -- it only reads it.

**RegistrySnapshot asymmetry, ruled deliberate.** `RegistrySnapshot` carries a projection for every other schema family but not `applicability`. This is deliberate: applicability answers "is this modelo due, and to whom" -- the floor rung of the authority-grade ladder (scheduling reach) -- while `RegistrySnapshot` is a filing-context projection one rung up. Resolving applicability without filing-grade review is correct per that ladder, not a gate dodged; coupling it to snapshot construction would wrongly tie a floor-rung fact to filing authority it does not need. Recorded in `resolve_applicability_rule_from_authority`'s docstring.

**Two expected failures, named so a later reader does not mistake them for migration damage.** `test_seed_modelo_applicability_legal_refs_resolve_in_registry` and `test_impatriado_in_window_routes_annual_irpf_to_modelo_151` failed transiently, immediately after `--apply` completed and before the cutover flip, on the wording "the revision declares a calculation-completeness manifest but NO export layout of any format" -- the hardened, operator-directed export-layout completeness gate inside `ValidatedRegistryAuthority.load()`'s `validate_registry()`, refusing 47 revisions tree-wide at that moment (including all six Modelo 303 revisions). This is not migration damage: it is the same gate the operator directed, mid-relocation from registry-build validation to the filing boundary at the exact moment these two tests ran, and both had already recovered to green by the time the flip's own regression suite ran.

Migration and cutover work is UNCOMMITTED at the time of writing; the operator has not authorised commits. Not this Step's scope, explicitly held: the export-layout/withdrawal-mechanism deletion the operator directed separately (a distinct, already-complete effort by other agents on a binding-file split) and the broader "remove every degradation-allowance gate" directive, which the coordinating agent scoped to that named mechanism rather than a codebase-wide sweep from this session.

---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:788800885a8c288632e9c807cca838b4791e3c2deb14ad570ca473581c7c1155'
step_id: 'S09'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Build and run a one-shot migrator transcribing the applicability rule literals into authoring-tree fragments for every modelo outside the campaign-owned 303 and 390 trees, prove hydrated rules compare equal to the literals, then delete the migrated literals outright

## Scope

- `dev/registry/authoring_migrate_applicability_fragments.py`
- `src/cadrumo/_data/registry/aeat/modelos/`
- `src/cadrumo/domain/calculations/registry/applicability.py`
- `src/cadrumo/domain/calculations/registry/tests/test_applicability_registry_cutover.py`

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

Commits `58d607019d` and `a284a8663c` delivered S09's exact historical cohort: 25 eligible modelos, 39 revision directories, fragments written with hydration equality, production cut over through `REGISTRY_RESOLVED_APPLICABILITY_MODELOS`, and all 25 migrated Python literals deleted atomically. The only literal rules remaining are Modelo 303 and Modelo 390, exactly the campaign-owned exclusions assigned to S19. Later directly authored applicability enrollments do not reopen or expand this historical migration cohort.

The current scratch-authority cutover suite passes 3/3, proving live registry resolution and mutation visibility without the bundled tree. Commit `ea09f7c399` reconciles the exhausted migrator's documentation and retains it solely for the explicit S19 ownership release. Ruff format/check and `git diff --check` pass.

## Notes

The earlier record's `UNCOMMITTED` statement and frozen description of 25 as the complete current owner set are historical. S09 is committed; the 25 are its migration cohort, while later rules may be authored directly in registry data. The migrator now yields no eligible rows because its only remaining literal inputs are the deliberately excluded 303 and 390 rules.

The bundled registry ownership property currently refuses before reaching this contract because of the active Modelo 200 revision split. That foreign red is recorded rather than represented as a passing S09 gate. No migrated non-303/390 Python literal residue exists, and no M200, 303, or 390 data path was touched during reconciliation.

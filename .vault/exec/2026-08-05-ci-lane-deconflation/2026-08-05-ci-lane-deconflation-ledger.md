---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:4f7b58860c75d6c13e6b9faadd4d4cee97a717db661753721adce0c704490c5b'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# `ci-lane-deconflation` ledger

## Changes

- `S02` `T` `.github/workflows/frontend.yml`
- `S03` `T` `.github/workflows/ci-full.yml`
- `S04` `T` `.github/workflows/ci-full.yml`
- `S05` `T` `origin/main`
- `S06` `T` `src/cadrumo/entrypoints/cli/tests`
- `S07` `T` `src/cadrumo/entrypoints/mcp`
- `S08` `T` `dev/audit`
- `S08` `T` `dev/deploy`
- `S08` `T` `dev/env`
- `S08` `T` `dev/registry`
- `S08` `T` `dev/docs`
- `S09` `T` `.github/workflows/ci-full.yml`
- `S11` `T` `src/cadrumo/domain/calculations/registry/tests`
- `S12` `T` `src/cadrumo/adapters/inbound/declaracion/_parser.py`
- `S13` `T` `src/cadrumo/_data/registry/aeat/modelos/100`
- `S14` `T` `src/cadrumo/_data/registry/aeat/legal`
- `S15` `T` `src/cadrumo/core/tests/test_toml_registry_parity.py`
- `S16` `T` `dev/packaging/tests/test_verify_distribution_identity.py`
- `S17` `T` `.vault/exec/2026-06-13-semantic-dedup-epic`
- `S18` `T` `src/cadrumo/domain/calculations/registry/tests/test_snapshot_filing_period_coverage.py`
- `S19` `T` `src/cadrumo/domain/calculations/registry`
- `S20` `T` `src/cadrumo/tests/test_import_hygiene_gate.py`
- `S21` `T` `src/cadrumo/domain/calculations/registry/_validate_relation_sources.py`
- `S22` `T` `src/cadrumo/entrypoints/mcp`
- `S23` `T` `src/cadrumo/entrypoints/mcp`
- `S24` `T` `src/cadrumo/entrypoints/cli/tests/test_modelo_result_summary_labels.py`
- `S25` `T` `src/cadrumo/entrypoints/cli/tests`
- `S26` `T` `.vaultspec/templates`
- `S27` `T` `src/cadrumo/entrypoints/mcp/tests`
- `S28` `T` `the two integration serial budget tests and .github/workflows/ci-full.yml`
- `S29` `T` `the pytest timeout failure-reporting hook and pyproject.toml`
- `S30` `T` `src/cadrumo/application/operator_surface/tests/test_contract.py`
- `S30` `T` `src/cadrumo/application/operator_surface/tests/test_contract_live.py`
- `S31` `T` `justfile`
- `S31` `T` `pyproject.toml`
- `S32` `T` `dev/registry/tests`
- `S33` `T` `src/cadrumo/tests/test_lane_reachability.py`
- `S34` `T` `justfile`
- `S34` `T` `.github/workflows/ci-full.yml`
- `S35` `T` `src/cadrumo/tests/test_lane_reachability.py and the lane declarations it reads`
- `S36` `T` `justfile and .github/workflows/docs.yml and dev/docs/tests`
- `S37` `T` `src/cadrumo/application/operator_surface/_help.py`
- `S37` `T` `src/cadrumo/locales/`
- `S37` `T` `src/cadrumo/application/operator_surface/tests/test_contract.py`
- `S38` `T` `dev/registry/_provenance_manifest.py`
- `S38` `T` `dev/registry/tests/test_export_tree.py`
- `S39` `T` `dev/registry/_provenance_manifest.py`
- `S39` `T` `dev/registry/tests/test_export_tree.py`
- `S40` `T` `pyproject.toml and .github/workflows/ci.yml and the four named gate modules`
- `S42` `T` `pyproject.toml and justfile and dev/tests and dev/registry/tests`
- `S43` `T` `.github/workflows/ci.yml`
- `S43` `T` `justfile`
- `S43` `T` `prek.toml`
- `S44` `T` `pyproject.toml and .github/workflows/ci.yml and the four named gate modules and src/cadrumo/adapters/outbound/fx`
- `S45` `T` `the plan and .github/workflows and justfile as the mapping's subject`
- `S46` `T` `src/cadrumo/adapters/persistence/storage`
- `S46` `T` `src/cadrumo/application/user_profile`
- `S46` `T` `src/cadrumo/application/bucket_maintenance`
- `S46` `T` `src/cadrumo/core`
- `S46` `T` `src/cadrumo/domain/calculations/registry/_compiled_cache.py`
- `S46` `T` `dev/registry/_generated_tree_publication.py`
- `S46` `T` `dev/write_site_census.py`
- `S47` `T` `.github/workflows/packaging-quick.yml and dev/packaging/tests/test_packaging_quick_workflow.py`
- `S48` `T` `dev/ci/tests/test_ci_workflow.py and justfile`
- `S49` `T` `.github/workflows/ci.yml and dev/ci/tests/test_ci_workflow.py`

- `S41` `T` `src/cadrumo/entrypoints/cli/_common.py`
- `S41` `T` `src/cadrumo/entrypoints/cli/_period_parsing.py`
- `S41` `T` `src/cadrumo/entrypoints/cli/_date_parsing.py`
- `S41` `T` `src/cadrumo/entrypoints/cli/_decimal_parsing.py`
- `S41` `T` `src/cadrumo/entrypoints/cli/_operator_surface_reconciliation.py`
- `S41` `T` `dev/quality/import_hygiene_test_debt.json`
- `S50` `T` `src/cadrumo/locales/es/modelo/schema/347.yml`
- `S50` `T` `src/cadrumo/locales/en/modelo/schema/347.yml`
- `S50` `T` `src/cadrumo/locales/ca/modelo/schema/347.yml`
- `S50` `T` `src/cadrumo/locales/hu/modelo/schema/347.yml`

## Notes

`S41` is RECORDED BUT NOT COMPLETE and its checkbox stays open. The row's own
`_common` half landed -- 1714 to 1160 lines across four new modules, under the
1250 ceiling with no pin, no `--accept-growth` and no carveout -- but the flip
the row exists to perform did not, because its premise that `_common` was the
sole remaining module-size offender is false at HEAD. These lines record the
code that moved so the decomposition is not invisible; they do not claim the
Step is done. `S51` through `S55` carry the populations that gate it.

The `import_hygiene_test_debt.json` line is collateral of the decomposition
rather than separate work: the debt entry for
`test_period_boundary_authority.py` recorded its reach against `cli._common`,
and repointing the import left that entry answering nothing while creating an
undocumented reach at `cli._period_parsing`. Both halves were corrected in the
same change, because a spare debt slot silently widens the ratchet.

The lane was measured twice, 192F/98E then 184F/75E, and NEITHER run is a
faithful reproduction of the CI step: `just docs` fails on 21 cli-sequence
golden divergences, so the terminology gates that P01.S04 ordered above this
step never received their artefact and 57 of the 75 errors are collection
failures of unknown verdict rather than measured backlog. The true failure
count is not knowable until `S55` lands.

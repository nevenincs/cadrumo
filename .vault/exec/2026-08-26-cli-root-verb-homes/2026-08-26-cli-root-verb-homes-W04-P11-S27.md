---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:ca6cc117adab46207b5f7b0cab3b323d07aff123b839ae56b9762599cb3802ca'
step_id: 'S27'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Retire config profile preflight in favour of app modelo readiness; sweep its specs, handler, payloads, tests, locale keys and documented sequences; `src/cadrumo/entrypoints/cli/_config/`.

## Scope

- `src/cadrumo/entrypoints/cli/_config/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_config/_profile_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_profile_inspect.py`
- `M` `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_terminal_errors.py`
- `M` `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_readiness_cli.py`
- `M` `src/cadrumo/application/modelo/_profile_readiness_gate.py`
- `D` `src/cadrumo/entrypoints/cli/tests/test_config_preflight_revision_default.py`
- `D` `src/cadrumo/entrypoints/cli/_config/tests/test_preflight_revision_ambiguity_refusal.py`
- `R` `src/cadrumo/entrypoints/cli/tests/test_config_profile_preflight_scope.py -> src/cadrumo/entrypoints/cli/tests/test_profile_readiness_blocks_modelo_work.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_config_profile_validate_payload_contract.py`
- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `M` `docs/how-to/choose-modelo.md`
- `M` `docs/how-to/censo-update.md`
- `M` `docs/_sequences/contracts/how-to/censo-update/censo-update-preflight.seq`
- `M` `docs/_sequences/contracts/how-to/choose-modelo/choose-modelo-applicability.seq`
- `M` `docs/_sequences/contracts/how-to/profile-setup/profile-setup-inspect.seq`
- `M` `docs/_sequences/how-to/censo-update/censo-update-preflight.json`
- `M` `docs/_sequences/how-to/choose-modelo/choose-modelo-applicability.json`
- `M` `docs/_sequences/how-to/profile-setup/profile-setup-inspect.json`
- `M` `docs/locales/es/LC_MESSAGES/how-to/choose-modelo.po`
- `M` `docs/locales/ca/LC_MESSAGES/how-to/choose-modelo.po`
- `M` `docs/locales/hu/LC_MESSAGES/how-to/choose-modelo.po`
- `M` `docs/locales/es/LC_MESSAGES/how-to/censo-update.po`
- `M` `docs/locales/ca/LC_MESSAGES/how-to/censo-update.po`
- `M` `docs/locales/hu/LC_MESSAGES/how-to/censo-update.po`
- `M` `dev/quality/registry_authority_consumer_census.v1.json`
- `verify:` `pytest test_profile_readiness_blocks_modelo_work.py -m integration` -> `pass`
- `verify:` `pytest test_documented_command_conformance.py -m integration` -> `pass`
- `verify:` `python -m dev.docs.sequences check --page how-to/profile-setup` -> `pass`
- `verify:` `python -m dev.locales scaffold --check` -> `pass`

## Notes

Both recorded blockers were refuted rather than waited out. `config profile
preflight` reads the active profile record through `_read_profile_record`, so it
required an unlocked session exactly as `app modelo readiness` does; the
"preflight works sessionless" claim was wrong. And the retiree needed no working
run to be compared, because `ModeloReadinessResult.missing` carries the same six
fields as the retired `ProfilePreflightMissingPayload` over the same
`modelo_work_profile_preflight_report` gate, plus the registry, binding and
ledger axes.

Retiring the verb exposed a live defect in its replacement: `app modelo
readiness --revision-id` raised `TypeError: 'typing.TypeAliasType' object is
not callable`, because the handler called `RevisionId(...)` on a PEP 695 alias.
It was the only such call site in the tree, and the flag had never worked.

The documented outcome changed truthfully. Preflight exited 0 on a fresh
sandbox profile; readiness exits 2 there, because `binding_ready` is false
while four source bindings are unfilled. The goldens and the prose now record
that, and the guide tells the operator to read the failing axis rather than the
overall verdict.

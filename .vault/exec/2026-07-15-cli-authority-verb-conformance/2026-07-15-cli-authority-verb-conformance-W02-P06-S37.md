---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S37'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S37 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Atomically replace broad auth clear across backend and live CLI contracts with typed target-scoped logout_operator_auth and reset_operator_auth, complete provider session coverage, safe secret and lock cleanup, distinct schemas and events, exact contract/risk/help/write metadata, four-locale help, and real workflow and command tests without a compatibility wrapper and ## Scope

- `src/cadrumo/application/auth/_operator_results.py`
- `src/cadrumo/application/auth/_operator_scope.py`
- `src/cadrumo/application/auth/_sessions.py`
- `src/cadrumo/application/auth/_acquisition_lock.py`
- `src/cadrumo/application/auth/_operator.py`
- `src/cadrumo/application/auth/__init__.py`
- `src/cadrumo/application/tests/test_cli_workflow_verification.py`
- `src/cadrumo/application/auth/tests/test_operator_storage_session.py`
- `src/cadrumo/entrypoints/cli/_config/_auth.py`
- `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `src/cadrumo/application/storage_write_policy.py`
- `src/cadrumo/application/operator_surface/_contract.py`
- `src/cadrumo/application/operator_surface/_risk_table.py`
- `src/cadrumo/application/operator_surface/_help.py`
- `src/cadrumo/core/errors/registry/_application_part1.py`
- `src/cadrumo/locales/en.yml`
- `src/cadrumo/locales/es.yml`
- `src/cadrumo/locales/ca.yml`
- `src/cadrumo/locales/hu.yml`
- `src/cadrumo/entrypoints/cli/_config/tests/test_auth_round5_surface.py`
- `src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py`
- `src/cadrumo/entrypoints/cli/tests/test_output_language_parity.py`
- `src/cadrumo/entrypoints/cli/tests/test_workflow_surface.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Atomically replace broad auth clear across backend and live CLI contracts with typed target-scoped logout_operator_auth and reset_operator_auth, complete provider session coverage, safe secret and lock cleanup, distinct schemas and events, exact contract/risk/help/write metadata, four-locale help, and real workflow and command tests without a compatibility wrapper

## Scope

- `src/cadrumo/application/auth/_operator_results.py`
- `src/cadrumo/application/auth/_operator_scope.py`
- `src/cadrumo/application/auth/_sessions.py`
- `src/cadrumo/application/auth/_acquisition_lock.py`
- `src/cadrumo/application/auth/_operator.py`
- `src/cadrumo/application/auth/__init__.py`
- `src/cadrumo/application/tests/test_cli_workflow_verification.py`
- `src/cadrumo/application/auth/tests/test_operator_storage_session.py`
- `src/cadrumo/entrypoints/cli/_config/_auth.py`
- `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `src/cadrumo/application/storage_write_policy.py`
- `src/cadrumo/application/operator_surface/_contract.py`
- `src/cadrumo/application/operator_surface/_risk_table.py`
- `src/cadrumo/application/operator_surface/_help.py`
- `src/cadrumo/core/errors/registry/_application_part1.py`
- `src/cadrumo/locales/en.yml`
- `src/cadrumo/locales/es.yml`
- `src/cadrumo/locales/ca.yml`
- `src/cadrumo/locales/hu.yml`
- `src/cadrumo/entrypoints/cli/_config/tests/test_auth_round5_surface.py`
- `src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py`
- `src/cadrumo/entrypoints/cli/tests/test_output_language_parity.py`
- `src/cadrumo/entrypoints/cli/tests/test_workflow_surface.py`

## Description

- Replace the broad auth-clear result and facade with distinct, strict, secret-free logout and reset contracts.
- Resolve explicit provider, all-provider, configured-provider, and explicit target-bucket scopes without switching the global active pointer.
- Delete provider sessions and locks through exact bucket routes, including the production Cl@ve Permanente session stem.
- Preserve provider and certificate configuration on logout; remove configuration, certificate registrations, and canonical secure-storage secrets on reset.
- Suppress duplicate state writes and events on idempotent reruns, and emit events only for providers whose artefacts or configuration changed.
- Replace the CLI command, schemas, operator contract, risk metadata, write policy, help inventory, and four-locale reference text without a compatibility alias.
- Add real encrypted-storage, ambient-session restoration, token-root, event, reserved-provider, schema, language, and destructive-confirmation coverage.

## Outcome

- `aeat config auth logout` now terminates local provider sessions without removing provider configuration or locks.
- `aeat config auth reset` now performs confirmed provider-custody cleanup and reports only actual effects.
- Explicit bucket B operations restore an ambient bucket A session unchanged.
- Known reserved providers are valid idempotent targets; omitted scope without configured state and conflicting `--provider` plus `--all` are typed localized refusals.
- The executable application and CLI source tree contains no old auth-clear facade, payload, command registration, risk key, or write-policy key.
- Focused verification passed: 13 auth/workflow tests, 22 auth CLI and confirmation tests, 6 output-language tests, 149 schema/operator-contract tests, 17 registry tests, four locale audits, Ruff, and all five import-linter contracts.

## Notes

- A transient Windows file-replace lock interrupted one Hungarian locale-manager write. Retrying the remaining manager operations completed successfully; no locale file was edited manually.
- The first CLI pytest invocations selected no tests because project defaults select the unit marker. Re-running the same focused files with the integration marker produced the passing results recorded above.
- Certificate keyring compatibility and the separate broad `config reset --scope auth` writer remain outside this Step under their assigned downstream plan work.

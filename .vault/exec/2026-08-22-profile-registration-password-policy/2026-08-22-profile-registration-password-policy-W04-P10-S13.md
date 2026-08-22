---
tags:
  - '#exec'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:63ef4d6a242ccf3bfd9e3c9f7545403fb8c9152d0dc22c487115053fa9687af8'
step_id: 'S13'
related:
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---

# Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then run focused anti-regression tests structural audits locale and documentation gates feature-surface checks full tests and vault checks

## Scope

- `repository quality gates`

## Description

- Re-ground the repository and governing decision semantically, then confirm the
  live credential, custody, recovery, application, TUI, CLI, locale, and error
  registry symbols with exact searches.
- Exercise the complete feature surface with serial focused tests and run the
  repository's structural, locale, API-reference, documentation, and Vault
  gates without absorbing concurrent work.
- Verify retired password-policy symbols remain absent and recovery-secret
  operations remain independent of profile-password assessment.
- Record full-tree failures against their exact current-HEAD owners instead of
  describing a partially executed or deselected lane as green.

## Outcome

- The default credential/security lane passed: 67 passed and 82 integration
  cases deselected in 24.01 seconds. The integration credential, TUI, scripted
  CLI, locale, and public-boundary lane passed: 104 passed in 92.43 seconds.
- The serial custody default lane passed: 218 passed and 10 deselected in 78.42
  seconds. Custody exposes no integration-marked tests (228 deselected). The
  recovery public-boundary lane passed 22 tests and authentication mapping
  passed 27 tests. Recovery-artifact formatting verification passed Ruff lint,
  Ruff format check, and 7 capsule-envelope rotation tests.
- Feature-scoped Ruff lint passed. Exact negative searches found no production
  `NIST_PASSPHRASE_MIN_LENGTH`, `PROFILE_CUSTODY_PASSWORD_MIN_SCALARS`,
  `validate_profile_password`, or `map_profile_password_proof_failure`; the two
  custody names occur only as obsolete-symbol absence assertions. Recovery
  modules contain no profile-password assessment references.
- The feature-scoped Vault behavioral checks passed with two warnings: the
  feature index has 4 related links for 16 feature documents, and the reviewed
  S12 execution record requires refreshed lifecycle metadata. Neither warning
  identifies a runtime or security defect.
- The path-scoped feature surface is green. No in-scope production or test red
  was found.

## Notes

- Full-tree gates are not green because concurrent, non-feature work is
  incomplete. Import-linter kept 9 contracts and reported 1 existing layered
  architecture contract broken by application-to-adapter imports. Full Ruff
  lint reported unrelated diagnostics including SIM300 in locale tests, E501 in
  the facade export scanner, and RUF022 in the calculation registry; Ruff format
  reported 94 unrelated files needing formatting. No such file was modified.
- Locale scaffold check/audit reports broad Modelo schema-leaf drift (for
  example 275 missing Catalan leaves), with no profile-credential key in the
  reported failures. API-reference check/audit reports 4 missing, 2 orphan, and
  4 stale stubs owned by concurrent calculation, operator-surface, registry,
  and source-connectivity changes. The narrow API docs suite passed 10 tests and
  failed the matching stub-completeness test.
- Documented-command conformance passed 337 cases and failed one unrelated
  workstation agent-harness sequence that cites absent `aeat app agent
  --output`. The user-scope nitpicky build failed after 67.98 seconds with 13
  unrelated warnings/errors: seven generated casilla-200 markup warnings and
  six stale filing/modelo CLI-sequence frame counts.
- `just docs-check 4` was stopped safely after more than ten minutes at roughly
  93 percent with many failures/errors and no final count; the bounded gates
  above preserve exact actionable failures. No orphaned process from that run
  remained.
- The prescribed full corpus harness stopped at collectability after 142.20
  seconds: five unrelated agent-evaluation/harness modules import concurrent
  symbols that are absent from current HEAD. Consequently the harness-protected
  full two-lane run was not represented as executed. Feature-focused lanes and
  the complete serial custody lane remained authoritative for this change.

## Reproducible command transcript

The two aggregate credential lanes were re-run during evidence repair because
the first version of this record did not preserve their literal path lists:

```text
uv run pytest -q -n 0 -m "unit and not external_tool and not os_keychain" src/cadrumo/core/tests/test_credentials.py src/cadrumo/core/errors/tests/test_registry.py src/cadrumo/core/errors/tests/test_registry_enforcement.py src/cadrumo/application/user_profile/tests/test_registration.py src/cadrumo/application/user_profile/tests/test_passphrase_rotation.py src/cadrumo/application/user_profile/tests/test_authentication_failure_mapping.py src/cadrumo/adapters/inbound/tui/tests/test_registration_screen.py src/cadrumo/adapters/inbound/tui/tests/test_profile_password_locale_parity.py src/cadrumo/entrypoints/cli/_config/tests/test_scripted_profile_creation.py src/cadrumo/entrypoints/cli/_config/tests/test_profile_password_inbound_matrix.py
```

Exit 0: 67 passed, 82 deselected in 37.90 seconds on the repair HEAD (the
original run was 24.01 seconds).

```text
uv run pytest -q -n 0 -m "integration and not serial and not os_keychain" src/cadrumo/application/user_profile/tests/test_registration.py src/cadrumo/application/user_profile/tests/test_passphrase_rotation.py src/cadrumo/application/user_profile/tests/test_recovery_custody.py src/cadrumo/adapters/inbound/tui/tests/test_registration_screen.py src/cadrumo/adapters/inbound/tui/tests/test_profile_password_locale_parity.py src/cadrumo/entrypoints/cli/_config/tests/test_scripted_profile_creation.py src/cadrumo/entrypoints/cli/_config/tests/test_profile_password_inbound_matrix.py
```

Exit 0: 104 passed, 5 deselected in 153.56 seconds on the repair HEAD (the
original run was 92.43 seconds).

The custody, recovery, mapping, and artifact commands were:

```text
uv run pytest -q -n 0 src/cadrumo/adapters/persistence/storage/custody --maxfail=1
uv run pytest -q -n 0 -m integration src/cadrumo/adapters/persistence/storage/custody --maxfail=1
uv run pytest -q -n 0 -m integration src/cadrumo/application/user_profile/tests/test_recovery_custody.py --maxfail=1
uv run pytest -q -n 0 src/cadrumo/application/user_profile/tests/test_authentication_failure_mapping.py --maxfail=1
uv run ruff check src/cadrumo/adapters/persistence/storage/custody/_recovery_artifact.py
uv run ruff format --check src/cadrumo/adapters/persistence/storage/custody/_recovery_artifact.py
uv run pytest -q -n 0 src/cadrumo/adapters/persistence/storage/custody/tests/test_capsule_envelope_rotation.py --maxfail=1
```

Their exit states were respectively: exit 0 with 218 passed/10 deselected in
78.42 seconds; exit 1 because zero tests ran/228 were deselected; exit 0 with
22 passed; exit 0 with 27 passed; exit 0; exit 0; and exit 0 with 7 passed in
8.48 seconds. The zero-test integration invocation is evidence of marker
absence, not a green test lane.

The feature Ruff scope was explicit and contained only the credential change's
production and test directories/files:

```text
uv run ruff check src/cadrumo/core/_credentials.py src/cadrumo/core/tests/test_credentials.py src/cadrumo/core/__init__.py src/cadrumo/application/user_profile src/cadrumo/adapters/inbound/tui/_registration_screen.py src/cadrumo/adapters/inbound/tui/tests/test_registration_screen.py src/cadrumo/adapters/inbound/tui/tests/test_profile_password_locale_parity.py src/cadrumo/entrypoints/cli/_config/_scripted_registration.py src/cadrumo/entrypoints/cli/_config/tests/test_scripted_profile_creation.py src/cadrumo/entrypoints/cli/_config/tests/test_profile_password_inbound_matrix.py src/cadrumo/adapters/persistence/storage/custody
uv run ruff format --check src/cadrumo/core/_credentials.py src/cadrumo/core/tests/test_credentials.py src/cadrumo/core/__init__.py src/cadrumo/application/user_profile src/cadrumo/adapters/inbound/tui/_registration_screen.py src/cadrumo/adapters/inbound/tui/tests/test_registration_screen.py src/cadrumo/adapters/inbound/tui/tests/test_profile_password_locale_parity.py src/cadrumo/entrypoints/cli/_config/_scripted_registration.py src/cadrumo/entrypoints/cli/_config/tests/test_scripted_profile_creation.py src/cadrumo/entrypoints/cli/_config/tests/test_profile_password_inbound_matrix.py src/cadrumo/adapters/persistence/storage/custody
```

Ruff check exited 0. Format check identified only the then-unformatted
`_recovery_artifact.py` plus unrelated custody tests
`test_custody_ceilings_have_one_home.py` and
`test_local_record_witness_contract.py`; formatting the production file and
re-running its three bounded commands above exited 0. The two unrelated files
were not changed. The repository-wide diagnostic commands were `uv run ruff
check .` and `uv run ruff format --check .`; they exited non-zero with the
unrelated paths and 94-file format count recorded above.

The exact negative-space searches were:

```text
rg -n --glob '!*.md' --glob '!*.json' --glob '!*.yml' --glob '!*.yaml' --glob '!*.po' --glob '!*.pot' 'NIST_PASSPHRASE_MIN_LENGTH|PROFILE_CUSTODY_PASSWORD_MIN|validate_profile_password|map_profile_password_proof_failure' src dev
rg -n 'assess_profile_password|ProfilePasswordAssessment|PROFILE_PASSWORD_(MIN|MAX)' src/cadrumo/adapters/persistence/storage/custody/*recovery* src/cadrumo/adapters/persistence/storage/custody/_kdf_supervision.py src/cadrumo/adapters/persistence/storage/custody/_kdf_worker.py
```

The first search exited 0 solely because it found the intentional
obsolete-symbol string assertions in `custody/tests/test_records.py`; the
second exited 1 with no recovery/profile-policy coupling matches. The feature
Vault command was `uv run vaultspec-core vault
check all --feature profile-registration-password-policy`; exit 0 with all
behavioral checks clean and the feature-index/lifecycle warnings recorded
above.

The structural, registry, and documentation commands were:

```text
uv run lint-imports
uv run python -m dev.locales scaffold --check
uv run python -m dev.locales audit
uv run python -m dev.docs.apidocs scaffold --check
uv run python -m dev.docs.apidocs audit
uv run pytest -q -n 0 dev/docs/apidocs/tests/test_manager.py dev/docs/tests/test_api_stubs.py dev/docs/tests/test_docs_build.py dev/docs/tests/test_docs_build_full_scope.py --maxfail=1
uv run pytest -q -n 0 -m integration src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py dev/tests/test_suggestion_command_conformance.py --maxfail=1
uv run pytest -q -n 0 -m docs dev/docs/tests/test_docs_build_user_scope.py --maxfail=1
just test-harness
just docs-check 4
```

`lint-imports` exited 1 with 9 contracts kept and the existing layered contract
broken. Locale scaffold/audit and API scaffold/audit exited non-zero with the
unrelated Modelo and 4-missing/2-orphan/4-stale drift above. The bounded API
suite exited 1 after 10 passed and the stub-completeness failure. Documented
command conformance exited 1 after 337 passed on
`docs/_sequences/contracts/workstation-setup/install-agent-harness.seq`.
Nitpicky user scope exited 1 after 67.98 seconds with the exact 13 diagnostics
already listed. `just test-harness` exited 1 at collectability after 142.20
seconds on `dev/agent_eval/tests/test_active_profile_confirmation_golden.py`,
`dev/agent_eval/tests/test_confirmation_gate_golden.py`,
`dev/agent_eval/tests/test_identity_switch_scoring_golden.py`, and
`src/cadrumo-harness/src/cadrumo_harness/tests/test_harness_delivery.py`; its
fifth corpus-provenance report was transient and the narrowed direct collection
later collected those two tests. `just docs-check 4` was manually interrupted
with Ctrl-C only after more than ten minutes, no output movement for several
minutes, approximately 93 percent progress, and many visible failures/errors;
there is deliberately no invented exit code, terminal count, or duration.

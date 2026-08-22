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
  93 percent with many failures/errors and no final count. The exact elapsed
  duration, individual diagnostics, and exit status were not captured. No
  orphaned process from that run remained.
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
re-running the artifact Ruff-check, Ruff-format-check, and seven-test commands
in this transcript exited 0. The two unrelated files
were not changed. The repository-wide diagnostic commands were `uv run ruff
check .` and `uv run ruff format --check .`; they exited non-zero with the
following captured Ruff-check paths/codes:
`dev/locales/tests/test_row_table_tr_argument_discovery.py` (SIM300),
`dev/quality/facade_export_scan.py` (E501), and
`src/cadrumo/domain/calculations/registry/__init__.py` (RUF022). The complete
Ruff-check diagnostic list and duration were not captured. Ruff format reported
94 files would be reformatted and 6,786 already formatted; its duration was not
captured.

The exact negative-space searches were:

```text
rg -n --glob '!*.md' --glob '!*.json' --glob '!*.yml' --glob '!*.yaml' --glob '!*.po' --glob '!*.pot' 'NIST_PASSPHRASE_MIN_LENGTH|PROFILE_CUSTODY_PASSWORD_MIN|validate_profile_password|map_profile_password_proof_failure' src dev
rg -n --glob '*recovery*.py' --glob '!**/tests/**' 'assess_profile_password|ProfilePasswordAssessment|PROFILE_PASSWORD_(MIN|MAX)' src/cadrumo/adapters/persistence/storage/custody
rg -n 'assess_profile_password|ProfilePasswordAssessment|PROFILE_PASSWORD_(MIN|MAX)' src/cadrumo/adapters/persistence/storage/custody/_kdf_supervision.py src/cadrumo/adapters/persistence/storage/custody/_kdf_worker.py
```

The obsolete-symbol search exited 0 solely because it found the intentional
string assertions in `custody/tests/test_records.py`. Both corrected recovery
searches were executed successfully by PowerShell on the repair HEAD and exited
1 with no matches in 0.26 seconds combined. The feature Vault command was `uv
run vaultspec-core vault check all --feature
profile-registration-password-policy`; exit 0 with all behavioral checks clean
and one exact warning: the feature index had 4 related links for 17 feature
documents. Its duration was not captured.

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

`lint-imports` exited 1 with 9 contracts kept and one broken `AEAT layered
architecture` contract; the full edge list and duration were not captured.
Locale scaffold/audit exited non-zero; the captured output included `ca.yml
missing=275` and missing Modelo 036, 220, and 390 schema leaves. The complete
locale diagnostic list, per-command exit status, and durations were not
captured. API scaffold/audit reported these exact 4 missing stubs:
`cadrumo.application.modelo._calculation_route`,
`cadrumo.application.operator_surface._calculation_workflows`,
`cadrumo.application.registry._source_connectivity_authority`, and
`cadrumo.core.source_connectivity`; 2 exact orphan stubs:
`cadrumo.application.operator_surface._classification` and
`cadrumo.application.operator_surface._risk_table`; and 4 stale parents:
`cadrumo.application.modelo`, `cadrumo.application.operator_surface`,
`cadrumo.application.registry`, and `cadrumo.core`. Their durations were not
captured. The bounded API suite exited 1 after 10 passed at
`test_every_source_module_has_a_stub`, reporting the same 4/2/4 set; duration
not captured.

Documented-command conformance exited 1 after 337 passed because
`docs/_sequences/contracts/workstation-setup/install-agent-harness.seq` cites
`@result aeat --format json app agent --output ./operator-workspace`: `--output`
is not an `aeat app` or global option and `agent` is not an `aeat app`
subcommand. It completed in 5.77 seconds. Nitpicky user scope exited 1 after
67.98 seconds with these exact 13 diagnostics: generated
`_generated/casillas/200.rst` markup warnings at lines 6684, 112222, 112255,
112288, 112428, 112461, and 112494; golden/directive frame mismatches at
`how-to/filing-spine.md:83` (7 versus 9), `:211` (6 versus 8), `:225` (6 versus
8), and `:239` (6 versus 8); `how-to/modelo-303.md:164` (6 versus 8); and
`how-to/verification-reports.md:202` (7 versus 9).

`just test-harness` exited 1 at collectability after 142.20 seconds on
`dev/agent_eval/tests/test_active_profile_confirmation_golden.py` (missing
`command_classification`),
`dev/agent_eval/tests/test_confirmation_gate_golden.py` (missing
`connected_server_and_client_session`),
`dev/agent_eval/tests/test_identity_switch_scoring_golden.py` (missing
`command_classification`), and
`src/cadrumo-harness/src/cadrumo_harness/tests/test_harness_delivery.py`
(missing `profile_bucket_session_open_resumed`). The harness also reported a
fifth corpus-provenance collection failure; its exact original path/message was
not captured. A direct follow-up collected the corpus-provenance module's two
tests, but the literal direct-collection command and duration were not captured
and are therefore not reconstructed here. `just docs-check 4` was manually interrupted
with Ctrl-C only after more than ten minutes, no output movement for several
minutes, approximately 93 percent progress, and many visible failures/errors;
the exact duration, diagnostic list, terminal count, and exit status were not
captured.

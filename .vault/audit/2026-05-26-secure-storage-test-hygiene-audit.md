---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---



# `secure-storage-production-hardening` audit: `test hygiene`

## Scope

Audited secure-storage-related tests for tautological assertions, fake or stub helpers, monkeypatch and environment shortcuts, skips, xfails, and mirrored business logic.

## Good Patterns

- `src/aeat/application/user_profile/test_repository_anti_tautology.py` and `src/aeat/domain/filing/test_roundtrip_anti_tautology.py` deliberately corrupt encrypted SQL payloads and prove the real load boundary rejects or surfaces the mutation. These are non-tautological boundary proofs.
- `src/aeat/application/test_state_projection.py` now uses `override_settings` and `EphemeralMasterKeyProvider` instead of env monkeypatching.
- `src/aeat/tests/secure_sql.py` provides a shared `isolated_ephemeral_secure_sql` helper that routes through `override_settings`.
- `src/aeat/entrypoints/cli/test_backend_boundary.py` already guards against CLI unit tests using process-state and skip language.
- `uv run pytest src/aeat/tests/test_secure_sql.py src/aeat/entrypoints/cli/test_backend_boundary.py -q` reported 26 passed.

## Findings

- High: many secure-storage-adjacent tests still set `AEAT_DATABASE_URL` through `monkeypatch.setenv`, including application ledger, filing, modelo, live, user-profile, domain repository, and CLI workflow tests. Settings/env parser tests can legitimately exercise env parsing; repository and CLI roundtrip tests should migrate to `override_settings` or `isolated_ephemeral_secure_sql`.
- High: some tests still manipulate `os.environ` directly for storage configuration. These should be replaced with centralized settings helpers unless the test is specifically proving env loading semantics.
- Medium: POSIX-only secure-storage file-permission tests use `pytest.mark.skipif`. The current project rule says tests must not use skips; this needs either a platform-neutral assertion pattern or a documented separate policy decision.
- Medium: legacy direct-engine tests under the envelope repository suite use monkeypatch to route default SQL engines. They should be migrated to a settings-backed helper before further runtime enrollment work broadens.
- Low: namespace literal assertions in user-profile repository tests are contract checks today, but they will become duplication once the namespace registry wave lands. `W03` and `W11.P19.S76` should replace local string assertions with registry-entry assertions.

## Disposition

- `W07.P12-S53` and `W07.P13-S54-S55` own classified secure-SQL backlog selection and guarded repair.
- `W11.P19.S74` owns replacing naked env handling in storage-adjacent tests with centralized settings helpers.
- `W11.P19.S75` owns replacing tautological or shortcut tests with real-behavior coverage.
- `W11.P19.S77` owns guard expansion so new tests cannot reintroduce direct env mutation, fake/stub shortcuts, skip/xfail shortcuts, or mirrored business logic.

## Validation

`uv run pytest src/aeat/tests/test_secure_sql.py src/aeat/entrypoints/cli/test_backend_boundary.py -q` reported 26 passed.

The audit used targeted `rg` scans for `monkeypatch`, direct `os.environ` storage mutation, mocks, fakes, stubs, `skip`, `skipif`, and `xfail` in secure-storage-related test surfaces.

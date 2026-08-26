---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:0d436928a855e7be610379acee1a3339190d513f56bb3661b6e0c84dc571158f'
step_id: 'S06'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---
# Migrate config login to canonical machine-secret channels

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody.py`
- `src/cadrumo/entrypoints/cli/tests/test_machine_secret_login.py`

## Description

- Grounded the login transport boundary with semantic code and accepted-ADR discovery, then confirmed exact consumers and obsolete branches with `rg`.
- Promoted `_LoginSecrets` onto the canonical strict frozen `MachineSecretPayload` base and registered it against the closed `config.login/passphrase` inventory slot.
- Replaced command-local fd/stdin branching with `select_machine_secret_channel` and `read_machine_secret_payload`.
- Made the only channel-free route an explicit hardened no-echo prompt on a verified terminal; otherwise login refuses before application authentication.
- Removed CLI environment/settings/keyring/substrate fallthrough, the headless-channel predicate, direct reader imports, and the nullable callback branch while retaining programmatic substrate configuration outside this CLI entrypoint.
- Preserved selection-before-read, read-before-authentication, one-shot callback closure, target-locale refusal rendering, and secret-free errors.

## Outcome

`config login` now resolves its passphrase exclusively through one canonical explicit machine channel or a verified interactive prompt. A headless invocation with no channel cannot inherit a configured passphrase through the application or storage substrate, and the command-local payload model is discoverable through the authoritative inventory.

## Verification

- `uv run --no-sync ruff check src/cadrumo/entrypoints/cli/_config/_custody.py src/cadrumo/entrypoints/cli/tests/test_machine_secret_login.py`
- `uv run --no-sync ty check src/cadrumo/entrypoints/cli/_config/_custody.py src/cadrumo/entrypoints/cli/tests/test_machine_secret_login.py`
- `uv run --no-sync pytest -q -n 0 src/cadrumo/entrypoints/cli/tests/test_machine_secret_login.py` - 2 passed.
- `uv run --no-sync pytest -q -n 0 -m integration src/cadrumo/entrypoints/cli/tests/test_profile_login_session_lifecycle.py` - 3 passed through real subprocess stdin login.
- Import-time registry assertion for `config.login/passphrase` passed.

## Notes

Real inherited-descriptor subprocess coverage for all commands remains assigned to W03.P06.S13. This Step establishes that login delegates descriptor reading to the already tested canonical reader.

The plan serializer carried the concurrent S05 and S06 closures in one shared-file delta. Root authorized the S05 commit to land that mechanical plan hash and both checkboxes; the S06 scoped commit therefore intentionally excludes the already-landed plan file while this execution record supplies S06 attribution.

## S18 evidence reconciliation

The focused two-test result above is a historical S06 landing result. S17 later retired patched near-handler cases under the feature's no-monkeypatch proof rule; the current `test_machine_secret_login.py` intentionally retains only the strict payload-model contract. Current end-to-end transport authority is the S13/S14 fresh-process matrix: `test_login_succeeds_through_each_leaf_channel` exercises stdin and the platform descriptor route through the production entrypoint, while the refusal cases cover ambiguity, malformed input, hostile environment non-interference, cleanup, and non-disclosure. The separate `test_profile_login_session_lifecycle.py` statement above remains a real-subprocess lifecycle result. S06 completion therefore depends on the stronger S13/S14 evidence, not on the retired patched cases.

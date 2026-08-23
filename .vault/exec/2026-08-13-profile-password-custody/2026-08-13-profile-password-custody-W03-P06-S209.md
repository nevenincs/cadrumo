---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:07eae8882122658c43bd22be2839b5cdae151908937f4173d0727b0cf790b840'
step_id: 'S209'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Have Terra XHigh reproduce and resolve the WSL supervised-KDF inherited-PTY attestation refusal that prevents the full machine-secret CLI subprocess matrix from reaching dispatch, preserve strict worker isolation without bypasses or weaker fallback, and add a WSL runtime gate proving all five leaf descriptor channels, both restore variants, root authentication, and cross-scope collision semantics

## Scope

- `src/cadrumo/adapters/persistence/storage/custody KDF supervision and src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`

## Description

- Reproduce the current WSL failure with the complete machine-secret subprocess matrix and an isolated-venv direct invocation.
- Trace why the supervised KDF worker rejects WSL-inherited PTY descriptors during profile-fixture registration before CLI dispatch.
- Correct the platform attestation or test-host contract without disabling ready-handshake validation, weakening process isolation, or adding an in-process fallback.
- Add a WSL runtime gate that executes the settled full subprocess matrix through real CLI, application, custody, and descriptor boundaries.

## Outcome

Open carry-forward. The 2026-08-23 machine-secret S17 gate reproduced the failure sequentially and through a direct isolated WSL virtual environment: profile registration stops at supervised-KDF descriptor attestation before any machine-secret command reaches dispatch. The feature therefore records only 23 real POSIX reader cases and two real CLI descriptor-zero collision probes on Linux. This Step owns the stronger full-WSL runtime proof rather than allowing the machine-secret feature to narrow or silently discard it.

## Notes

The closure gate is `uv run --no-sync pytest -q -n 0 -m integration src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py` executed inside WSL with every settled case collected and passing, no runtime skip, no patched KDF or CLI boundary, and no weaker supervision fallback. The result must include all five leaf descriptor channels, both restore variants, root authentication, descriptor zero, dual-source certificate calls, cross-scope collisions, cleanup, and non-disclosure.

---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S52'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Reject duplicate keys in the secrets-stdin JSON payload before strict validation runs, because json.loads collapses them to the last value before extra forbid can observe the collision, allowing silent custody drift on the automation channel

## Scope

- `src/cadrumo/entrypoints/cli/_config/_secure_input.py`

## Description

- Add `_reject_duplicate_object_keys`, a `json.loads` `object_pairs_hook` that
  raises `ValueError` on a repeated object key, keyed off the field name only
  (never a payload value) so the refusal message cannot carry a secret.
- Install the hook on the single `json.loads` call in `read_secrets_stdin`; it
  fires for every object the decoder builds, including nested ones, so the
  collision can never resolve silently before the strict `extra="forbid"`
  pydantic model observes the mapping.
- Route the raised `ValueError` through the existing `except (ValueError,
  UnicodeDecodeError)` arm, reusing the current
  `cli.config.custody.errors.secrets_stdin_invalid_json` locale key; no new
  operator-facing copy was needed.
- Amend the module and function docstrings so the strict-parse claim is total
  as written.
- Add two real-CLI regression tests to `test_config_recovery_lifecycle.py`:
  one driving `config recovery verify --secrets-stdin` with a duplicated
  `recovery_code` key carrying two different values, asserting refusal and
  that the second (genuine) value was not silently accepted; and the oversize
  case for the neighbouring `P08.S55` step.

## Outcome

Duplicate JSON keys in a `--secrets-stdin` payload now refuse with the
existing invalid-JSON refusal instead of silently collapsing to the last
occurrence. Verified by driving the real CLI subprocess harness with a
payload carrying `recovery_code` twice — once with the wrong code, once with
the genuine enrolled mnemonic — and asserting the run refuses (exit 2) rather
than reporting a successful verification. `ruff check`, `ruff format --check`,
and `ty check` are clean on the touched module; `pytest --collect-only -q`
over `src/cadrumo` collects cleanly (13993 collected, 3246 deselected, zero
errors).

## Notes

None. No secret value is placed in any exception message; the duplicate-key
message names only the static field name.

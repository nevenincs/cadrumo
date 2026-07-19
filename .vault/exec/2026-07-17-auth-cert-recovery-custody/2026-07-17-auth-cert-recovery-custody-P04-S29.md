---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S29'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Prove passphrases, mnemonics, and secret-input values are absent from help and examples

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_help_without_secrets.py`

## Description

Verified against HEAD `8af409cd3f`, no re-implementation needed. The claim spans three test surfaces that together cover passphrases, mnemonics, and secret-input values across help and examples:

- `test_help_without_secrets.py` parametrizes every custody-adjacent subgroup help (`config recovery --help`, `config recovery create --help`, `config recovery verify --help`, `config recover --help`, `config passphrase --help`, plus the general `config`/`app`/`app ledger`/`app modelo` surfaces) and asserts exit 0 with real content while a `KEY=value`-shaped passphrase-leak regex never matches; a companion anti-tautology case (`test_data_verb_still_refuses_without_passphrase`) proves the introspection gate has not started skipping real verb execution.
- `test_root_grammar_invariants.py::test_recovery_verbs_reject_mnemonic_argv_options` proves no recovery verb accepts the mnemonic (or any secret) as an argv value, so no example in help text or usage error can surface one.
- `test_config_recovery_lifecycle.py` (P04.S28, already closed) proves recovery status/create/rotate/verify/recover carry no serialized mnemonic material.

## Outcome

Verified complete, zero production-code or test changes needed. `uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_help_without_secrets.py -q -m integration` → `12 passed`; `test_root_grammar_invariants.py` + `test_repair_policy_coverage.py` → `15 passed`.

## Notes

Bookkeeping-only closure: this record documents verification, not new implementation. `test_help_without_secrets.py` alone checks the narrower passphrase-value-leak claim; the mnemonic-absence claim is proven by the sibling `test_root_grammar_invariants.py` test named above — the step's evidence is distributed across the three files rather than concentrated in the one named in its scope annotation.

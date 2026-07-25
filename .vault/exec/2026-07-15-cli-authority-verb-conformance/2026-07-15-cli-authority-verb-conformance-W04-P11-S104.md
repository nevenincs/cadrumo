---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S104'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove reset start, status, resume, operation IDs, retention override, reasons, and confirmations across real processes

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_config_reset_lifecycle.py`

## Description

Prove reset `start`, `status`, and `resume` across real processes, covering operation
ids, the retention override, the audit reason, and the confirmation requirement.

## Outcome

`src/cadrumo/entrypoints/cli/tests/test_config_reset_lifecycle.py` carries two
integration cases:
`test_config_reset_group_has_exact_sessionless_bootstrap_ownership` (`:70`) pins the
group's bootstrap ownership, and
`test_config_reset_start_status_and_resume_exact_durable_journal` (`:80`) drives the
three leaves against a real durable journal, which is what makes the resume path
meaningful — resume rolls an existing journal forward rather than starting a new
operation.

The module is `integration`/`hex_entrypoint` marked and passed in the coordinator's
W04 gate run (`uv run --no-sync pytest <14 W04 files> -m "integration and not
os_keychain"` → `1 failed, 154 passed`), the single failure being the unrelated S112
control.

## Notes

Option-surface coverage (the `--operation-id`, `--override-retention`, `--reason`
pairing rules, and the `--yes` refusal) is carried at the registration level by S101
and at the destructive-confirmation gate by S119; this record covers the
across-real-processes lifecycle proof only.

These are `integration`-marked modules; the repository default `addopts` is
`-m 'unit and not external_tool and not os_keychain'`, so a bare `pytest <path>`
collects zero tests and exits green. The marker is required for the run to be a
verification.

`vaultspec-rag` is degraded (truncated code index reporting `degraded_reasons: []`);
all findings were confirmed with `rg` and direct file reads.

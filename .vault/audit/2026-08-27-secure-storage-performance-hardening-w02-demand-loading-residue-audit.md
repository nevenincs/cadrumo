---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:d494ee2321e16d01181e50a93bee9463798922e7cf2e4353cdab71e5da60332c'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
  - "[[2026-08-22-secure-storage-performance-hardening-adr]]"
---

# `secure-storage-performance-hardening` audit: W02 demand-loading residue

## Summary

The `W03.P08.S32` cold-process listing contract was the first gate to observe a
real CLI process end to end. On its first run it failed on three properties
`W02` had already marked complete, and chasing the last of them surfaced three
more defects. All six are fixed; this record exists because the checkbox and
the tree disagreed, which is the failure mode `aeat-agent-orchestration`
warns about -- delivered-as-specified and recorded-but-not-implemented wearing
the same mark.

None of this was caught earlier because no gate ran a whole command in a fresh
process and looked at what it imported and wrote. `test_lazy_command_tree`
guards one family (registry) on the help path; `test_cli_performance_budgets`
tests the calibration arithmetic, not any live node.

## Findings

### F1 - the registry loaded at bootstrap for every command

`src/cadrumo/entrypoints/cli/_common.py` imported
`domain.calculations.registry.authority` at module scope for ONE call site on a
filing-precondition refusal path. `_common` is loaded by the CLI bootstrap, so
every command -- including all 68 state-free nodes -- paid for the whole
calculation registry.

Observed: 138 registry modules at CLI import. After demand-loading: 0.

### F2 - the custody adapter dragged in the authenticated aggregate

`adapters/persistence/storage/_profile_custody.py` imported
`_profile_custody_carry` at module scope, reaching
`ledger.confirmation_record` -> `confirmation_gate` -> `evidence_draft` ->
`invoices` -> `workflow.state_models` -> `active_profile` ->
`profile_bucket_scan` -> `profile_repository`. Carry is needed only when carry
runs; it is now loaded at its two delegating methods.

### F3 - every leaf invocation materialized the whole storage tree

`_profile_authentication_gate.preflight_parsed_leaf` called
`ensure_storage_tree()` unconditionally. A read-only listing created `blobs`,
`financial`, `secrets`, `submissions` and the whole `cache` tree -- 25
directories -- while declaring `side_effects={none}`. Materialization is now
gated on the spec's own declaration, the same authority the census and write
routing read. This exempts 218 of 365 nodes.

Observed: 27 created paths, now 2.

### F4 - a payload monolith pulled a sibling command's services

`entrypoints/cli/_config_payloads.py` imports the application services every
config verb needs. The listing imported it for two row types and received
`application.config_reset` -> `user_profile.lifecycle` -> `custody_service`.
The two rows moved to `_config/_profile_list_payloads.py`, matching the
per-leaf payload convention already used by the censo, check and google leaves.
The monolith remains the home of every other config payload and is a candidate
for the same treatment per leaf.

### F5 - a second, heavier definition of "which profiles exist"

`application/workflow/profile_bucket_scan.py` produced a UUID-and-label
projection -- the same fact the summary inventory produces -- through the
authenticated aggregate, taking a per-profile custody lock and able to publish
a label head as a side effect of resolving a NAME. Two definitions of one fact
that could disagree. All four functions now read `summary_inventory`, so the
projection has one authority. Every consumer benefits: `config_reset`,
`login_interaction`, `status_projection`, `profile_health`, `_common`.

### F6 - the sandbox notice contradicted its own cheapness contract

`application/operator_output/_sandbox_notice.py` documents itself as "cheap
enough to call on every emitted line", then called
`CommittedProfileRepository().load()` -- custody lock, password material,
transaction journal, label-head verify-or-publish -- on every emitted line of
every command. It now reads the summary projection, and the docstring states
what it does.

## Carry-forward

- The diagnostic log root (`logs`, `logs/cadrumo.log`) is still created by any
  invocation, because `get_logger` runs at module import in 178 modules and
  `configure_logging` deliberately creates the directory eagerly so an
  unwritable root degrades to stderr instead of crashing startup. The listing
  contract names those two paths as an explicit exemption rather than relaxing
  to a prefix match, so a real regression still fails loudly. Making the file
  handler lazy (`delay=True`) would move that degradation check to first emit
  and is a deliberate decision for the logging owner, not a silent change here.
- `core/i18n/_render.py` binds `_log = get_logger(__name__)` at module scope
  and never uses it. Dead, but not load-bearing for the above.
- `W04.P09` and `W04.P10` file hints name
  `test_command_loading_contract.py`, which the `S54`/`S55` cutover replaced
  with `test_command_spec_universal_gates.py`. The Step intent survives; the
  paths need rewriting before those Steps are worked.

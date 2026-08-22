---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:c03b680ea0d4e13971cab6664c819a03a72256106d651059db7f6e82de21a7c4'
step_id: 'S04'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Add a universal census gate that fails for every unclassified node and prove the detector against an externally injected node

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_command_loading_contract.py`

## Description

- Enroll the complete live root, group, and leaf census in a dynamic policy gate
  with no frozen command count.
- Add a test-only, independently adjudicated callback-owner partition covering
  capabilities, effects, performance, write routing, destructive behavior,
  filing handoff, and live-write behavior for every current live node.
- Disambiguate only mechanically repeated callback owners by their live path so
  helper-generated future groups cannot collapse into an existing judgment.
- Prove the gates bite for an injected unclassified leaf, a future group created
  through the real metadata helper, and six real-node semantic downgrades across
  custody, network, Google, filing, browser, subprocess, state, and route axes.
- Prove Typer lazy materialization retains the original callback through its
  wrapper, retains the exact policy object, and caches the materialized callback.
- Attach policies to the previously omitted executable `aeat` and `aeat app`
  callbacks and correct the full-tree helper's vendored Click return type.
- Enforce physical deletion of the legacy risk table, write-verb catalogue, and
  path-keyed production policy authorities.
- Resolve both high-severity and the medium-severity independent review findings
  before closure.

## Outcome

Every current live CLI node is explicitly classified and exactly reconciled to
an independently reviewed semantic judgment. The gate grows from the runtime
tree, rejects missing and stale judgments, and proves the common helper-generated
group path cannot bypass future enrollment. Legacy keyed authorities remain
deleted rather than retained as compatibility data.

Scoped Ruff and `ty` checks passed. The universal contract passed 11 tests. The
combined capability, census, config, ledger, modelo, remaining-app, MCP, and
root-write policy suite passed 47 tests. The final independent review approved
with no critical, high, or medium findings.

## Notes

The first semantic oracle recognized only five owner-name signals; independent
review proved it missed downgrades on real profile and ledger commands. An exact
owner partition replaced it. A second review then found repeated metadata-group
callback qualnames collapsed distinct nodes; the final partition explicitly
disambiguates all repeated owners and a planted future group proves the detector
reds. No production compatibility shim or count assertion was introduced.

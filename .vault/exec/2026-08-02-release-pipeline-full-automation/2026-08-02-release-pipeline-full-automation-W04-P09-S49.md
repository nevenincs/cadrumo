---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:b153d6223b15c83c27371e0bcc710ea4bbfbed1ec6650b04753d78341bfe6ff2'
step_id: 'S49'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

# Add OP-10 and OP-11 to the runbook operator-actions section as named outstanding items, because the section is gated on naming exactly the outstanding halves and the toolchain precondition in particular is stated as unverified by the decision record itself and blocks the very first real dispatch at its very first stage, gate: uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q passes with the operator-actions assertions extended to cover the alerting channel and the toolchain precondition

## Scope

- `RELEASING.md`
- `src/cadrumo/tests/test_release_config.py`

## Description

- Add **OP-10** to RELEASING.md's `### Operator actions` section: names the
  default `release-alert`-labelled-issue alerting channel
  (`dev/release/alerting.py`), states it works with no configuration from the
  moment the chain lands, and names the `CADRUMO_ALERT_WEBHOOK` repository
  variable as the optional nomination that REPLACES (not supplements) the
  issue path once set.
- Add **OP-11**: names the toolchain precondition the version-bump stage's
  own `npx` shell-out depends on, states plainly that whether the
  self-hosted Linux fleet carries `node` is unverified by the decision
  record itself (not just by this repository), and that the first real
  dispatch refuses at its first stage naming this item if absent.
- Extend `test_releasing_doc_operator_actions_section_names_the_outstanding_halves`
  with matching assertions (`OP-10`, "alerting channel", "release-alert";
  `OP-11`, "node", "unverified") alongside the existing OP-9/OP-12/#618/OP-3
  ones, so the section's completeness is enforced going forward the same way
  the other four items already were.
- Inserted both entries between OP-9 and OP-12 to preserve numeric order.

## Outcome

Gate green: `uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q`
passes 9/9, with the operator-actions section now naming OP-9 through OP-12
plus the carried-forward #618 item and narrowed OP-3 — every operator
decision point the accepted ADR creates.

## Notes

Landed first and reported to the coordinator before `W04.P09.S43` (a
different agent, extending OP-10 with the read-only environment-inventory
label-presence check) touches the same `### Operator actions` section, per
the coordinator's explicit sequencing request — avoids two agents racing
edits to the same paragraph.

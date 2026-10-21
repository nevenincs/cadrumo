---
tags:
  - '#audit'
  - '#agent-harness'
date: '2026-10-21'
modified: '2026-10-21'
body_schema: 'body-v2'
body_hash: 'sha256:b4db9a3a198f41c0c8fd906b886743b3b35e82cb30e7616062b9f5d66dbdb20d'
related:
  - "[[2026-10-21-agent-harness-plan]]"
---

# `agent-harness` audit: `boundary review`

## Scope

Integrated review of `2026-10-21-agent-harness-plan` Steps S02 to S07: commits `ea1dc6f9c9`, `cd2b853e84`, `efb980bf53`, `2c798517b3`, `6e1168d693`, `662548eceb` and `6880c47d58`, plus the identity ADR correction `b4182dfc8d` and the locale commits `1a4f75bdc6` and `3ee542eb96`. Two passes were made, an initial review of S02 to S05 and a delta review of S06, S07 and the ADR. The review was checked against the amended `2026-07-02-agent-harness-refoundation-adr` and the rules `00-architecture` and `02-runtime-tui-and-agent-harness`.

## Findings

### eval-coverage | high | S04 left two runner checks uncalled and removed the only test of a live helper

`check_contradiction_scenario` and `check_profile_confirmation_scenario` in `dev/mcp_eval/_runner.py` lost their only caller when the live scorer was deleted. `lifecycle_stages_in_canonical_order` in `dev/mcp_eval/_models.py` stayed in use but lost its test. Resolved in `662548eceb`: the two checks and their models were deleted, and `dev/mcp_eval/tests/test_lifecycle_stage_order.py` was added.

### protective-gate | high | the S06 gate failed on HEAD after S07 named a retired tool in a test

`dev/quality/tests/test_no_authored_agent_content.py` scanned test modules and flagged the `harness_load` literal in `src/cadrumo_mcp/mcp/tests/test_installed_stdio.py`. Resolved in `6880c47d58`: the serving scan now uses `dev.first_party_source.is_production_source`, and a fixture proves a planted channel in a production module is still reported.

### gate-coverage | medium | the gate did not reject a reintroduced cadrumo_harness package

Resolved in `6880c47d58`. `retired_package_findings` walks `src/` and is proven by a planted `cadrumo_harness/mcp` fixture.

### boundary-docs | medium | technical docs described skill serving and cited deleted paths

Resolved in `662548eceb`. The topic and architecture pages were restated to the MCP-only scope. Articles 186 and 187 were deleted together with their catalogue, toctree and manifest entries. The es, ca and hu catalogues were retranslated in `1a4f75bdc6`.

### native-contract | medium | the native contract advertised retired SKILLS_DIR and RULES_DIR variables

Resolved. The variables were dropped from `native/application-environment.toml` in `662548eceb` and from `native/CONTRACT.md` in `196a50b322`.

### identity-read | medium | the identity ADR named a nonexistent whoami tool

Resolved in `b4182dfc8d`. `2026-07-08-mcp-identity-linked-operation-adr` now names `status` as the identity read: `src/cadrumo_mcp/mcp/protocol_contract.py:189`, gated at `src/cadrumo_mcp/mcp/runtime_adapter.py:431`.

### packaging-comment | medium | the pyproject comment still described harness operating data

Resolved in `662548eceb`.

### gate-proof | medium | no test asserted that harness_load is an unknown tool

Resolved in `662548eceb`. `harness_load` was added to `_REMOVED_TOOLS` in `src/cadrumo_mcp/mcp/tests/test_installed_stdio.py`.

### import-lanes | low | mcp_eval took agent_eval's lane position in .importlinter

Resolved in `662548eceb`. `mcp_eval` now sits between `locales` and `operation_contract_manifest`.

### stale-docstrings | low | two mcp_eval docstrings promised skill documents

Resolved in `662548eceb`.

### gate-scope | low | the serving scan reads Python sources only

Recorded in the gate's module docstring in `6880c47d58`. Native sources are not a shipped root, so the scan does not touch the desktop relay of cadrumo-agent's own skills endpoint.

## Recommendations

The serving scan does not cover native sources (finding `gate-scope`). Whether those need a gate of their own is a follow-on question; nothing reachable today serves Cadrumo-authored content from native code.

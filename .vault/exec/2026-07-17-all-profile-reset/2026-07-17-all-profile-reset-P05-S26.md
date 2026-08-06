---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:8cca6004f6caf109c9f6e518a161cf7209600e250b7fd96995dec7cc71c8d3b6'
step_id: 'S26'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Migrate the reset payload schemas and write-policy tokens to the accepted reset grammar

## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`

## Description

- Add `ConfigResetTargetPayload`, `ConfigResetSummaryPayload`, `ConfigResetOperationPayload` (with `from_operation` projecting the real `ConfigResetOperation`) to `_config_payloads.py`.
- Register `config.reset.start` / `config.reset.status` / `config.reset.resume` schemas (`ConfigResetStartResult`, `ConfigResetStatusResult`, `ConfigResetResumeResult`) via `@register_schema(...)`, replacing the retired flat `ConfigResetResult`.
- Confirm the runtime write-policy allowlist (`storage_write_policy.py`) still guards the reset family under its active-profile-session gate.

## Outcome

Verified against HEAD (`8af409cd3f`), not re-implemented; the payload schemas were landed by commit `38eba09021` (`git log -S'class ConfigResetOperationPayload' -- src/cadrumo/entrypoints/cli/_config_payloads.py` shows exactly that one commit). Read `_config_payloads.py`: `ConfigResetTargetPayload`/`ConfigResetSummaryPayload`/`ConfigResetOperationPayload` at lines 478-551, and `config.reset.start`/`config.reset.status`/`config.reset.resume` registered at lines 554-572 — no leftover flat `config.reset` schema.
`PROFILE_BOUND_WRITE_VERB_PATHS` in `storage_write_policy.py:188` carries the single prefix token `"config reset"`; `inspect_storage_write_policy` matches this catalog **by prefix** (per its own docstring: "matches this catalog by prefix after the CLI root reconstructs the Typer verb path"), so `"config reset"` already covers `config reset start`, `config reset status`, and `config reset resume` without a per-subverb token — no drift to sweep here, confirmed by reading the matching function's docstring and the catalog comment directly rather than assuming.

## Notes

No incidents. The write-policy token predates this campaign (`git log -S'"config reset"' -- storage_write_policy.py` traces to the earlier package-root-rename commit `8d4cd1efce`), and happens to already be correct for the new subverb grammar by virtue of prefix matching — it did not need a hand-sweep for this step, contrary to what a token-rename would normally require per `aeat-cli-pull-and-file-standard`.

---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:e52d188780002cc984ff80ad6f9ac4de54b5ccc3f56a841952a3c11a50870264'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# `cli-action-envelope-hardening` audit: `S94 independent closure review`

## Scope

Independent closure review of S94's LLM optional-extra consumers and local-vision admission proof. The review covered current absent-extra integrity, exported-guard inventory coverage, the actual local runtime transport, test-double prohibitions, removed recovery DTO and installation-hint forwarding, and static analysis of the owned paths.

## Findings

### s94-target-contract | low | The current LLM boundary preserves machine identity without consumer recovery prose

Every current exported `require_optional_extra(LLM_EXTRA)` guard is derived from source and driven in an installed core-only product cohort. The Anthropic client and provider-loader boundaries preserve the same registered extra facts. The local-vision override uses a catalogued model and injected hardware measurement only; production admission still reads the measured resident set from `GET /api/ps` before the real loopback `POST /api/chat` call. The reviewed files contain no import finder, `find_spec`, `sys.modules`, fake, mock, stub, patch, monkeypatch, skip, xfail, removed DTO, install-hint forwarding, or raw recovery wrapper.

### s94-terminal-projection-boundary | medium | The canonical optional-extra base error still owns English feature and install text outside S94

`MissingOptionalExtraError` continues to construct its message from `OptionalExtra.feature` and `install_hint` in `src/cadrumo/core/_optional_extras.py`. S94 does not rewrap or serialize that prose, and the installed-core proof validates its identity only. The pending terminal/core projection owner must make the actual operator envelope locale-neutral.

### s94-campaign-closure-dependency | medium | The global rehoming validation remains red outside the S94 target family

The fresh direct rehoming validation did not report the S94 `LLMContentionError` family, but it remains red for S38 and separate Modelo and ledger-storage families. That is not a defect in this reviewed LLM slice, yet the campaign must retain the global fixed-point prerequisite before claiming complete action-envelope closure.

## Recommendations

Keep S94 open as directed until the terminal/core projection owner removes the raw optional-extra presentation path and the campaign-level rehoming fixed point and subsequent independent closure pass are recorded. Do not replace the installed-product cohorts with import interception or a simulated transport; retain the source-derived guard inventory and the real `/api/ps` assertion when expanding the LLM surface.

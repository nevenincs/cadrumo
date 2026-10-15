---
tags:
  - '#audit'
  - '#startup-service-repair'
date: '2026-10-14'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:830b126ddf8e803fa8afc4ac0e64a53abe0eb399880073d505a97dccd1709d4b'
related:
  - "[[2026-10-14-startup-service-repair-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace startup-service-repair with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

# `startup-service-repair` audit: startup diagnosis and supervision

## Scope

Integrated review of the uncommitted startup-service-repair implementation against the accepted canonical environment and desktop shell decisions. Reviewed diagnostic forwarding and containment, worker exchange fencing, KDF cleanup, shared status observations, retry supervision, and user retry integration. Other concurrent work is outside this repair except where it interacts with these workflows.

<!-- What was audited and why -->

## Findings

### retry-budget | medium | Observation failures must preserve exhausted retries

Initial review found that transient runtime/status failures reset the retry budget in `native/desktop/src-tauri/src/agent/supervisor.rs`. This could restart endless automatic launches for the same broken service. Corrected to preserve the budget and original refusal through transient failures; only verified sign-out, profile changes, and explicit retry reset it. A regression covers exhaustion followed by read failure and runtime unavailability. Updated native verification remains pending.

### live-timeouts | low | Historical timeout attribution remains incomplete

The first 10-second worker exchange and the 30.783-second KDF cleanup cannot be assigned a precise internal cause from the historical logs. Request/action fields and cleanup process/pipe/directory spans now survive diagnostic filtering. Worker cascades and unbounded queue waits are repaired, but original live causes require packaged reproduction.

### verification | low | Package acceptance remains pending

Review verdict PENDING. Reused passing focused Python diagnostics, lifecycle, transport and KDF checks; 52 native sign-in tests; nine earlier supervisor tests; frontend check; and browser refusal/retry scenario. Registry gate and diagnostic privacy regressions pass. Root owns remaining shared checks, refreshed supervisor verification, and rebuilt package acceptance. No critical or high code findings identified.

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### {topic} | {level} | {summary}

     followed by a paragraph carrying the detail. {topic} is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### final-native-review | low | Native corrections verified

Follow-up review found no defects in the preserved retry budget or nonzero helper outcome. All 10 supervisor tests pass, including pending-read responsiveness and exhaustion across observation failures. The real nonzero-exit regression passes and retains the typed refusal envelope. Frontend checks pass after the contract change. Three initial supervisor failures were obsolete expectations for the intentional `agent_root_unmarked` mapping; corrected fixtures pass without timeout changes.

### repository-gate | low | Unrelated registry collection error prevents full-suite success

The configured `just test-gate` found a collection failure at `dev/registry/tests/test_record_design_source_selection.py:111`: one expected exercise unpacked multiple values. The run was stopped after establishing this failure to release resources for package acceptance. It is not passing evidence. `just check-registry-gate` passes. Package and remaining code-quality verification are still pending.

### service-start-reply | medium | Asynchronous startup acknowledgement was rejected as unreadable

Direct inspection found `AgentService.admin("start")` returns `kind=starting` while `native/desktop/src-tauri/src/agent/supervisor.rs:262` expected an immediate lifecycle `event`. Corrected the caller to accept the administration acknowledgement and leave readiness/refusal to the existing service event stream. The rebuilt package's manual admin start acknowledged in 0.001 seconds and subsequently emitted the agent refusal, independently of a GUI.

### startup-refusal-cause | medium | Typed startup causes were lost at the service boundary

`src/cadrumo_agent_service/main.py` and `service.py` reduced preflight exceptions to generic failure and discarded the inner agent refusal detail. Corrected both paths to use the existing launcher categories and log the agent's validated refusal code without serializing exception payloads. Six focused regression cases pass. In the rebuilt package, `build/acceptance/agent-manual-fecjpz6t/storage/logs/cadrumo.log:31` now states `hosted_lane_unproven`, including on asynchronous retry at line 33. Runtime readiness, password-authenticated CLI holder, exact service admission, twelve-provider catalog/status, protected credential set/remove/reset with CAS, and contained close all completed without a GUI.

### cli-auth-homes | medium | Ordinary CLI sign-in is not hosted provider sign-in

Two user-requested Luna max investigations traced the service and agent separately. A packaged-interpreter composer probe confirms custom `CODEX_HOME` and `CADRUMO_AGENT_CODEX_HOME` are absent, while OS home variables remain. The agent seats hosted Codex at `providers/codex`, then creates a fresh per-turn home and copies only that provider home's `auth.json`; a synthetic production-helper probe confirmed present/absent source behavior. Hosted Claude uses a persistent per-provider `CLAUDE_CONFIG_DIR`, with no automatic import from the user's home. The real Codex CLI reports login status exit 0 in the selected account, but exit 1 with no auth file in the manual hosted provider home. Provider settings' sign-in mode is not credential provisioning. No credentials were imported as a workaround. Hosted authentication provisioning and recorded hosted-package proof remain separate requirements; no working hosted conversation is claimed.

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->

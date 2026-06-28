---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
---

# `cli-workflow-redesign` research: `profile-owned output language`

This research examines the current output-language path and the gap exposed by CLI workflow execution: active CLI copy defaults to settings/environment, while the operator profile and first-run wizard do not own a persisted language preference.

## Findings

The current language resolver is settings-only. `core.i18n._render.output_language()` reads `load_settings().aeat_output_language` and defaults to `es` on failure. The settings field is `aeat_output_language`, with environment override `AEAT_OUTPUT_LANGUAGE`. This makes environment variables a valid explicit override, but not a profile-owned user preference.

The CLI imports `tr()` through `entrypoints.cli._i18n`, so command help and command output resolve language before command execution. This means a profile-backed language preference must be readable without requiring a command handler to run first. The resolver cannot depend on a CLI command callback having already loaded profile state.

The profile key registry is descriptor-backed. `domain.profile.PROFILE_KEYS` is compiled from `application.wizard._catalogue.WIZARD_FLOWS`; `config profile list/get/set/unset/status` already route through `workflow_state_repository()`. Adding a profile language field belongs in the wizard descriptor and profile-key registry, not in a CLI-local list.

`config init` is descriptor-driven. The dynamic command parameters are generated from wizard questions in `application.wizard._commands`. Adding an output-language question to the descriptor automatically exposes a first-run flag and allows the same persisted key to be set through `config profile set`, provided validation is represented in the wizard question.

Profile persistence is bucket-scoped through workflow state. `persist_answers()` serializes descriptor answers to profile-key values and writes through `set_profile_values()`. Existing profile CLI commands already read and write the active profile record through `workflow_state_repository()`.

There is no profile language key today. Search results show `AEAT_OUTPUT_LANGUAGE` usage in settings, error/i18n tests, and CLI tests, but no profile key such as `output.language`, `profile.language`, or `ui.language`.

Supported locale files are currently `en`, `es`, `ca`, and `hu`. The settings resolver accepts any string, so backend validation should explicitly constrain profile language to the shipped locale set unless a central locale catalogue already exists.

The desired precedence is clear from user workflow requirements: an explicit environment override remains valid, while the active profile language becomes the normal persisted user preference. Therefore the runtime resolver should use this order: explicit environment/settings override, active profile language, settings default.

Because help text resolves before command handlers run, the active profile language lookup must be low-level, read-only, and fail-soft. It must not emit bucket events, mutate state, require a configured profile, or leak tracebacks during help rendering.

The implementation must avoid CLI business logic. Language validation and persistence belong in the wizard/profile backend. CLI commands only expose descriptor-generated `config init --output-language` and ordinary `config profile set output.language LANG` behavior through existing backend services.

Tests should assert observable behavior, not development metadata. Appropriate coverage includes: profile-key registry includes `output.language`; `config init --output-language en` persists the active profile value; `config profile set output.language ca` updates the value; i18n resolver uses active profile language when no explicit environment override is set; `AEAT_OUTPUT_LANGUAGE` still wins when present; unsupported language values are rejected through the same wizard/profile validation path.

---
tags:
  - '#audit'
  - '#profile-output-language'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - '[[2026-05-13-cli-workflow-redesign-profile-output-language-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
---

# `profile-output-language` Code Review

W60-001 | HIGH | Profile output language is not read by the resolver
`core.i18n.output_language()` still resolves only `load_settings().aeat_output_language`, so an active profile value stored at `output.language` is ignored. The focused test `test_output_language_reads_active_profile_without_emitting_bucket_events` fails with `assert 'es' == 'ca'`. `core.errors.resolve_output_language()` carries the same settings-only duplicate branch and is not routed through the canonical i18n resolver.

W60-002 | HIGH | The descriptor-backed profile key is not implemented
The setup wizard profile section does not contain an `output-language` question bound to `output.language`, and `SetupAnswers` has no `output_language` field. Because profile keys are compiled from the wizard descriptor, `PROFILE_KEYS` cannot include `output.language`, `aeat config init --output-language` cannot be generated, and `aeat config profile set output.language ...` cannot validate through the descriptor/profile backend.

W60-003 | MEDIUM | Profile mutations do not emit bucket events
`set_profile_values()` and `clear_profile_values()` update profile state and timestamps only. They never append a `WorkflowEvent`, while the accepted ADR says language mutations are normal profile mutations and emit the normal bucket-scoped profile event path. The scoped profile action tests also do not assert event emission.

W60-004 | MEDIUM | W60 verification is marked complete despite failing or missing tests
The W60 plan rows for profile-language behavior and targeted test execution are marked complete, but the focused i18n test fails and the broader scoped test slice cannot collect because `WizardUnsupportedConsoleError` has no declared error-code registry entry.

W60-005 | LOW | Scoped tests still carry development metadata
`test_workflow_surface.py` contains a `Pre-W4` docstring reference and a `developer_commands` test name. The ADR requires help/output assertions to avoid ADR filenames, wave ids, phase ids, plan row ids, and other development metadata.

W60-REREVIEW-001 | INFO | Re-review passed after reapply
Current W60 re-review found no blocking findings in the scoped implementation. The resolver now reads `AEAT_OUTPUT_LANGUAGE`, active profile `output.language`, then settings default; `output.language` is descriptor-backed; profile mutations append bucket events; scoped W60 tests do not hardcode ADR/wave/phase metadata; and `WizardUnsupportedConsoleError` has a declared error-code row. Verified with the focused W60 pytest slices.

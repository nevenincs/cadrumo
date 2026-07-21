---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S36'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Confirm the two-tier enrollment gate refuses a plain executable fence on an enrolled page while non-enrolled pages keep the verb-path and option-name checks

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`

## Description

- Verify the two-tier enrollment behaviour landed by `W03.P07.S24` is complete and gate-proven end to end against the live CLI tree.
- Identify the one uncovered clause of the S36 contract: `S24` proved each tier in isolation (`test_enrolled_page_refuses_plain_executable_fence` for the enrolled refusal; the base `test_documented_commands_conform` and `test_live_introspection_matches_reality` for the verb-path/option-name checks), but no single focused test pinned the tier *boundary* — the coexistence the step names.
- Add `test_two_tier_enrollment_gate_coexists` to `test_documented_command_conformance.py`: a real end-to-end gate proving both tiers coexist across the enrollment boundary — a non-enrolled page is never subject to the plain-fence refusal yet its base verb-path/option-name checks still flag a wrong option, and an enrolled page's plain fence is refused while its directive frame lines still receive the base checks (refusal orthogonal to, never replacing, base validation).
- Add the `_NON_ENROLLED_BAD_OPTION_FIXTURE` (a non-enrolled page whose plain fence cites `--bogus-option`) so tier-two preservation is asserted against a genuinely-wrong command, not only a clean one.

## Outcome

- The full conformance module is green: 58 tests pass under `-m integration` (was 57), collect-only clean; ruff and ty clean.
- The coexistence test is a genuine gate, not evidence-only: it fails loudly if a future change displaces the base checks for non-enrolled pages or leaks the enrolled refusal onto a non-enrolled page. It asserts on a live-introspected violation string (`--bogus-option` flagged by `_validate_command`), so it cannot pass vacuously.
- The two-tier enrollment contract (ADR D7) is now pinned end to end: enrolled pages refuse plain executable fences; non-enrolled pages keep exactly today's verb-path and option-name checks.

## Notes

- Extended the S24 conformance module additively; no existing test weakened. `git diff` on the file before editing showed no non-authored WIP.
- `S37` (full docs gate suite green) is intentionally left unchecked: it is owned by a separate baseline sweep and completes after the W05 content wave lands.
- The shipped-enrolled-page live scan (`test_shipped_enrolled_pages_have_no_plain_executable_fences`) remains vacuous-but-not-skipped until the W05 tutorials land; it is not in this step's scope.

---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S53'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---

# dispatch Sonnet grounding pass against calendar to applicability join to confirm unification holds

## Scope

- `src/aeat/application/overview/`

## Description

- Ground the calendar and work-create flows with semantic retrieval and exact source inspection.
- Trace Modelo 100 applicability from the schedule-only taxpayer projection through the registry rule.
- Trace the universal filing-baseline gate through CLI work creation and work lifecycle validation.
- Compare the gate with repeatable activity-schema validation and wizard visibility rules.
- Identify the profile-status path that independently reports the same incorrect filing blockage.

## Outcome

The calendar and work-create paths share Modelo 100 applicability correctly, but unification breaks after that decision. A resident natural person with no economic activity is legitimately Modelo 100-applicable. Calendar projection pads an absent `activities.description` only for schedule diagnostics, while the later universal filing baseline requires that same value and refuses work creation before revision readiness.

This is a MAJOR continuity defect: a lawful pensioner/landlord has no permissible activity to enter yet cannot create the only applicable return. The activities section is repeatable, the schema validator does not require it when absent, and the wizard exposes it only for economic activity. Profile status repeats the erroneous global filing-blocked result. W02.P67.S418 was added to repair the target-aware boundary and prove the real CLI journey while retaining Modelo 130 and 303 applicability refusals.

## Notes

Relevant surfaces are `src/aeat/application/modelo/_profile_readiness_gate.py`, `src/aeat/entrypoints/cli/_modelo_work_lifecycle_cli.py`, `src/aeat/application/modelo/_work_lifecycle.py`, `src/aeat/entrypoints/cli/_config/__init__.py`, `src/aeat/domain/deadlines/_profiles.py`, and `src/aeat/application/user_profile/_projections.py`. Existing `test_config_profile_preflight_scope.py` encodes the invalid refusal and must be replaced by real target-aware coverage.

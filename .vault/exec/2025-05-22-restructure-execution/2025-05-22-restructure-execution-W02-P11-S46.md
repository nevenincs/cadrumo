---
tags:
  - "#exec"
  - "#restructure-execution"
step_id: S46
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-19-profile-lifecycle-disaster-plan]]"
---

# restructure-execution W02.P11.S46 — calendar/explain consistency regression test

## Outcome

Five-test regression suite landing in
`src/aeat/application/overview/test_calendar_applicability_consistency.py`
pinning that `build_overview_calendar` and `build_overview_explain` return
identical `ApplicabilityVerdict` for every modelo across the four core
persona profiles (autónomo, sociedad limitada, landlord, attribution entity).

## Commits

- `acea52801` — S43+S44+S46 batch: authority docs, `_gating_fields()`, `SuppressedCalendarEntry`, consistency tests
- `e01a9147c` — S45: `--show-suppressed` CLI flag on `aeat app overview calendar`

## Tests passing

```
test_calendar_and_explain_agree_on_applicability_verdict[autonomo] PASSED
test_calendar_and_explain_agree_on_applicability_verdict[sociedad_limitada] PASSED
test_calendar_and_explain_agree_on_applicability_verdict[landlord] PASSED
test_calendar_and_explain_agree_on_applicability_verdict[attribution_entity] PASSED
test_derive_modelo_applicability_is_the_shared_implementation PASSED
```

## Structural pins enforced

- Calendar path and explain path call the same `derive_modelo_applicability` object (identity-equal).
- `SuppressedCalendarEntry` captures verdict + truncated reason for every
  non-applicable obligation when `show_suppressed=True`.
- `--show-suppressed` CLI flag renders suppressed entries as tab-separated
  lines alongside the normal calendar output.

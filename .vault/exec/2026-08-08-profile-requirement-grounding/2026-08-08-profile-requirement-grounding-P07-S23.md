---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:76b784499d1cf69f6f81d89df707d92f1c58ec58288526fa20ed2fc7eb0c1a98'
step_id: 'S23'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Fix the no-op foral guard: tax_residence.ccaa being absent silently skips the parse_tax_region check instead of refusing, per the per-operation-axis audit's finding three

## Scope

- `src/cadrumo/application/modelo/_work_create_policy.py`

## Description

- Re-read the governing audit before acting, per this project's mandate to recompute a finding's conclusion at report time. The audit document itself records that this exact finding was investigated and **withdrawn** after this Step was opened, under the heading "Withdrawn: the CCAA foral finding does not survive verification either".
- Independently re-verified the withdrawal against current `HEAD` rather than trusting the audit's prose: read `guard_active_profile_foral_ccaa` in `_work_create_policy.py:171-187`. Its body is `raw_ccaa = fact_value(record, "tax_residence.ccaa"); if raw_ccaa: parse_tax_region(raw_ccaa)`. For a DECLARED value this calls the real domain parser, which raises `ForalRegimeError` for `pais_vasco`/`navarra` (case-insensitively) and passes through common-regime CCAAs - a declared foral filer is genuinely refused at work-create, contradicting the plan Step's premise that the guard is "a no-op".
- Confirmed the estatal-fallback claim is also not a silent defect: the calculation-side CCAA-to-estatal fallback the audit's ORIGINAL finding characterised as an unintentional silent default is a documented, deliberate decision (cited by the audit at `_profile_binding.py:505-511`, naming the 0511/0512 mínimo-del-contribuyente precedent and explicitly stating the named CCAA's parameters are "a named follow-up, not silently assumed to mirror estatal forever").
- What DOES survive, per the audit's narrowed residual claim: an UNDECLARED `tax_residence.ccaa` (the field is genuinely optional, absent from `_FILING_BASELINE_PROFILE_PATHS`, and not conditionally required by `_completeness.py`) receives estatal parameters with no advisory. This is not a separate defect - it is the SAME optional-field-without-a-conditional-requirement-grammar gap the audit's first finding already names as needing a `required_when` grammar on `ProfileFieldDefinition` (mirroring `ProfileKey`'s existing `required_when`), which is explicitly scoped in that finding's remediation as its own decision, not folded into this Step.

## Outcome

No code change in this Step. The plan Step's premise ("no-op foral guard") is falsified: the guard correctly raises for a declared foral CCAA. The narrower residual gap (undeclared CCAA, no advisory) is recorded as belonging to the conditional-requirement-grammar follow-up the first audit finding already tracks, not actioned separately here, to avoid two Steps converging on the same eventual fix from different angles.

## Verification

Direct inspection of `src/cadrumo/application/modelo/_work_create_policy.py:171-187` (current tree) confirms the guard body matches the audit's re-verification exactly: a declared, non-empty `raw_ccaa` is always parsed through `parse_tax_region`, which is the real domain function, not a stub. No test changes were needed since no code changed; the existing behavior this Step confirms is already covered by the domain-level `parse_tax_region` test suite.

## Notes

This is the clearest instance in this campaign of the project's own "a right conclusion can outlive its reason" and "measured claims survive, reasoned claims do not" lessons: the plan Step's action text was written from the audit's FIRST pass (a code read producing a plausible mechanism), and the audit's OWN second pass - driving `parse_tax_region` directly with real inputs - retracted it before this Step ever executed. Acting on the stale plan-step wording without re-reading the audit's current state would have produced either a no-op "fix" to code that already worked, or worse, an unnecessary behavioural change to a guard that was already correct.

---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:e988927a7cbeeae6497cb2b408834adb71e35c5d2ac90da41160e50bfd210653'
step_id: 'S31'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# DEFERRED as out of scope for the window-order work, decide whether the effective-dating projections should honour valid_to so an expired window stops projecting, the site recording the gap in place

## Scope

- `src/cadrumo/application/user_profile/_projections.py`

## Description

- Establish what would have to change, finding three resolvers sharing one rule rather than a single projection to amend.
- Establish what expiry would be measured against, finding no caller supplies an instant and the only one available is the clock.
- Decide against honouring `valid_to` on an implicit today, and record the reason at the ordering helper rather than as a note about a gap.
- Establish that the field is nonetheless writable, the lifecycle upsert accepting it from its command.
- Close the resulting silent no-op by reporting an end date that ends nothing at the profile validation surface.
- Scope the report to the effective fact, so an end date a later window supersedes stays unreported.
- Select that fact through the projection's own ordering rather than a second copy of the rule.
- Pin the two halves together, that the value keeps resolving and that the surface says so.

## Outcome

Decided: the projections do NOT honour `valid_to`, and the decision is now recorded as a ruling with its reason rather than as an acknowledged gap.

Two findings drove it. The first is that this is not one site. `_in_window_order` in the projections, `fact_value` in the orchestration, and the output-language resolver in the repository all sort on `valid_from` with absent windows first and take the last, so honouring expiry in the projections alone would create exactly the disagreement between readers that the ordering work existed to end.

The second is decisive and is about what expiry means. Expiry is only defined against an instant, and no caller supplies one; the only instant available inside these functions is the clock. A projection that dropped expired facts against today would return different values for the same record on different days, and these projections feed filing inputs and completeness checks whose effective instant is the PERIOD being filed rather than the day the command runs. An implicit-today rule would resolve a 2024 filing against 2026's calendar and would do so silently. Dropping a path also reads downstream as unset rather than as ended, so a required field whose window closed would surface to the operator as missing.

So honouring expiry means threading an explicit `as_of` through every caller, each deciding the instant its own read is effective at. That is a larger and different change, and the ruling says so at the site.

The consequence implemented is the one the ruling leaves behind. `valid_to` is accepted by the lifecycle upsert, so an operator can record an end date that changes nothing at all. `ProfileValidationService` now emits a WARNING, `effective_window_end_not_enforced`, naming the declared date and the action that does work — recording a later `valid_from` at the same path. The report is scoped to the fact the resolvers actually select, so an end date that a later window supersedes is correct bookkeeping and stays silent, and it selects that fact by reusing `_in_window_order` rather than restating the rule.

Six cases in `src/cadrumo/application/user_profile/tests/test_effective_window_end_is_reported_not_enforced.py` pin the behaviour and the report together, including that a closed window still projects its value, that a superseded end date is not reported, and that a fact with no end date is not reported.

`uv run --no-sync pytest` over the new cases and the projections suite reported `22 passed in 9.96s`. The wider `src/cadrumo/application/user_profile` and `src/cadrumo/domain/user_profile` suites reported `367 passed in 51.74s`. `ruff check` reported `All checks passed!`, `ruff format --check` reported `5 files already formatted`, and `ty check` reported `All checks passed!`.

## Notes

The row asked whether an expired window should stop projecting and the honest answer is that the question is underspecified as posed. "Expired" needs a date, and the reason this looked like a small gap is that the missing date is invisible while nothing sets a window. Answering yes without supplying it would have introduced clock-dependence into filing-input projections, which is a worse failure than the one being fixed and would have been invisible in every test that runs on a single day.

The warning is deliberately not an error. A recorded end date is not malformed and the profile is not invalid; the operator has described something the system does not implement, which is a thing to tell them rather than to refuse.

The report reuses the projection's private ordering helper from a sibling module in the same package. That is intentional: a fourth copy of the selection rule could drift from the three that exist, and this check is only meaningful while it names exactly the fact the readers resolve to.

Not verified: nothing here establishes that any shipped surface renders this warning to an operator. The issue reaches the validation report, and the surfaces that display validation issues were not exercised. A run confirming an operator actually sees it is outstanding.

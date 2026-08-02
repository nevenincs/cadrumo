---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:b9fa4735577827973e951a10d01b846314456b054a5029acc1c4e13f28713916'
step_id: 'S19'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Carry the hotfix carve-out onto the candidate record as a shortened window admissible only when the record names an incident reference and a release-owner approval, preserving the readiness gate terms verbatim rather than weakening them while the wait moves from a human to the pipeline, gate: uv run --no-sync pytest dev/release/tests/test_soak_promoter.py -q passes covering a shortened window accepted with an incident reference present and refused when it is absent

## Scope

- `dev/release/release_candidate.py`
- `dev/release/soak_promoter.py`
- `dev/release/tests/test_soak_promoter.py`

## Description

- Add `soak_hours_override`, `incident_reference`, and `release_owner_approval` to the candidate record, plus a `hotfix` property.
- Add a model validator refusing a shortened window that lacks either authorisation, so an unauthorised shortening cannot exist as a loadable candidate.
- Refuse at seal time an override that does not actually shorten the declared minimum.
- Add five tests: the authorised shortening, each missing authorisation separately, the non-shortening override, and a hotfix still facing the full readiness gate.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_soak_promoter.py dev/release/tests/test_release_candidate.py -q` reports 33 passed. Lint, format and `ty check` clean over my files.

The policy's three conditions are now split across the two places that can actually enforce them: the incident record and the release-owner approval are properties of the record and are enforced at construction, while "every applicable gate green before publication" is the readiness re-check already enforced at promotion time. A hotfix therefore shortens the CLOCK and weakens no gate, which is asserted directly rather than assumed.

## Notes

The finding worth recording is a test that silently changed meaning under me, and it is the reason to re-read neighbouring tests when extending a model rather than only running them.

`test_a_record_carrying_an_unknown_field_refuses_to_load` planted `soak_hours_override` as its unknown key, chosen in S14 precisely because no field claimed it. S19 made it a REAL field. The test still passed - so a green suite would have told me nothing - but it now passed through the hotfix validator rejecting an unauthorised override rather than through `extra="forbid"` rejecting an unknown key. The assertion had quietly stopped testing the property it was written for, while looking untouched. The planted key is now one no field can ever claim, with a comment recording why.

Two refusals are deliberately separate rather than one combined check. A candidate carrying an incident number but no approval is exactly the shape an automated emergency path would produce by accident, so each authorisation is asserted on its own; a single "both present" assertion would pass while one half was never actually reachable.

The override must strictly shorten. An override at or above the declared minimum is either a no-op wearing an incident number or a way to EXTEND the window through the emergency path, and the policy permits neither - the carve-out exists to shorten an emergency window, not to serve as a general dial over the soak duration.

---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:6e421e4af706289d0084f39f76d68d038805fd02078d38eec68954722b52de83'
step_id: 'S41'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Reduce the release module family to what the adopted path invokes

## Scope

- `dev/release/environment_inventory.py`

## Changes

- `D` `dev/release/environment_inventory.py`
- `D` `dev/release/promote_python_cohort.py`
- `D` `dev/release/version_bump.py`
- `D` `dev/release/_asset_transport.py`
- `D` `dev/release/tests/test_environment_inventory.py`
- `D` `dev/release/tests/test_promote_python_cohort.py`
- `D` `dev/release/tests/test_promote_pypi_destinations.py`
- `D` `dev/release/tests/test_version_bump.py`
- `M` `dev/release/tests/test_justfile_release_guidance.py`
- `M` `RELEASING.md`
- `verify:` `uv run --no-sync pytest -q -n0 dev/release/tests/test_justfile_release_guidance.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/release/` -> `pass`

## Notes

The family is down to four modules, each with live consumers: readiness, version
identity, burned versions and alerting.

Each deletion was checked for a hazard it still guards rather than counted as
unreferenced. `version_bump` executed the bump stage of a workflow that no longer
exists, and the release pull request does that now. `promote_python_cohort` validated a
cohort for a publication flow that was replaced by building from the tag; its index
guard delegated to `version_identity.assert_version_available`, which survives with
consumers, so no refusal was lost. `_asset_transport` documented one remaining consumer,
and that consumer was the evidence-collection recipe removed in the preceding step.

`environment_inventory` was the closest call. Its capability is real - it reads forge
environment state, which is the class of gap that hid a missing deployment environment
earlier in this work - but it carried operator-obligation identifiers in its code and
prose, which the codebase does not admit, and its expected environment list named a
design that is gone while omitting the one the publish job actually claims. The
capability is preserved in the runbook as two commands whose output was checked against
this repository rather than assumed.

One failure in this run was mine: removing the evidence-collection recipe left the gate
that asserted its contents behind. Removed with it.

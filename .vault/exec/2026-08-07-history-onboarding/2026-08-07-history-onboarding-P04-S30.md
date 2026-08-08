---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:a7ea0d54d24a46f0db31f9f91c049944d8fdf2a0a5ce213f8596effe6868e549'
step_id: 'S30'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# Enroll the app.* payload modules into the JSON-schema conformance parametrisation in staged per-family batches, since SCHEMA_REGISTRY is populated at collection time from the config payload modules only, so every parametrised case was a config or root key and no app command was inside the gate at all. That is not something a passing run could reveal, because a gate can only check what is registered when it collects. LIVE FAMILY LANDED at commit 71a7cc3ba2, measured from outside the repository first with a probe that refuses rather than passes if the import adds no key: enrolling _app_live_payloads adds 33 schema keys and takes the gate from 163 to 229 cases, all green, so no conformance violation was hiding behind the absence. FOUR FAMILIES REMAIN and are the outstanding batches, named in the test module's own comment so the staging is visible rather than implied: agent-workspace, contract, maintenance and quickfile. Gate for each remaining batch. Measure the delta before landing, land only if green, and if a batch reds then that is a real conformance finding to report rather than a reason to leave the family unenrolled

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`

## Description

- Read the gate and establish which payload modules it imports at collection time.
- Confirm by measurement that no app command was inside the gate at all.
- Probe the live family from outside the repository, with a probe that refuses rather than passes if the import adds no key.
- Land the live batch and confirm the case count matches the probe exactly.
- Probe the four remaining families together, per module so the contribution of each is visible.
- Land them and confirm again.

## Outcome

The gate carried **no** `app.*` key. Every one of its 163 parametrised cases was a `config` or root key, so the whole `app` surface sat outside the conformance check while the gate reported green.

The mechanism is that the schema registry is populated by decorators at import time, the CLI loads its payload modules lazily at dispatch, and the gate imported only the config payload modules. So the registry was empty of app keys when the module collected. **A gate can only check what is registered when it collects, which means a passing run could not have revealed this** — the absence was invisible from inside the result.

Enrolled in two measured batches. The live family adds 33 schema keys and takes the gate from 163 to 229 cases. The remaining four — agent-workspace, contract, maintenance and quickfile — add 52 more for 333, with quickfile contributing 49 of those on its own. **All green in both batches**, so no conformance violation was hiding behind the absence; the coverage gap was the whole defect.

This matters for the campaign's own surface rather than in general: every command the history-onboarding work exposes is an `app live` leaf, so none of the payloads this campaign added had ever been checked for envelope conformance.

## Verification

Baseline, before any enrolment:

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py -n0 -q -m integration
    163 passed in 55.09s

Live family probed from a plugin resident OUTSIDE the repository, loaded by path, so nothing tracked changed while measuring:

    PYTHONPATH=<scratchpad> ... -p enrol_app_live
    PROBE APPLIED: enrolled 33 app.* schema key(s); first five ['app.live.borrador.100.latest', ...]
    229 passed in 56.48s

Then landed, and the count reproduced exactly:

    229 passed in 59.13s

Remaining four probed the same way, reporting per module so no family's contribution was assumed:

    PROBE APPLIED: 52 new key(s) total; per module {'_app_agent_workspace_payloads': 1,
      '_app_contract_payloads': 1, '_app_maintenance_payloads': 1, '_app_quickfile_payloads': 49}
    333 passed in 56.12s

Landed, reproduced:

    333 passed in 96.20s

Both probes **refuse rather than pass** when the import adds no key. That guard is the point: a probe that silently enrolled nothing would have produced a green run indistinguishable from a real measurement, which is the same failure mode as the gap being measured.

One process note against the runner: a first attempt exited 5 with no tests run, because these cases carry the `integration` marker and a bare path deselected all of them. The runner says so explicitly, and a green-looking exit there would have meant nothing.

`ruff format` and `ruff check` clean. Commits `71a7cc3ba2` (live) and `385db34f3d` (remaining four), both explicit pathspec, both verified after with `--numstat`.

## Notes

Executed by the coordinator directly rather than dispatched, while the fleet was occupied.

One bookkeeping failure of my own worth recording, because it is the state this campaign keeps finding in other rows: after landing the live batch I left this row unchecked and unrecorded, so it read as unstarted while a third of it was in HEAD. That is the same shape as the four rows found landed-but-unrecorded elsewhere in this campaign, and it happened to the person tracking them. Corrected by recording the batch in the row text before completing the rest.

The enrolment is additive and changes no assertion. It widens the parametrisation over the existing conformance rules, so a family reddening on enrolment would have been a real finding rather than a reason to leave it out; none did.

What this does not establish: that the app payloads are correct, only that they satisfy the conformance rules the gate encodes. A rule the gate does not have is still not checked for any family.

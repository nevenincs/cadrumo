---
tags:
  - '#exec'
  - '#distribution-harness-identity'
date: '2026-07-18'
modified: '2026-07-19'
body_hash: 'sha256:d6dce28b6f2952c35c682805f2649fd3b7c45bf490536ae142f00a83e0c9dcef'
step_id: 'S05'
related:
  - "[[2026-07-18-distribution-harness-identity-plan]]"
---

# Re-baseline the eval scenarios and golden expectations onto the migrated persona and skill tokens (scenario skill_name and persona fields, identity-switch and discovery golden scores, flywheel report expectations)

## Scope

- `src/cadrumo/agent/eval/scenarios/`

## Description

- Re-baselined the eval persona free-labels onto the migrated persona identity: the `persona="modelo-preparer"` fields on the hand-built `LiveTrajectory` / `LiveScenarioScore` fixtures in `test_discovery_scoring.py`, `test_identity_switch_scoring_golden.py`, and `test_report_and_flywheel.py` are now `"cadrumo-modelo-preparer"`, and the `_models.py` `LiveTrajectory.persona` docstring example was updated to match.

## Outcome

- The scenario `skill_name` fields (the other half of S05's token set) were necessarily migrated in S03 because `run_golden_scenario` validates them against the shipped skill directories, so the skill rename would otherwise have reddened the scenarios; S05 completes the persona fields. The `GoldenScenario` schema carries no persona field, so there was nothing to migrate in the scenario TOMLs for personas.
- No golden SCORES or report expectations changed: the deterministic scorers compute over the tool-call trajectory and command keys, not the persona label, so the identity-switch/discovery pass-fail verdicts and the flywheel report markdown assertions are token-independent and stayed green as-is. There are no stored golden-output fixture files to regenerate (goldens are inline typed fixtures; the flywheel promoted-scenario is written to a tmp dir, not committed). The re-baseline is therefore an honest reflection of the renamed surface, not a hand-patch to force a pass.
- Green gates: the full `src/cadrumo/agent/eval/tests` suite was 93 passed; ruff check + format + ty clean on the four touched files.

## Notes

- No incidents. Scenario NAME labels (e.g. `scenario="cierre-trimestre"`, `"descubrimiento-verbo-long-tail"`) were intentionally left unchanged: scenario names are a distinct identifier axis that the migration did not rename (only persona and skill tokens carry the `cadrumo-` prefix).

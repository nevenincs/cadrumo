---
tags:
  - '#exec'
  - '#distribution-harness-identity'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S05'
related:
  - "[[2026-07-18-distribution-harness-identity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace distribution-harness-identity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-07-18-distribution-harness-identity-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Re-baseline the eval scenarios and golden expectations onto the migrated persona and skill tokens (scenario skill_name and persona fields, identity-switch and discovery golden scores, flywheel report expectations) and ## Scope

- `src/cadrumo/agent/eval/scenarios/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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

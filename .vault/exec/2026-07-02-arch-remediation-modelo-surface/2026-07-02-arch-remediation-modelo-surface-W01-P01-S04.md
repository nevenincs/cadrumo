---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S04'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-modelo-surface with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-07-02-arch-remediation-modelo-surface-plan placeholders are machine-filled by
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
     The Delete the _rewrite_m210_sentinels rewrite shim and consume the typed unresolved-outcome member to emit the BLOCKING verification finding and ## Scope

- `src/aeat/application/modelo/_verification_actions.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Delete the _rewrite_m210_sentinels rewrite shim and consume the typed unresolved-outcome member to emit the BLOCKING verification finding

## Scope

- `src/aeat/application/modelo/_verification_actions.py`

## Description

- Delete `_rewrite_m210_sentinels` from verification actions.
- Add `_m210_unresolved_outcome_findings` to consume typed M210 outcomes.
- Convert the convenio verification tests from sentinel observations to `RegistryCalculationUnresolvedOutcome`.

## Outcome

The verification layer now emits M210 BLOCKING findings from typed unresolved outcomes.

## Notes

Focused verification for W1 passed: `32 passed in 22.49s` in `_scratch-codex/w1_m210_convenio_pytest.log`.

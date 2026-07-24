---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S26'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-wizard-substrate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S26 and 2026-07-23-tui-wizard-substrate-plan placeholders are machine-filled by
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
     The Retire the one-shot runner and prompter surfaces with every consumer moved in one atomic explicit-path commit, running collect-only clean immediately before the commit and regenerating apidocs stubs in the same commit and ## Scope

- `src/cadrumo/application/wizard/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retire the one-shot runner and prompter surfaces with every consumer moved in one atomic explicit-path commit, running collect-only clean immediately before the commit and regenerating apidocs stubs in the same commit

## Scope

- `src/cadrumo/application/wizard/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Verify pre-flight at HEAD: zero prompter references in `_commands.py`, the scripted-walk splice live, 416 wizard+flows tests green.
- Delete `_prompter.py`, `_runner.py`, `tests/_scripted_prompter.py`, `tests/test_prompter.py`, `tests/test_questionary_smoke.py`, `tests/test_runner_condition.py`.
- Relocate `WizardUnsupportedConsoleError` and `WizardEditUnsupportedConsoleError` into `_errors.py` as CLI-boundary wrappers of the substrate refusal; update their registry qualnames; delete the two answer-queue error rows with their classes.
- Prune the wizard package facade of the prompter exports and update its docstring to the substrate wording.
- Rewrite `test_setup_runtime.py` onto the scripted intent driver: canonical-dict drives, committed-map visibility assertions, substrate overflow error; regenerate the shared ordered-token fixture from the substrate's own projected walk, excluding the descendant-count token per the sibling realignment contract.
- Repoint `test_taxpayer_axes_roundtrip.py` onto the shared scripted walk helper.
- Drop the prompter test and imports from the modelo work wizard tests; remove the output-surface allowlist row; remove the retired lazy-import edge and lower the edge ceiling 477 to 476.
- Flip the prompt-singularity gate to assert the flow substrate's line frontend and capability probe as the only prompt surfaces, keeping the anti-vacuity anchor and discrimination tests.
- Regenerate apidocs stubs in the same commit (two stale stubs removed, wizard and tui toctrees refreshed).
- Run full-tree collect-only clean immediately before the commit; land everything as one explicit-pathspec commit.

## Outcome

Landed as one atomic commit (subject `refactor(wizard): retire the one-shot prompter and runner; the flow substrate is the sole prompt authority`, tagged `relocation:WizardUnsupportedConsoleError`; 19 files, +342/-1676). Post-commit gates green: prompt-singularity gate, documented-command conformance, JSON-schema conformance (509 passed together), wizard+flows suites (399 passed), modelo work wizard tests, error-registry suite. The flow substrate is now the sole prompt authority tree-wide.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- The pre-deletion consumer sweep caught three would-be breakages: the ordered-token fixture is imported by five sibling test modules; the sibling scripted-walk helper auto-defaults the descendant-count page so the shared fixture must not carry a token for it; and `WizardPersistMode` is a Literal, not an enum.
- Owner triage: lazy-import discovery failures from peer uncommitted work in `_checkpoint_store.py` and `_commands.py` (new function-local edges) are peer-owned and excluded from this commit, as are peer edits in `_persistence.py`, `flows/_review.py`, auth/apoderado files, and the auth apidocs stub.
- Deferred (approved): the two orphaned queue-error locale leaves await the post-merge locale sweep; the set-only locale lane discipline holds.

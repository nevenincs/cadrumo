---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:5ece0454bb4052baca99c8a445f4964c094c8e3133182ca2440e21fcdf7c5d1b'
step_id: 'S26'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Retire the one-shot runner and prompter surfaces with every consumer moved in one atomic explicit-path commit, running collect-only clean immediately before the commit and regenerating apidocs stubs in the same commit

## Scope

- `src/cadrumo/application/wizard/`

## Description

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

- The pre-deletion consumer sweep caught three would-be breakages: the ordered-token fixture is imported by five sibling test modules; the sibling scripted-walk helper auto-defaults the descendant-count page so the shared fixture must not carry a token for it; and `WizardPersistMode` is a Literal, not an enum.
- Owner triage: lazy-import discovery failures from peer uncommitted work in `_checkpoint_store.py` and `_commands.py` (new function-local edges) are peer-owned and excluded from this commit, as are peer edits in `_persistence.py`, `flows/_review.py`, auth/apoderado files, and the auth apidocs stub.
- Deferred (approved): the two orphaned queue-error locale leaves await the post-merge locale sweep; the set-only locale lane discipline holds.

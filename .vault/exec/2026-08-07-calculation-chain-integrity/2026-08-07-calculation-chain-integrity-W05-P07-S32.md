---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:ebdd710310dc76d8b10ff37fa51356f7db572d316bb6a6d5eee4497f9c4ec107'
step_id: 'S32'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W05.P07.S32

## Outcome

Classified, and the classification **contradicts the Step's stated root cause**. The six failures are real and the count is right; the shared cause is not a stray `.gitignore`.

## What the Step asserts

> six errors share one root cause where a stray gitignore sits in the build output directory outside the declared manifest

## What is actually there

**No such file.** A hidden-file sweep for `.gitignore` under every build-output-shaped directory returns nothing. The premise's artefact does not exist in the tree.

**The six failures do reproduce**, and the count matches exactly — `6 failed, 399 passed` across `dev/packaging/tests`:

- `test_each_recipe_collects_a_non_empty_selection` ×3 (`packaging-smoke-preflight-tests`, `packaging-smoke-installed-oracles`, `test-dev-ci`)
- `test_the_justfile_recipes_together_own_every_test_in_this_directory`
- `test_dependency_surface_cli_json_contract`
- `test_cli_exits_zero_and_emits_a_passing_report`

## The actual shared cause of the four

Four of the six fail with `no pytest collection summary in output`, and the assertion prints the output it rejected. That output **contains a collection summary**:

    998/1011 tests collected (13 deselected) in 0.92s

So the recipe's subprocess collected fine and the reader failed to recognise the result. This is a parsing failure in `_collected_count`, not a manifest or inventory drift — nothing about the cohort's contents is wrong.

The likely mechanism is visible in the rejected output itself: this test module contains **parametrised tests whose IDs embed collection-summary-shaped strings**, e.g.

    test_the_node_id_reader_declines_lines_that_are_not_node_ids[332/345 tests collected (13 deselected) in 1.11s]

A reader scanning line-by-line for a summary meets those node-id lines first. That is a plausible mechanism rather than a confirmed one — stated as such, because the reader was not stepped through.

## Why the distinction matters

The stated cause and the observed one lead to opposite fixes. "A stray file sits outside the declared manifest" points at the manifest or the build output; the observed failure points at the summary reader in the preflight harness. Acting on the stated cause would change packaging inventory in response to a test-harness parsing bug and leave all six failures standing.

## Disposition

Classified, not fixed, which is what the Step asks for. Two of the six (`test_dependency_surface_cli_json_contract`, `test_cli_exits_zero_and_emits_a_passing_report`) were not diagnosed and are not assumed to share the parsing cause — the Step's "one root cause" framing is itself part of what this record declines to take on trust.

Anyone fixing this should start at the collected-count reader in `test_preflight_recipe_selection.py`, and confirm the two undiagnosed failures separately before folding them into the same explanation.

---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:494edb6177a4a08fc9df57266d6fd71cde14d168f2cfbec405f9cc8a96efccc1'
step_id: 'S04'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Verify the full documented-command conformance gate passes green and pytest collect-only is clean

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`

## Description

- Add an anti-vacuity tripwire test (`test_gate_scans_a_realistic_invocation_count`) asserting the parsed-invocation count across the doc surface is at or above a `_VACUITY_FLOOR` of 200 (observed ~591), so a re-swept anchor fails loudly instead of passing a vacuous suite.
- Run the full documented-command gate, the reconciled sibling gate, `ruff`, `ty`, and `pytest --collect-only` over the CLI tests directory.

## Outcome

- Documented-command gate: green, 61 passed (60 prior + the new tripwire).
- Sibling self-referential-string gate: green, 8 passed after reconciliation; both gates together 69 passed.
- `ruff check` and `ty check` clean on both edited modules.
- `pytest --collect-only -q` clean across the CLI tests directory: 2319 tests collected, no collection errors (the earlier `ImportError` from the renamed symbol is resolved).

The static conformance floor is honest and non-vacuous, and the vacuity regression cannot recur silently: the floor test reds if the anchor is ever swept off `aeat` again.

## Notes

The tripwire floor is set well below the observed count and well above zero deliberately — a vacuity tripwire, not a brittle exact assertion, so ordinary doc churn never trips it while a re-broken anchor does.

## Review remediation (PASS-WITH-FINDINGS)

The W01.P01 code review returned PASS-WITH-FINDINGS; two remediations landed.

- Finding 1 (MEDIUM): the "no cadrumo CLI-invocation exists in docs" premise was false. Two how-to pages cited the wrong executable in line-wrapped inline spans — `cadrumo config auth configure` (authenticate-with-aeat) and `cadrumo app` (profile-setup). Both were rewritten to `aeat ...`. The parsed-invocation count stayed at 591 because both corrected citations sit in newline-wrapped inline-code spans that `_INLINE_CODE_RE` (single-line by design) does not individually capture; the same commands are already validated via their single-line occurrences elsewhere in each file. A minor extraction-coverage observation, not a defect: the inline-code extractor does not join a code span wrapped across two source lines.
- Finding 2 (LOW): a pre-existing parser false positive — the string parser tracked only the four root-global value-consuming options, so a resolved command's own value-consuming option made its value look like a dead subcommand (`aeat app agent --layout plugin` flagged "plugin is not a subcommand"). Fixed by preserving the ordered post-executable token stream on `_CitedCommand` and excluding option values (derived from the resolved command's real params) from the dead-subcommand check. Pinned by `test_value_consuming_option_value_is_not_a_dead_subcommand`, which also confirms a fabricated genuinely-dead subcommand under a live group is still refused.

Scope-enrollment deferral (per reviewer directive): expanding `_TREE_DOC_DIRS` to bind the nested `docs/reference`, `docs/verification`, and `docs/architecture` surfaces (~6 additional invocations) is deferred to the operator decision at W06. This is now ready-once-finding-2-landed: with the value-consuming-option false positive fixed, those surfaces can be enrolled without the parser reddening on legitimate `--option value` invocations.

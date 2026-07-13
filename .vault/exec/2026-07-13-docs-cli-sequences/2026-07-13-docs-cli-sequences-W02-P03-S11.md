---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S11'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-cli-sequences with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Write runner tests driving a real create-calculate-verify chain hermetically and asserting captured values thread through subsequent frames and ## Scope

- `dev/docs/sequences/tests/test_runner.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Write runner tests driving a real create-calculate-verify chain hermetically and asserting captured values thread through subsequent frames

## Scope

- `dev/docs/sequences/tests/test_runner.py`

## Description

- Drive a genuine Modelo 130 chain through the runner — `work create`, `work calculate` with real registry bindings, `work verify` as the terminal result frame — against real crypto and the real registry; the verify gate genuinely refuses without clean cross-period evidence, so the result frame exercises a real declared `@expect exit_code == 1`.
- Assert capture threading with the real ids: the captured work-unit and calculation-revision ids equal the envelope values their frames minted, appear in the later frames' executed argv, and the authored command lines keep their placeholders.
- Prove sandbox isolation and determinism in one assertion: two executions in fresh sandboxes yield distinct storage roots, identical capture maps, and zero pre-mask differing JSON paths with byte-identical raw outputs per frame (a state leak would surface as an idempotent-no-op envelope difference).
- Assert the fail-closed live-AEAT refusal for `app live ... pull`, `pull-history`, and `reconcile pull` frames, raised before the sandbox directory is even created.
- Assert the instructive capture diagnostics (text-output capture names the `--format json` remedy; a missing json-path names the path) and the fail-fast undeclared non-zero exit carrying the resolved argv and remedy.
- All tests real-behaviour: no mocks, no skips, no xfail, no seeded stand-ins; 11 tests green alongside the 40 parser/seed tests.

## Outcome

The W02.P03 runner is proven on a real CLI lifecycle end to end. Observed residual non-determinism for the chain is EMPTY: with the clock frozen and the profile id injected, work-unit and calculation-revision ids are content-addressed and every timestamp is pinned, so two runs are byte-identical pre-mask — trivially within the central `GOLDEN_MASK_FIELDS`. The test pins that observation; the W02.P05 anti-tautology gate formalises it.

## Notes

The Modelo 130 verify refusal exits 1 (not 0-with-warning), which is exactly the declared-non-zero case the grammar's `@expect exit_code` pseudo-path exists for. The sandbox profile's synthetic fact set had to include `identity.name`, `identity.surnames`, and `taxpayer_type.entity_type` to satisfy the modelo profile-readiness gate.

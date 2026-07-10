---
tags:
  - '#audit'
  - '#binding-vocabulary-cli-cohesion-close-honesty'
date: '2026-07-04'
modified: '2026-07-04'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-adr]]"
---

# `binding-vocabulary-cli-cohesion-close-honesty` audit: `binding vocabulary close honesty review`

## Scope

Fresh-context campaign-close honesty review for the binding vocabulary CLI cohesion campaign after the plan reached `27/27` checked steps. The review treated the campaign as newly inherited and re-checked plan health, execution-record coverage, operator-visible source vocabulary, current gates, and stale references before declaring the campaign closed.

## Findings

### vocab-plan-closure | low | plan structure and exec coverage are complete

`vaultspec-core vault plan status --json 2026-06-26-binding-vocabulary-cli-cohesion-plan` reports `27/27` steps complete, no next open step, and `exec_missing_ids=[]`. `vaultspec-core vault plan check 2026-06-26-binding-vocabulary-cli-cohesion-plan --json` reports no findings. The final open rows `W04.P07.S21` through `W04.P07.S24` now have closure-retry evidence in their execution records and were checked through the vault plan CLI.

### vocab-operator-surface | low | shipped operator vocabulary is reconciled

Source-only search over the CLI entrypoints, runtime write-policy allowlist, error registry, operator help, and locale catalogues found no `bindings preview`, `modelo.bindings.preview`, `calc pull --compute`, `pull --compute`, or `config.google.sync.calc.pull_compute` hit. Current HEAD carries the reconciled commands: `app modelo bindings resolve`, `config google sync calc compute`, and the canonical `app modelo work calculate`. Help probes for `aeat app modelo bindings --help`, `aeat config google sync calc --help`, and `aeat app modelo work calculate --help` confirm the same surface.

### vocab-gates | low | close gates are green in the current shared tree

The current close evidence is green: full collect-only completed clean (`12276/14908 tests collected`, `2632 deselected`), locale audit reports `ok` for all four root catalogues, documented-command conformance reports `58 passed`, JSON schema conformance reports `140 passed`, and locale parity plus help-honesty reports `21 passed`. Logs are recorded in the `W04.P07.S21` through `W04.P07.S24` execution records.

### vocab-historical-stale-examples | low | historical/test-output artifacts still mention retired names

The inherited search still finds retired command names in historical or generated evidence artifacts: the campaign reference and older ADR/research/audit documents name `bindings preview` and `calc pull --compute` as the problem being remediated, while `test_docs_output.txt` and `.agents/testimonials/review-calculation-values.md` contain old example output. User documentation source under `docs/how-to`, `docs/explanation`, `docs/tutorials`, `docs/runbooks`, and `README.md` has no stale `bindings preview`, `modelo.bindings.preview`, `calc pull --compute`, or `pull --compute` hit. This is therefore not a D9 operator-surface closure blocker.

## Recommendations

- Declare the binding vocabulary CLI cohesion campaign closed: plan structure, execution records, source-visible command vocabulary, and close gates are complete.
- Do not add a new D9 step for historical ADR/research/reference mentions; they preserve the before-state and remediation rationale.
- Formally defer `DFR-D9-VOCAB-HISTORICAL-STALE-EXAMPLES` to the documentation/test-output regeneration owner: refresh or archive `test_docs_output.txt` and `.agents/testimonials/review-calculation-values.md` when that surface is next regenerated. The blocker is explicitly outside the operator-visible source and user-doc source closure gate.

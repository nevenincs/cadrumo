---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:ef125bbd9140e0c7682c8400364eefb6b43b648d12321d27404dd739eef79377'
step_id: 'S99'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Take the second entry on the hiding-rank worklist and test whether it is wirable rather than only annotatable: the filed-history scoping signal and the period-selection rows are both consumed from constants, and neither is a one-line fix, since the classifier needs an availability report the discovery model consumes without retaining and the row projector needs pair and selection state the capture stage does not carry up. Record what the wiring would require and state in both docstrings that they are declared and not yet reached, the empty selection table and the least-informative hedge being what an operator sees meanwhile.

## Scope

- `src/cadrumo/application/live/filed_data_capture.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/application/live/filed_data_capture.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `pytest src/cadrumo/application/live/tests/ -k "filed_data or filed_history"`
  5 failed / 85 passed, IDENTICAL against `git show HEAD:` of the changed file,
  so the failures are pre-existing and unrelated
- `verify:` the four ledger gates 25 passed; `docstring_reference_ratchet`,
  module ratchet and secure-store gate exit 0
- `verify:` duplication 10 / 0.05%; dead code 0; unused 1033, exact 404
- `verify:` `ruff check` and `ty check` clean

## Notes

Working the hiding-rank list in order, this entry was tested for wirability
before being annotated, because a cluster described as "replaced by constant
defaults" reads like a one-line fix. It is not, and the reason is the same on
both halves: the inputs do not survive the pipeline.

`classify_register_scoping_signal` needs the availability report.
`FiledHistoryDiscoveryReport` consumes it to build itself and does not retain
it, so classifying at the composition site means carrying it on that model.
`filed_period_selection_rows` needs `declarations_by_pair` and `selected`,
neither of which the capture stage passes up. Both are model changes and stay
open.

What an operator sees meanwhile is worth stating exactly, and now is: an always
empty selection table, and `INCONCLUSIVE` — a hedge, so not untrue, but the
LEAST informative one, reported even where the discriminator could say more.
That distinction is why this is not simply a false claim like the filing-status
token was; the value is honest and uninformative rather than wrong.

The five failing tests are pre-existing. A/B against `git show HEAD:` of the
only file this step changed gives the identical five, and the failure is an
operation receipt carrying no `result_ref`, which is peer work in flight on the
operation-definitions surface.

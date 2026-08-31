---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:85988d08e1c83dc8c48e6561daeeadbd35aceb08e42dee58389cb3d975348744'
step_id: 'S105'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Correct the historical Modelo 303 box-45 finding to a parallel decomposition and record the parity recommendation.

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S105.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p02-s105-execution-self-review-audit.md`

## Notes

- Historical reconciliation only: the exact P02.S105 plan row corrected S104's one-box framing. Eight of the official ten addends were measured as unreachable from box 45 while 43 and 44 reached it, establishing parallel official-box and semantic-casilla derivations rather than a single divergent pair. No fresh source, registry, or test receipt is reconstructed.
- The historical recommendation was parity assertion, not rewriting the semantic decomposition to enumerate official box numbers: assert the official ten-addend identity so the two derivations remain locked together. This remained a structural recommendation, not evidence that a present filing value was wrong.
- Lifecycle boundary: S104 is the antecedent narrow hazard; S106 later isolates five official addends with a live omission finding and supersedes this row's risk framing. No S106 result is claimed here.
- This docs-only reconciliation changes no registry data, formula, source, plan state, baseline, threshold, or default index.

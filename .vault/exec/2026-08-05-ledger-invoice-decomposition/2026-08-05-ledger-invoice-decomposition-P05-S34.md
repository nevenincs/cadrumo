---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:99aea435b82d27ee9e1532f436e06ff7151a5206ea438a7561e55e4df5aba4c3'
step_id: 'S34'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Bundle the PGC norms cited in the oracle docstrings, or mark them not-yet-bundled so the citation stops asserting grounding it lacks

## Scope

- `src/cadrumo/_data/corpus/normatives/html`

## Description

- Reconcile the oracle docstrings against the bundled corpus.
- Take the second branch of the Step: mark the PGC citations as not-yet-bundled rather than bundling them.

## Outcome

Landed as commit `a3b1a50227`, "docs(tests): stop the oracle prose citing accounting norms it cannot show you".

RECONSTRUCTED RECORD, written 2026-08-06 from the commit.

THE STEP OFFERED TWO OPPOSITE OUTCOMES AND THIS RECORD STATES WHICH WAS TAKEN, because the row alone does not say. The action reads "bundle the PGC norms cited in the oracle docstrings, OR mark them not-yet-bundled". The commit subject settles it: the prose was corrected to stop citing what it cannot show. The norms were NOT bundled; the citation was demoted to an honest one.

That leaves the PGC NRV 12.ª/14.ª bundling obligation OPEN, exactly as the ADR still records it under its corpus-bundling constraint. A reader who assumed the first branch from the checked box would believe the corpus contains text it does not.

## Verification

```
uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests -n 0 -q
```

Re-verifiable directly against the corpus tree: the PGC norms remain absent from `src/cadrumo/_data/corpus/normatives/html`. The Step is complete in its second branch, and the bundling obligation it deliberately did not discharge stays live in the ADR.

## Notes

Reconstructed under the plan-closure rule after `vault plan status` reported this Step checked with no execution record. The commit was located by SCOPE FILE, never by step id: a bare `git log --grep=S##` returns commits from other campaigns, because step ids are per-plan and collide across plans. That search returned confident, plausible, entirely wrong matches for every one of the nine unrecorded steps before the namespace error was caught.

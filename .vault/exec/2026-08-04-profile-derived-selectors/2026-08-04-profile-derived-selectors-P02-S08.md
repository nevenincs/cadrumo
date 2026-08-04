---
tags:
  - '#exec'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:0cc73486f2ab65c46f26cf49ed1aebff1acf52de49cfc5fc02255c8470a88b05'
step_id: 'S08'
related:
  - "[[2026-08-04-profile-derived-selectors-plan]]"
---

# Delete the three derived-path seed lines from the eight files carrying the duplicated block, leaving the raw operator field untouched, and do NOT add per-descendant rows to compensate because all eight profiles declare zero descendants so the injector re-derives zero from genuine absence and no expected figure may move, treating any assertion that shifts as evidence the deletion was done wrong rather than as a figure to re-pin, and excluding the two idempotency tests whose purpose is asserting the injector defers to an explicit fact

## Scope

- `src/cadrumo/application/modelo/tests/`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

## Outcome

Three of the four duplicated seed lines are gone from all eight fixture modules, and no
expected figure moved.

The fourth line stayed. It seeds a RAW OPERATOR field rather than a derived one, and deleting
it would have removed a legitimate input -- a distinction an executor working from
"convert every derived seed" would plausibly have missed.

The deletion was safe for a measured reason rather than an assumed one, and the measurement
was made three times independently. All eight profiles declare zero descendants and carry no
per-descendant rows, so the injector re-derives zero from genuine absence and the seeded zero
was redundant rather than load-bearing. The executor confirmed this itself by grepping for
per-descendant rows rather than taking the brief's word, which is the check that made the
deletion defensible.

An earlier escalation had claimed the opposite -- that these were live consumers of the
override channel whose expected figures would move once the computation stopped being
suppressed. That claim was raised three times and was wrong: it generalised a figure measured
against a two-descendant fixture onto eight profiles that declare none. It was settled by
measuring all eight rather than by adjudication.

The escalation still improved the Step. The hazard it aimed at was real one step removed:
reading the instruction as convert-by-adding-descendants WOULD move every downstream
assertion and tempt a re-pin to whatever the engine emits, which is the tautology the project
forbids. The Step was hardened to say delete, add nothing, and treat a shifting assertion as
evidence the deletion was done wrong rather than as a figure to re-pin.

Two idempotency tests were deliberately excluded, since their whole purpose is asserting the
injector defers to an explicit fact. They invert with compute-always in a later Step and must
fail loudly when it lands rather than be quietly adjusted.

## Notes

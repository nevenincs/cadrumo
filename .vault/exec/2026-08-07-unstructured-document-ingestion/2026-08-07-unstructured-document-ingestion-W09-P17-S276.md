---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:14587a0413cf1e5273d11e2e44859b2c8bc795c42bfb9f08c9868b95e86ee071'
step_id: 'S276'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Let an operator record the identification without the territory

## Scope

- `src/cadrumo/entrypoints/cli`
- `src/cadrumo/application/ledger`

## Description

- Make the persisted territorial scope optional, and the CLI flag with it.
- Refuse a record that answers neither question, at the model and at the CLI.
- Stop the territory being manufactured where it was never answered.
- Re-anchor the roundtrip anti-tautology proof on the invariant that survives.

## Outcome

`--scope` was required while `--identification-state` was optional, so an operator who knew which State VAT-identifies a counterparty and not where it was established could not record the half they knew. That is an asymmetry on the axis the fifth amendment split precisely because the two facts are independent.

Both are now optional and either may stand alone. The relaxation is not a relaxed flag: it carries its own refusal semantics, because the shape it admits — a record answering nothing — is worse than the absence it replaces. An empty record addresses a counterparty, occupies its key, and answers every later question with a silence that reads as a confirmed absence. It is refused twice: by a model validator at the persistence boundary, and by an instructive CLI refusal that names both flags before the store is touched.

The load-bearing half is what an unanswered territory means downstream. `declared_fact` now returns nothing rather than a territory when the scope was never answered, so the assembly records a missing input. **Absence means the question was not asked, never that the answer is Spain** — the mainland is the majority answer, so a default there would be invisible in testing while placing Canarian and Ceutan counterparties inside a territory their operations are not subject to.

Two consequential sites moved with it. The conflict check compares only answers that both exist, so a narrower assertion over a stored territory is not read as a disagreement while a CHANGED territory still refuses. The contradiction path needs a stored territory to contradict, so a record holding only an identification raises none.

## Verification

    show CLI + counterparty CLI (unit or integration, -n0):   21 passed of 21 collected
    counterparty roundtrip:                                    4 passed of 4 collected
    application/ledger + JSON schema conformance:           1640 passed, 3 failed

Record states measured directly:

    identification only -> territorial_scope=None, declared_fact=None
    territory only      -> identification_state=None, declared_fact set
    neither             -> ValidationError

Locale key written to all four catalogues and confirmed by reading each value back from the file: 4 of 4.

## Notes

Of the three suite failures, one was mine and two were not. The confirmation-gate case passes in isolation and the structured-path case names none of the changed symbols; neither file references the changed surfaces at all.

The one that was mine is the roundtrip anti-tautology proof, and it failed for the right reason: it asserted that a persisted record stripped of its territory must not load, which was true while the territory was the whole content of the record and is false now. It was re-anchored rather than deleted. The proof now loads the narrowed record — asserting the relaxation actually works — and then strips the identification as well and requires the refusal. That is the sharper invariant, because it is the one that cannot be relaxed further without the record becoming meaningless.

A pydantic strictness error surfaced a second model still declaring the scope required, in the CLI payloads, which the type checker would not have caught because the field was simply narrower than its source. Found by running the verb rather than by reading it.

The catalogue files are deliberately NOT committed. My scaffold run removed a peer lane's `flows.manager.action.google_export*` keys, which have twelve live call sites in a file that lane is actively editing; committing my working copy would have deleted keys their code still calls. My own key is already at HEAD and their keys are intact there, so the correct action was to commit nothing from that path.

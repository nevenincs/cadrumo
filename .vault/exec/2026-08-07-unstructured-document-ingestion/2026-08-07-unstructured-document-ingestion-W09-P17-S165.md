---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:1a9486b22e555548c257ba7e13b2c7e673ed4e28c1b609699072ef5e11d0dcc4'
step_id: 'S165'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Add supplier and customer name rows to the read-path invoice field contract, each declared beside the identifier it belongs to, on the stated pairing rationale the postal row already carries.
- Declare both as free text, so neither asks for a role-evidence key.
- Widen both response models, the transcribed-value one and its anchor mirror, keeping field order aligned with the contract.
- Ground both fields through the same text grounder every other free-text field uses, add them to the grounded mapping the contract declaration keys, and carry them into the draft the grounder returns.
- Populate the party-name values and their anchors in the read fixtures, and the grounder parity fixture.

## Outcome

The record and the code now agree. The enrolled set named party names while the read-path contract carried neither, so the vision and text populations recovered no name at all and only the structured path filled the draft fields — a contract the code did not have, which the amendment names as misleading every reader until one of them moves.

The identity resolver is the consumer that was already waiting. Its confirm path documents its own gap in the code: the counterparty name is reachable only as an operator override, because there is no extraction heuristic for it. There is one now.

**The role-evidence question resolved to no, and it resolved by measurement rather than by preference.** `carries_role_evidence` derives from the declared form being a tax identifier, not from a hand-listed field set, and its paired validator refuses a role-evidence instruction on any other form — so a free-text name cannot carry one without changing what the property means. The same amendment that ordered this widening also ruled the evidence keys stay at two, because the design-target model's context budget is a hard constraint and a key with no consumer is review theatre. The two rulings agree, and the code enforces the second one structurally.

There is a substantive reason as well as a structural one. Role evidence answers "which party does this value belong to" for a value whose party is genuinely in doubt: two tax identifiers on one invoice have the same printed shape, so position says nothing about ownership. A name is not that kind of value — it is the thing a reader would quote to evidence an identifier's role. Asking for evidence of a name's role would be asking what assigns a name to the party whose name it is.

## Verification

The `llm` package, both lanes, sequential:

    uv run --no-sync pytest src/cadrumo/llm -n0 -q -p no:randomly -m unit
    376 passed, 3 deselected in 156.28s (0:02:36)

    uv run --no-sync pytest src/cadrumo/llm -n0 -q -p no:randomly -m integration
    2 passed, 377 deselected in 4.06s

The widening's own gates fired before the fixtures were populated and named every surface that had not moved: a missing anchor key, a field with no envelope, an envelope byte-identical to its value, and the contract-versus-grounder parity set. That is the mechanism working as designed rather than four separate defects — the parity gate keys off the one contract declaration, so a row added without a grounded value raises rather than travelling with no provenance.

Downstream packages, unit lane:

    uv run --no-sync pytest src/cadrumo/llm src/cadrumo/application/ledger src/cadrumo/entrypoints/cli -n0 -q -p no:randomly -m unit
    7 failed, 2320 passed, 3222 deselected, 16 warnings in 328.54s (0:05:28)

None of the seven is on this row's surface. Six are one lane mid-rename of an aggregation issue reason, with the enum moved and its tests not yet swept; one is a CLI module-size budget a different lane exceeded. Neither file set references the field contract, the response models or the party-name fields.

## Notes

**The prompt cost, measured rather than estimated.** Contract-derived prompt content grew from 4,729 to 5,515 characters, about 786 more or roughly 196 tokens, across the field-instruction lines and the JSON skeleton. The role-evidence block measured a delta of exactly zero, which is the ruling holding: two more fields cost two more instruction lines and two more skeleton keys, and no additional evidence keys. Sixteen contract rows became eighteen. The figure is the contract-derived portion of the prompt, not the whole rendered prompt, and it is stated that way because the whole is assembled from substitutions this measurement does not span.

The two surfaces the atomic widening warning named as the recurring trap were already closed for this field class before the row began: the draft carries both names, and the projection payload mirrors them. The extract command splats the draft into a payload that forbids extra fields, so a draft field with no payload field raises for every document — that trap has shipped twice on other field classes and does not apply here, which is why this widening reached four files rather than six.

The name values are spelled accented and with their legal-form suffix, and the anchors carry the printed heading rather than the bare name. Both choices are the fixture doing work: an ASCII fixture cannot fail when a reader folds diacritics silently, and an anchor equal to its value makes the downstream parse check compare a value against itself.

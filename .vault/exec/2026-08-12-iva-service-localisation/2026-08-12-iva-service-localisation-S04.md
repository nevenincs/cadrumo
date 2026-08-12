---
tags:
  - '#exec'
  - '#iva-service-localisation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:c5ef9a2fd9a66edf722b5203ecf57be1b6a82b0fff41d34aa932572666a59c16'
step_id: 'S04'
related:
  - "[[2026-08-12-iva-service-localisation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace iva-service-localisation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-08-12-iva-service-localisation-plan placeholders are machine-filled by
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
     The Fork the outbound services classification on the customer's condition per LIVA art 69: the B2B limb keeps not-subject under 69.Uno.1 for a recipient that is an empresario o profesional established outside the Comunidad, and the B2C limb resolves to a SUBJECT domestic outcome under 69.Uno.2 because the supplier is established in the TAI. UNKNOWN and PUBLIC_ADMINISTRATION reach neither limb. Declare the customer tax status on the row's consumed party facts so the operator is asked for it on this branch and only on it and ## Scope

- `src/cadrumo/domain/iva/_classification.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Fork the outbound services classification on the customer's condition per LIVA art 69: the B2B limb keeps not-subject under 69.Uno.1 for a recipient that is an empresario o profesional established outside the Comunidad, and the B2C limb resolves to a SUBJECT domestic outcome under 69.Uno.2 because the supplier is established in the TAI. UNKNOWN and PUBLIC_ADMINISTRATION reach neither limb. Declare the customer tax status on the row's consumed party facts so the operator is asked for it on this branch and only on it

## Scope

- `src/cadrumo/domain/iva/_classification.py`

## Description

- Narrowed the outbound services row to the B2B limb of art. 69.Uno.1.º, keyed
  on an `empresario o profesional` set that does NOT require registration.
- Added the B2C limb as a rate-tier row under art. 69.Uno.2.º, so a supply the
  TAI keeps picks its domestic category from the tier exactly as a domestic
  sale does.
- Widened the rate-tier demand to reach the new branch, passing an undetermined
  status as an open axis rather than as a value.
- Renamed the rule id to say what the row turns on, and moved its registry
  grounding row in the same change.
- Added the registry row for the new rule, with art. 69.Dos's carve-back stated
  in its notes.

## Outcome

Done. The rule-case fixture and the classification-assembly suite pass.

The rule-id rename could not have been split: the grounding table and the
decision table are held in parity in BOTH directions by a shipped gate, so a
renamed row with no matching registry row fails, and so does the reverse. That
is the gate working -- it made the atomic change the only possible one.

## Notes

**The governing record was wrong on one point and is amended rather than
quietly departed from.** It said the row should declare the customer's tax
status among the party facts it consumes. `PartyFact` is a two-member vocabulary
naming the establishment-versus-identification conflation specifically, and
`customer_tax_status` is a required criteria field nine sibling rows already read
without declaring anything. There was nothing to declare. What actually had to
widen was the rate-tier demand.

**Carried forward, named rather than left to be found:** art. 69.Dos is not
modelled, so its closed list of B2C services to recipients outside the Comunidad
is over-taxed by default. That is the direction the project's own mandate warns
nothing watches -- over-payment produces valid output, no refusal and no signal.
It is preferred here only because the operator can see and correct a subject
classification, while the under-declaration it replaces was silent. Modelling the
list needs a service-kind axis that does not exist: `TransactionKind` carries one
general services member, so deciding which lettered item an invoice falls under
would mean reading its prose.

**`PUBLIC_ADMINISTRATION` is deferred, not decided.** Art. 69.Tres.4.º treats a
legal person holding an IVA identification as an empresario for these rules even
when it does not act as one. Until that is grounded the member reaches neither
limb and lands on human review.

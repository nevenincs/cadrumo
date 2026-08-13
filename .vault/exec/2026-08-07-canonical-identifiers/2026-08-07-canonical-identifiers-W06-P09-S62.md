---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:1539796ec23526c6c03539b5ef7b7d582e3ca7e80f59fd2f1b6716a02514918b'
step_id: 'S62'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# cross-field tax-identity consistency audit for every model `W06.P09.S45` retyped

## Scope

- `src/cadrumo/`

## Description

- Checked the ADR's own scope boundary before auditing (`Consequences`,
  "a model holding two or more tax-identity fields for what is supposed to
  be one party" — the `ModeloDraft.profile_tax_id`/`.subject_tax_id` pair,
  guarded by `_enforce_draft_invariants`, is the ADR's own named proof
  case). The check is model-INTERNAL: two-or-more fields on ONE model,
  both meant to name ONE party. A cross-OBJECT divergence (two different
  model instances that happen to share a party) is a different, larger
  question this row's own wording does not reach — recorded separately
  below rather than silently folded in or silently dropped.
- `S45` retyped exactly two sites, in two models. Checked each:
  - `domain/contribuyente/family.py`'s `_RentaPersonProfileBase` (and its
    subclasses `RentaDescendantProfile`, `RentaAscendantProfile`): ONE
    tax-identity field (`tax_id`) per instance, naming that one descendant
    or ascendant. No second field on the model claims the same party — a
    `RentaFamilyProfile` holds a TUPLE of these, one row per distinct
    family member, never two fields for one member. **Disposition: N/A,
    single identity field, no cross-field validator applicable.**
  - `application/filing/_complementaria.py`'s `_SubmittedOriginal`
    (`@runtime_checkable Protocol`): ONE tax-identity field
    (`profile_tax_id`). **Disposition: N/A, single identity field — and
    moot regardless, since a `Protocol` carries no runtime validation at
    all (established in `S45`'s own record); a `@model_validator` has
    nowhere to attach on a pure structural type.**
- Traced `_SubmittedOriginal`'s sole concrete satisfier,
  `domain/submission/_models.py`'s `ModeloPresentado`, to check whether IT
  (not retyped by `S45` — it was already `SubjectTaxId`-typed at `HEAD`
  before this campaign, confirmed via `git show HEAD:` predating this
  session) holds a second tax-identity field. It does not — one
  `profile_tax_id` field, same single-field shape.
- Found a genuine but OUT-OF-SCOPE-for-this-row gap while tracing
  `_SubmittedOriginal`'s one live caller: `build_complementaria`
  (`application/filing/_complementaria.py`) reads
  `original_submission.profile_tax_id` (the `_SubmittedOriginal`/
  `ModeloPresentado` shape) and SEPARATELY loads `original_draft` (a
  `ModeloDraft`, via `_load_original_draft(original_submission.draft_id)`)
  and never asserts the two agree — even though `ModeloDraft` already
  guards its OWN two identity fields via `_enforce_draft_invariants`. This
  is the same identity-divergence risk the ADR names, but spans TWO
  model instances rather than two fields on ONE model, so it sits outside
  both the ADR's literal "sibling field on the same model" framing and
  this row's literal "model... that holds more than one tax-identity
  field" framing. Not fixed here — recorded as a candidate follow-up,
  matching this campaign's established practice of flagging a real
  adjacent finding rather than silently expanding a row's scope to absorb
  it (`W06.P09.S45`'s own two semantic-misclassification findings follow
  the identical pattern).

## Outcome

COMPLETE against the row's own gate. Both models `W06.P09.S45` retyped are
checked and recorded: neither holds more than one tax-identity field for
one party, so neither needs (and neither gets) a new cross-field
consistency validator. No code changed — the row's gate is a check-and-
record, and the check's answer for every in-scope model is "not
applicable."

## Notes

The `build_complementaria` cross-object gap is real and worth a deliberate
decision (add an explicit
`if original_submission.profile_tax_id != original_draft.profile_tax_id:
raise ModeloBuilderError(...)` guard, mirroring `_enforce_draft_invariants`'s
own shape) but is intentionally not executed by this row: it is a behavior
change to a live application boundary function, not a narrowing retype or
an in-scope model audit, and deserves its own sign-off rather than riding
in under a check-and-record Step's gate.

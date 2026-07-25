---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S13'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Collect the DNI validity-date contraste in the manager auth form and require a contraste only on the non-QR route, satisfied by either the soporte or the validity date, so the default QR flow and Clave Permanente are not refused

## Scope

- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py`

## Description

- Add the DNI validity-date row to the manager auth form, seeded from the profile like every other auth field.
- Persist the new path with the other three, through the same plural door.
- Replace the requirement that demanded both Cl@ve halves from every Cl@ve mode with the route-conditional rule the ADR correction states.
- Require the contraste only when the non-QR route is selected, and accept either the numero de soporte or the validity date as satisfying it.
- Exempt Cl@ve Permanente, whose second half is a password rather than a contraste.
- Route the decision through the resolver the live session entry uses, rather than restating its rule.
- Translate the new field label and the contraste refusal in all four catalogues, each carrying its own locale's date mask.
- Refuse a malformed validity date at the row by asking the record's own validator, before any write.
- Replace the docstring claim that the plural write door is atomic with the failure windows that actually remain.
- Prove the certificate is selected before the provider is activated by reading both events back, rather than by reading the source alone.
- Cover the action end to end for the first time, including that a refused answer writes nothing.

## Outcome

The page now asks for what the chosen route actually reads. A DNI holder
has somewhere to put their half of the contraste, and an operator on the
default QR route or on Cl@ve Permanente is no longer refused for a value
their route never reads. Before this, the refusal returned before the
commit, so those operators could not record even their provider choice:
the page was not degraded for them, it was unusable.

The rule is not restated anywhere. The page resolves through the same
profile-first resolver as the session entry and reads the same contraste
property, so the two surfaces cannot form separate opinions about
whether a credential is sufficient.

One defect found while covering it, and reachable by an ordinary
operator: the validity-date row was collected as free text while the
schema types the path a date, and the plural write door is a loop over
the singular one that persists between iterations. Typing the date in
the form the document prints therefore left the three earlier paths
durably written and the fourth refused, with the profile recording
credentials for a provider that workflow state never activated. The row
now asks the record's own validator before anything is written. The
half-write window itself is documented rather than papered over, because
closing it needs a transactional profile write, which is a question
about a door shared across the application rather than one this action
may settle.

Thirty-six cases pass. `ruff check` and `ruff format --check` pass;
`ty check` passes. The two owning suites and the locale honesty gate
pass whole and serially, 324 cases across both lanes, with no
held-serial warning.

## Notes

The implementation landed under `26fabdb536`, which is not this
executor's commit: the work was completed in the working tree and swept
into a peer's commit before it could be committed under its own. The
content is this Step's and is correct at HEAD; the attribution is not,
and is recorded here so a later reader looking for the Step's commit
finds it. The row-level date validation, the corrected atomicity account
and the end-to-end coverage followed in `15f71e175d`.

The plural-door atomicity claim had propagated into a docstring, a
commit message, an earlier Step Record and a test asserting the property
existed. All four are corrected; the test that defended it is replaced
by one that documents the real behaviour, so a later author who notices
the truth is not blocked by a gate defending a fiction.

The four locale catalogues were entangled throughout with two other
agents' live uncommitted keys. Each commit staged only this Step's hunks
through a patch reversed and reapplied against the index, leaving the
working tree untouched; both peers' work remained intact.

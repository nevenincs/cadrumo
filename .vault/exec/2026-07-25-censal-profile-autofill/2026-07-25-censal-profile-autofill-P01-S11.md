---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S11'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Declare the DNI validity-date contraste beside numero_soporte and resolve it profile-first with the settings fallback, refusing a non-QR route that carries neither form

## Scope

- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`

## Description

- Declare the DNI contraste in the auth section under its Spanish stem, beside its NIE counterpart and at the same identity sensitivity.
- Type it as a date, following the censo date fields, because the projection renders a date fact as the ISO token the AEAT form is given verbatim.
- Resolve it profile-first with the environment as fallback, the same shape as the identity and the soporte.
- Fold the two contraste forms into one accessor, so the refusal asks whether the operator has a contraste rather than which document they hold.
- Bind a profile-borne date onto the setting the non-QR page flow types into, unwrapped, since that setting is a plain string rather than a secret.
- Correct the three auth descriptions that asserted rationales the decision record has since overturned.
- Update the contraste refusal in all four locales to name both profile paths instead of sending a DNI holder to an environment variable.
- Pin the new field and prove the refusal did not weaken: a profile carrying neither contraste form still refuses the non-QR route.

## Outcome

Three new tests, eighteen in the two files together.

`uv run --no-sync pytest` over the two files reported `18 passed in 9.95s` at the committed HEAD. The whole auth package reported `188 passed in 251.20s`, up from `185` before this Step. The profile domain and application packages reported `285 passed in 44.66s`.

`uv run --no-sync python -m cadrumo.locales scaffold --check` reported `missing=0` for all four catalogues.

`uv run --no-sync ruff check` and `uv run --no-sync ty check` both reported `All checks passed!`.

## Notes

The whole auth section is absent from the compiled profile-key catalogue the wizard registers, so the value validator reports every one of its four paths as an unknown key. The declared date type is therefore not enforced on the write path: a malformed date is stored and typed verbatim into the AEAT form, where it is refused opaquely. This predates the new field and applies equally to the two that shipped before it, so it is reported rather than patched here; enrolling the section belongs with the setup surface that collects it.

The declared type is not decorative at the storage layer. A well-formed ISO value is promoted back to a date on read, so it renders as the exact token the form expects; only the absence of write-side validation is the gap.

The operator readiness probes and status surfaces still read the Cl@ve settings directly, so a profile-borne credential of any of the three kinds still shows as unconfigured there. A separate Step is proposed for it rather than folded in here.

The locale catalogue check reports four extra keys per locale for a censal pull action, orphaned when that pull was reverted at the tree level. They belong to another campaign and are left alone.

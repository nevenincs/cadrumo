---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:b17bdf90d3daf247a93740121d99b5d9596f28ee744e1e88c4bc6d53f3ec3d45'
step_id: 'S02'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Resolve Clave credentials from the active profile with a settings fallback, refusing a Clave mode missing either half and naming what is absent

## Scope

- `src/cadrumo/application/auth/_sessions.py`

## Description

- Read the active profile's identity and both Cl@ve credentials in one pass, replacing the single-purpose tax-identity reader so the record is opened once rather than twice per session entry.
- Resolve each Cl@ve half profile-first with the provider's own settings field as fallback, so an operator configured through the environment is unaffected.
- Bind a profile-borne credential onto the settings the provider will read, because the outbound providers take their credentials from settings and a resolved value would otherwise never reach the AEAT form.
- Return the caller's settings unchanged when the profile carries nothing, keeping the environment-configured path byte-identical.
- Refuse a Cl@ve mode with no DNI/NIE anywhere through a new typed error, naming the profile path and the configuration verb.
- Refuse the non-QR Cl@ve Movil route when neither contraste is available, and leave the QR route unrefused, since the QR route never types one.
- Keep the profile-identity guard's semantics unchanged, now reading the resolved identity rather than the raw setting.
- Register the new error in the error registry with its own refused code and a profile-edit suggestion, so the operator is not told to switch profile for a credential they simply have not recorded.
- Add the three locale leaves across all four catalogues through the locales CLI, and update the existing missing-identity message, which named only the environment variable.

## Outcome

Ten tests in `src/cadrumo/application/auth/tests/test_clave_credential_resolution.py`, all passing. They cover profile-wins, settings-fallback, the soporte reaching the contraste setting, both refusals, the QR route not being refused, the DNI validity date satisfying the contraste, the permanente identity, the certificate no-op, and that rebinding preserves every other secret.

`uv run --no-sync pytest src/cadrumo/application/auth/tests/ -q --no-header -p no:randomly -n0` reported `185 passed in 200.39s`.

At the committed HEAD, `uv run --no-sync pytest` over the two new test files plus the pre-existing operator tests reported `43 passed in 153.00s`.

`uv run --no-sync python -m cadrumo.locales scaffold --check` reported `ok` for all four catalogues. The error-registry and locale gates reported `82 passed in 111.05s`.

`uv run --no-sync ruff check` and `uv run --no-sync ty check` both reported `All checks passed!` across the touched files.

## Notes

The decision record says a Cl@ve mode with either declared field missing must refuse. Taken literally that would refuse the default QR route, which types no contraste at all, and Cl@ve Permanente, whose second half is a password the schema declares no field for. Refusing either would break a flow that works today, which the same decision explicitly forbids. The requirement is therefore grounded in what each route reads: every Cl@ve mode needs the DNI/NIE, and the contraste is required exactly when the non-QR route is selected.

The same record states the authenticating person is not always the taxpayer the profile describes, which is why the credential is recorded separately from the profile tax identity. The pre-existing identity guard contradicts that: it refuses whenever the Cl@ve identity differs from the profile tax identity, so a representative authenticating as themselves cannot proceed. The guard is a fail-closed safety gate and relaxing it is a safety decision, so it is preserved unchanged and the contradiction is reported to the coordinator.

The operator readiness probes and status surfaces still read the Cl@ve settings directly, so a profile-borne credential will not show as configured there until those surfaces adopt the same resolution. Live authentication itself is unaffected, because the binding happens at the session entry both live paths pass through.

Cl@ve Permanente's password remains environment-only. The schema declares no field for it and the settings description states it is deliberately environment-only, like the certificate passphrase.

The lazy-import, import-hygiene, docstring-link, locale-honesty and legacy-dotenv gates were red before and after this work, on sites owned by other campaigns and named in the coordinator report. None of the failing sites belong to the files touched here.

---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:18962be2cd3227ed6403015570d4b1af2976ca940c8bf282b64a3f1c67961873'
step_id: 'S262'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Reconcile all four production catalogues with current source and registry revision ownership, including Modelo 038, Modelo 220, Modelo 763, missing and orphaned keys, then rerun audit, drift, completeness, and every nitpicky build

## Scope

- `locales/ and dev/locales/ and docs/locales/`

## Description

Trace the shared runtime and documentation catalogue authorities, reconcile current source keys and Modelo revision moves through the canonical locale tooling, synchronize gettext once, and prove catalogue integrity plus localized rendering without an English fallback or a parallel locale owner.

Normalize authored multiline casilla display text only at the generated raw-HTML boundary so wrapped translations cannot break RST indentation, and retain the selected build language unchanged apart from whitespace.

## Outcome

The S233 state of 48 missing keys, 20 extras, and two revision moves per runtime locale was reconciled. Concurrent registry work landed Modelo 038, Modelo 220, and Modelo 763 ownership; the remaining six missing and eight stale keys per locale were supplied with real English, Spanish, Catalan, and Hungarian text through one batch and removed through one canonical scaffold.

After the canonical manager relocation landed, exact source discovery found 45 preserved `flows.manager.*` keys with zero production call sites. The no-legacy rule therefore retired that identical leaf set across Catalan, English, Spanish, and Hungarian through `dev.locales scaffold`; commit `6f7b0de660` contains exactly the eight canonical runtime catalogue files. Its `flows.yml` deltas remove the same 45 keys per locale, while its `cli.yml` deltas are ordering-only with flattened key/value mappings unchanged. Current `scaffold --check` and `audit` report all four catalogues clean.

The documentation i18n tool ran once. Two Hungarian machine-text dashes were rephrased and three retired environment-reference catalogues were removed. Multiline localized casilla values are collapsed only at the generated raw-HTML boundary. No English fallback, registry-local catalogue, or generated CLI reference edit was introduced.

## Final proof

- Runtime locale audit, parity, registry ownership, and dynamic-prefix coverage: 418 passed in 369.25 seconds.
- Documentation PO parse, completeness, orphan, and dash checks: 10 passed in 20.35 seconds.
- Fresh gettext catalogue drift: 3 passed in 79.01 seconds.
- Spanish, Catalan, and Hungarian nitpicky builds: 5 passed in 318.98 seconds.
- Main full-scope nitpicky build: 1 passed in 539.59 seconds.
- Ruff across `dev/locales`: clean.
- Scoped ty and Ruff for `dev/locales/tests/test_audit.py`: clean. A broad informational ty run over untouched `dev/locales` reported 55 pre-existing diagnostics and was not represented as S262-owned work.

Formal review independently verified the identical 45-key retirement, zero production call sites, ordering-only CLI changes, canonical authority, and absence of fallback or unrelated paths. Its initial rejection concerned only this record's stale pre-S268 wording; the wording and final green evidence are now corrected for re-review.

## Notes

The open checkpoint is `8e503ffd3a`. Documentation synchronization landed in `1ad8509ea4`; the raw-HTML renderer and regression landed amid `b4c58f41a7`; the contextual product-identity audit enrolment landed amid `5099b4f968`; and the final canonical runtime reconciliation landed in `6f7b0de660`. This record claims only S262's reviewed portions of concurrent commits and preserves all peer work.

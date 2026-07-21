---
tags:
  - '#exec'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
---

# Register or rehome the FormerProduct exception classes so the exception-base-hygiene gate passes without allowlist mutes

## Scope

- `src/cadrumo/core/errors`

## Description

- Confirmed no peer WIP in `src/cadrumo/core/errors` before editing.
- Ran `test_exception_base_hygiene.py` and enumerated the exact 3
  violations: `FormerProductStateError(RuntimeError)`,
  `FormerProductAuthSessionStateError(RuntimeError)`, and
  `Modelo210AgrupacionRentaRowsError(ValueError)`.
- Read each class's definition and every call site to determine root
  cause rather than muting the gate:
  - `FormerProductStateError` is raised from inside `Settings`/pydantic
    validation during bootstrap (`_resolve_database_url_for_active_profile`
    -> `refuse_former_product_database`), before the `AeatError` registry
    can be relied upon. The CLI boundary (`entrypoints/cli/_errors.py`)
    explicitly catches it ahead of the broad `AeatError` arm and
    translates it into a registered `CliRefusedBoundaryError` — the same
    shape as the existing allowlisted harness-boundary precedents
    (`SchemaResolutionError`, `LiveHarnessError`).
  - `FormerProductAuthSessionStateError` is the identical former-product
    refusal shape, raised at the session-store storage boundary
    (`_repository_for_path`) before any repository/registry access; a
    refusal-only signal that never reads, moves, or adopts the retired
    state it detects.
  - `Modelo210AgrupacionRentaRowsError` is a private domain
    row-validation carrier (`domain/modelos/_row_models.py`) with
    exactly one production call site
    (`application/modelo/_m210_agrupacion_renta.py`), which always
    converts it to the `AeatError`-derived `ModeloError` before it
    leaves the module boundary — the same shape as the existing
    `_RowParseError`/`_WizardFieldError` private-carrier precedents.
- Registered all three in `_ALLOWLIST` with the above rationale (no
  gate weakening; every entry documents why the class is a legitimate
  root, not why the check should be skipped).
- Re-ran the gate: both tests green
  (`CADRUMO_LOCAL_STORAGE_ROOT` pointed at a scratch directory for the
  duration of the run, working around an unrelated real leftover
  `aeat.db` file on this dev machine's storage root that otherwise
  trips `FormerProductStateError` during eager `Settings()`
  construction — never touching the real file).
- Ran ruff check + format on the touched test file; both clean.

## Outcome

Landed in commit `7fa034c84c`. `test_exception_base_hygiene.py` passes
both `test_production_exception_classes_do_not_introduce_unregistered_builtin_roots`
and `test_exception_base_hygiene_allowlist_carries_review_rationales`.
No production behavior change; the gate is genuinely green at HEAD via
root-cause classification of each root, not an allowlist mute of an
unexamined violation.

## Revision (wave-2 review)

The review returned REVISION RECOMMENDED (2 MEDIUM): `FormerProductStateError`'s
registration was confirmed genuinely honest and kept as-is, but the other two
allowlist entries were judged to be avoidable mutes rather than necessary
exceptions, since both classes could be rehomed instead.

- `Modelo210AgrupacionRentaRowsError`: rehomed to
  `(AeatError, ValueError)`, matching its three siblings already declared
  in the same module (`Modelo349CountryPrefixContextError`,
  `Modelo347ThresholdError`, `Modelo184ShareSumError`) — a one-line
  change since the module already imports `AeatError`. Registered as
  `REFUSED_MODELO_210_AGRUPACION_RENTA_ROWS` in the domain error-code
  registry shard, alongside its three siblings, following their exact
  field shape. The caller's existing `ModeloError` wrap in
  `application/modelo/_m210_agrupacion_renta.py` is unchanged.
- `FormerProductAuthSessionStateError`: unlike its sibling
  `FormerProductStateError`, it is raised at the adapter/storage
  boundary (`_repository_for_path`,
  `adapters/outbound/aeat/auth/_session_store.py`), never during
  `Settings`/pydantic bootstrap, and was never translated anywhere in
  production — it propagated as an unclassified internal error with no
  CLI-boundary catch. No bootstrap-cycle constraint bars it from the
  registry-bound hierarchy the way it does for its sibling. Rehomed to
  `AuthError`, the shared outbound-AEAT-auth base already declared in
  the same package (`adapters/outbound/aeat/auth/_errors.py`), rather
  than adding a CLI-boundary catch-and-translate: deriving from the
  established `AuthError` hierarchy is the more honest fix since the
  bootstrap-cycle reason that forces its sibling to stay a bare
  `RuntimeError` does not apply here, and it lets any caller already
  catching `AuthError`/`AeatError` observe this refusal without a new
  special case. Registered as `AUTH_FORMER_PRODUCT_SESSION_STATE` in the
  adapter error-code registry shard, alongside its sibling
  `AeatSessionExpiredError`.
- Both allowlist entries removed from `test_exception_base_hygiene.py`;
  `FormerProductStateError`'s entry is unchanged.
- Registering both classes required a locale `message_key` in the
  central error-code registry; added
  `errors.refused.modelo_210_agrupacion_renta_rows` and
  `errors.auth.auth_former_product_session_state` to all four locale
  catalogues via `python -m cadrumo.locales set`, never hand-edited.
- Re-ran the hygiene gate (both tests green), the M210 agrupacion-renta
  domain test suite, the session-store roundtrip test, and the
  repo-wide locale parity + translation-honesty gates plus the full
  `adapters/outbound/aeat/auth` and `domain/modelos` test suites (410
  passed, 8 deselected). One unrelated pre-existing failure surfaced
  (`test_codebase_to_locale_parity`: 26 "extra" `cli.help.*`/`cli.root.*`
  keys) — traced to an unrelated, still-uncommitted peer WIP in
  `entrypoints/cli/__init__.py` renaming its module-level `tr`/
  `PRODUCT_IDENTITY` imports to `_tr`/`_PRODUCT_IDENTITY` (confirmed via
  `git diff`, an in-progress private-import-naming cleanup, not touched
  by this Step); none of my new locale keys appear in that failure's
  key list. Ruff check + format clean on every touched file.
- Confirmed no peer WIP in any file this revision touched before
  committing.

Landed in commit `50078ae795`.

## Notes

No incidents. Blocked briefly on exec-record scaffolding because the
feature had no ADR document yet (`vault add exec` requires
research -> ADR -> plan -> exec); flagged to the team lead rather than
authoring the decision record myself, and the ADR landed shortly after
from elsewhere in the swarm.

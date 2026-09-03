---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:5fa2cf2f10afc1b9a0d23be539c77e2f3b2e5905c63276d4d381c608c19ab9a6'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `w08 p28 s403 review`

## Scope

Independent review of `W08.P28.S403` against the approved TUI architecture plan,
the accepted navigation-join decision and its root-composition research, and
the completed S400, S401 and S402 records. The committed review target was
`458c50e816`; unrelated dirty working-tree changes were not treated as
implementation evidence. The review covered
`src/cadrumo/entrypoints/tui/account.py`, `src/cadrumo/entrypoints/tui/app.py`,
`src/cadrumo/entrypoints/tui/launcher.py`, `src/cadrumo/entrypoints/tui/__main__.py`,
the four `src/cadrumo/locales/*/common.yml` files, and focused account, root,
launcher and generation tests. It checked delegation to the existing Profile,
Login, passphrase and operation owners; the username-left/actions-right header;
all six account actions; typed non-secret recomposition; capability teardown;
expiry handling; viewport/focus behavior; localization; and secret/internal-ID
redaction. The focused TUI suite passed (24 tests), but the installed entry
point still refuses without an externally supplied root provider.

## Findings

### production-account-door-composition-unreached | high | The installed root receives test-supplied doors rather than composing the account owners

At the committed HEAD, `compose_account_factories()` and
`compose_profile_sign_out_factory()` are defined but referenced only by their
focused tests. `InstalledWorkbenchFactoryDependenciesV1` accepts an already
constructed `AccountFactoriesV1`, and
`compose_installed_workbench_generation_provider()` only passes that value
through. No production launcher path binds the live profile session to the
Profile overview/persistence, login choices/authentication, passphrase
assessment/rotation, language, appearance and canonical sign-out owners. The
module entrypoint calls `main()` without a provider, which returns `2` and
writes `workbench.root.composition_required`; `python -m cadrumo.entrypoints.tui
--self-test` therefore never mounts the account header. The helper-level tests
prove delegation and no construction-time effects, not installed reachability.

### authenticated-session-recomposition-unreached | high | Typed root outcomes have no installed bootstrap owner

The app correctly clears account factories, destination/search catalogues,
refresh doors, active target and semantic focus before returning a typed,
non-secret result for change-user, password rotation, successful sign-out or
expiry. The launcher has a loop that can consume that result, but
`main()` receives its `recompose_authenticated_session` callback as `None` by
default and `__main__.run()` never supplies one. With the provider-only path,
the loop returns the outcome and `main()` discards it before returning zero;
there is no call site to the S401 bootstrap/session owner. Thus a root outcome
cannot select a fresh authenticated or unauthenticated root in the installed
entrypoint. The focused test injects the missing callback and so does not prove
the installed lifecycle.

### expiry-refresh-uncaught | high | A live-session expiry raises during child return instead of producing the typed expiry handover

`compose_secure_profile_workbench_generation_provider()` rejects an absent,
sealed, mismatched or expired custody session by raising `RuntimeError`, and
the secure generation read door invokes that check at both capture boundaries.
The app's expiry branch only handles a refresh door that returns a projection
whose posture is `EXPIRED`. On a real child dismissal,
`_on_destination_dismissed()` first invokes search refresh (which catches and
sanitizes the failure) and then invokes `_show_home()`; the Home refresh calls
the same generation provider and its exception is not caught. The result is no
typed `EXPIRED` outcome and no `_request_recompose()` teardown, leaving the
expiry contract unproven in the production path.

The app-level teardown itself is otherwise sound: the account factories,
destination catalogue, Home/search refresh doors, active target and semantic
focus are severed, and the operation scope is shut down by
`_run_root_session()`'s async context manager. The header renders only the
profile label; profile IDs and credential values are not rendered or included
in the recompose payload except for the deliberate non-secret handover
identity needed by the outer owner. The four locale files provide distinct
translations for all six account labels and refusal/default strings. The
80/100/120-column test confirms every account button remains focusable and
inside the viewport, with username before the action grid; it does not replace
the missing installed lifecycle proof.

### account-identity-join-unvalidated | high | Account display and strong-close identity can diverge

The revised `InstalledWorkbenchAccountInputsV1` independently accepts
`profile_id`, `profile_overview`, and `login_choices`. Its factory presents and
edits `profile_overview`, but binds canonical sign-out to the separate
`profile_id`; it validates neither identity equality nor that the selected
profile's label appears in the current login inventory. A stale or incorrectly
assembled input can therefore show account A while submitting the strong-close
operation for account B. This is a custody/session stale-state integrity break
at the new production account-composition boundary.

### authenticated-session-recomposition-resolved | low | Fresh provider selection follows root teardown

Resolved on re-review. `run_authenticated_workbench_sessions()` settles each
root's operation-service scope before passing only
`AccountRecomposeRequiredV1` to the injected outer session owner. It accepts
only a new root-input provider or stops fail-closed, so it cannot revive the
previous root. The focused real-session probe mounts two distinct roots across
a password-change request and observes the one non-secret handoff. The root
continues to clear its account, catalogue, Home and search fields before
returning that outcome.

### production-account-door-composition-resolved | low | Installed generation binds the existing account owners once per service graph

Resolved on re-review. The installed-generation adapter now builds
`AccountFactoriesV1` from current account inputs and the exact operation
composition services. It delegates Profile, login, passphrase, language and
appearance to their existing owners, while the sign-out door submits the
canonical request only on invocation. Construction captures no password or
custody material and the focused probe confirms it constructs the real Profile,
Login and Passphrase screens without persistence, authentication, assessment
or rotation effects.

### account-identity-join-resolved | low | The account boundary rejects stale identity and label joins

Resolved on re-review. `InstalledWorkbenchAccountInputsV1` now requires the
overview identity to equal the authenticated profile identity and requires that
identity to occur exactly once in current login choices with the same label.
Direct wrong-identity and wrong-label probes both fail before screen or
strong-close factory construction, preventing an account display from targeting
another profile.

### expiry-refresh-resolved | low | Confirmed live-custody expiry takes the typed teardown path

Resolved on final re-review. The secure generation provider now distinguishes
only a matching, unsealed live session whose own expiry check is true, raising
`AccountSessionExpiredError` for that case. The root catches only that exact
signal while refreshing Home and emits the existing typed `EXPIRED` handoff;
it clears account factories, destination and search catalogues, refresh doors,
active target and focus before exit. Missing, sealed or mismatched custody and
all unrelated refresh failures still propagate as their original failures, so
they cannot be represented as a false expiry. The focused root test injects
the precise signal during initial Home refresh and proves the stale
profile-bound doors are no longer callable.

## Recommendations

For `production-account-door-composition-unreached`, compose every account
door from the live authenticated session and the exact S402 services at the
launcher boundary, with no passphrase or custody object crossing into the root.
Add a real entry-point proof that invokes each owner through the account header
and confirms construction does not perform implicit persistence, network work
or a duplicate screen mount.

For `authenticated-session-recomposition-unreached`, connect the existing
typed outcome loop to the S401 bootstrap/session owner and add an installed
lifecycle proof for change user, password, sign-out and expiry that observes
old-door revocation and fresh-root selection.

For `expiry-refresh-uncaught`, translate custody expiry at the launcher refresh
boundary into the existing `HomeSessionPosture.EXPIRED`/typed outcome path (or
an equivalent fail-closed handover) before any profile-bound search or Home
projection is exposed, and test expiry during child return.

For `account-identity-join-unvalidated`, derive every account door from one
canonical selected-profile projection, or validate that the supplied profile
identity equals the overview identity and has the same current inventory label
before constructing a factory. Add direct refusal probes for mismatched
identity and label inputs.

No further S403 recommendation. Final re-review found no remaining
S403-owned critical or high finding. Focused lifecycle, account, installed
generation, launcher and bootstrap verification passed 48 tests; scoped Ruff
and ty checks passed; basedpyright reported zero errors, warnings and notes.

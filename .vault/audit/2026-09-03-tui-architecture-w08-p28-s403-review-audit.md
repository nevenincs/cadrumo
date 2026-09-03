---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:84dcd22d1cae3d54b9c107d41263d24592f875e65f24cdfebe38354ed14766e4'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `w08 p28 s403 review`

## Scope

Independent review of `W08.P28.S403` against the approved TUI architecture plan,
the accepted navigation-join decision and its root-composition research, and
the completed S400, S401 and S402 records. The live review covered
`src/cadrumo/entrypoints/tui/account.py`, `src/cadrumo/entrypoints/tui/app.py`,
`src/cadrumo/entrypoints/tui/launcher.py`, their focused account, root,
launcher and bootstrap tests, and the committed S403-adjacent diff. It tested
the production reachability of each account door, non-secret recomposition,
custody/session stale-state revocation, no implicit I/O or network work, and
single-screen replacement.

## Findings

### authenticated-session-recomposition-unreached | high | Root outcomes terminate the installed session instead of rebuilding it

`CadrumoTuiApp` correctly clears its account factories, destination catalogue,
Home refresh door and search doors before returning a typed non-secret
recomposition outcome for change user, password rotation, successful sign-out
or expiry. `_run_root_session()` returns that value, but `main()` discards the
result of `asyncio.run()` and returns zero. There is no launcher call site for
`run_workbench_bootstrap` or a session loop. Consequently each of the four
transitions closes the installed TUI rather than handing control to the
S401-owned bootstrap state machine for a fresh authenticated or unauthenticated
root. The focused test proves only that `_run_root_session()` returns the
request, so it cannot detect this installed lifecycle break.

### production-account-door-composition-unreached | high | The installed root receives test-supplied doors rather than composing the account owners

`compose_account_factories()` and `compose_profile_sign_out_factory()` are
referenced only by focused tests. The launcher accepts an already-built
`AccountFactoriesV1` through an externally supplied root-input provider and
never binds the current authenticated profile, login choices, canonical
passphrase owners or same-registry S402 operation services to those doors. The
entry-point fixture supplies only a `profile` member, so it cannot exercise a
real account action. This leaves Profile, change user, password, language,
appearance and sign-out as isolated factory helpers rather than production
account affordances, contrary to S403's composition scope.

## Recommendations

For `authenticated-session-recomposition-unreached`, make one launcher-owned
session coordinator consume each typed recomposition outcome, settle the old
operation scope, and invoke the existing bootstrap owner to select the next
root. Add an installed lifecycle proof for change user, password, sign-out and
expiry that observes old-door revocation and a fresh root selection.

For `production-account-door-composition-unreached`, compose every account
door from the live authenticated session and the exact S402 services at the
launcher boundary, with no passphrase or custody object crossing into the root.
Add a real entry-point proof that invokes each owner through the account header
and confirms construction does not perform implicit persistence, network work
or a duplicate screen mount.

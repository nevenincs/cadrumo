---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e00316f6b94945615d78726739235ac351f5ad178e16d892a8fac36dc63a80f4'
step_id: 'S206'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Have Terra XHigh turn on recovery enrollment at the profile creation door, wiring the composable enrollment mint into the create transaction so a real operator's profile is enrolled at the moment it is created, since the accepted decision places enrollment at creation and the mint lands as a primitive its consumer must call, and the single line that activates it belongs to the transaction whose ordering guarantee closed the displaced-session leak rather than to the row that built the primitive

## Scope

- `src/cadrumo/application/user_profile/_registration.py and src/cadrumo/application/user_profile/_custody_service.py`
- `src/cadrumo/entrypoints/cli/`
- `src/cadrumo/adapters/inbound/tui/`
- `src/cadrumo/locales/`
- `docs/how-to/protect-data-access.md`

## Description

- Keep recovery minting inside the sole registration transaction and require a
  verified handoff before capsule publication.
- Require exact masked mnemonic re-entry on attached-terminal and full-screen
  surfaces; cancel, mismatch and shutdown refuse without publishing a profile.
- Give headless callers paired bounded handoff and verification descriptors,
  with strict framing, descriptor preflight, buffer wiping and Windows HANDLE
  bootstrap support.
- Declare the paired descriptor contract on the authoritative command graph and
  project it generically into discovery schemas.
- Replace the password-only warning outcome with a mandatory enrolled outcome
  and document the operator protocol in every shipped locale.

## Outcome

Every supported profile-creation lane now enrolls recovery before the capsule
exists. Attached-terminal and TUI operators must re-enter the exact ordered
24-word mnemonic through a masked input. Headless callers receive one bounded
strict JSON handoff through an inherited writable descriptor and return the
same phrase through a distinct readable descriptor. The mnemonic never enters
arguments, environment variables, ordinary stdout or stderr, normal JSON
envelopes, logs, or durable application results.

Recovery handoff is fail-closed. Missing or one-sided channels, invalid or
colliding descriptors, malformed or oversized payloads, mismatched proof,
cancel, shutdown and I/O failure all abort before publication. Windows launches
the base interpreter directly so STARTUPINFOEX applies inherited HANDLEs to the
process that consumes them; the POSIX counterpart uses `pass_fds`.

The scoped feature gate passed Ruff and 39 integration tests, with the POSIX
transport case platform-skipped on the Windows host. Independent review found
no remaining HIGH or MEDIUM issue.

## Notes

The earlier narrower delivery and its permanent password-only profile outcome
are retired. No post-creation enrollment writer or compatibility path was
introduced.

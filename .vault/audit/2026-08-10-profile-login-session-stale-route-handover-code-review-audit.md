---
tags:
  - '#audit'
  - '#profile-login-session'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:116fe422853cafbdf3b0e39f518676940b4be19a103d0bcc93c7fa535f1fa014'
related:
  - "[[2026-07-24-profile-login-session-adr]]"
---

# `profile-login-session` audit: `Stale route handover code review`

## Scope

Reviewed the uncommitted stale-route handover change in
`src/cadrumo/application/user_profile/_login_session.py` and
`src/cadrumo/entrypoints/cli/__init__.py`, together with the added cases in
`src/cadrumo/application/user_profile/tests/test_login_session.py` and
`src/cadrumo/entrypoints/cli/_config/tests/test_login_frontend.py`. The review
was grounded in the accepted profile-login/session decision, the accepted CLI
action-envelope decision and its active plan, and checked the nested
`ContextVar` lifetime, the authenticated profile/pointer/session/database-route
alignment, failure safety, test anti-tautology, and shared-worktree overlap.

The nested route changes themselves are scoped correctly: `_record_activation`
routes both activation records to the authenticated bucket and restores its
caller's override on exit, while `_bind_authenticated_profile_to_invocation`
registers the replacement override as a Click context resource so it remains
effective through dispatch and is unwound at context close. The pointer, live
session, activation writes, and continued invocation therefore agree on the
authenticated bucket along the reviewed success path. The unrelated root
landing/import hunk in the same CLI file was treated as peer work and excluded
from the fix assessment; no peer files were modified by this review.

## Findings

### frontend-regression-fixture | high | The new real-adapter test fails before reaching the route assertion

`test_authenticated_profile_replaces_the_invocations_stale_storage_route`
registers its two profiles with different passphrases even though profiles in
one isolated storage root share the same wrapped master key. With normal
pytest addopts disabled so the named new case is actually collected, the
second `attempt_registration` raises `MasterKeyPassphraseMismatchError`; the
test never exercises `_bind_authenticated_profile_to_invocation`. The ordinary
project invocation reported green only because its active test-selection
configuration collected 8 of 30 tests and deselected this new case. The added
regression suite is therefore not green under full focused collection.

Resolution (2026-08-10): **RESOLVED.** Both registrations now use one
synthetic passphrase, matching the real shared master-key contract. An explicit
four-case real-adapter lane with repository addopts disabled passed `4/4`,
including both new stale-route tests, the no-screen gate refusal control, and
the existing named-other-profile manager refusal control. The corrected
frontend case now reaches and proves its effective-settings and classified
bucket-route assertions.

### shipped-handover-proof | medium | The original successful gate continuation is still not exercised

The frontend case calls `_bind_authenticated_profile_to_invocation` directly.
It can pass even if `_authenticated_at_the_gate` stops calling the helper,
binds it after session resume, or otherwise regresses the successful Textual
child-context to synchronous parent-context continuation that caused the
reported command failure. The application test independently proves that
activation writes tolerate a stale route, but neither added case performs a
successful `_authenticated_at_the_gate` handover or the named `config profile
edit` continuation. This leaves the connection between the two individually
tested halves unproved, contrary to the accepted decision's real
negative/recovery/retry and ordinary named-profile handover expectations.

Disposition (2026-08-10): this remains an honest validation boundary, not a
blocker for the narrow fix. The two production doors that repair the defect are
both exercised with real storage: `login_profile` proves activation against an
inherited stale route, and `_bind_authenticated_profile_to_invocation` proves
the synchronous Click-context replacement and route classification. What is
still absent is one terminal-driven composition proof spanning the Textual
child task, `_authenticated_at_the_gate`, and continued manager dispatch. That
residual should be added when the suite has a real full-screen terminal harness;
it does not invalidate the focused route and lifecycle evidence now passing.

## Recommendations

- For `frontend-regression-fixture`, register both profiles with the same
  synthetic operator secret, then rerun the named case with the repository's
  default selection disabled and retain the effective-route assertions.
  **Completed:** the corrected explicit lane passes.
- For `shipped-handover-proof`, add one real-behaviour test that drives a
  successful gate outcome through `_authenticated_at_the_gate` (preferably the
  named `config profile edit` continuation) and observes the effective route,
  resumed bucket session, active pointer, and continued target after the child
  Textual context returns. Do not replace that proof with a patched presenter
  or a direct helper call.

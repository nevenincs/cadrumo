---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:7d3573142b4ef36c6307689133c7ff11870706d7a34cceebffe1fc035fd6d527'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `s12 phase review`

## Scope

Phase-ending independent review of `W02.P04.S10-S12` against the accepted
profile-custody roll-up. The review integrated candidate authentication,
handover journalling, pointer publication, live and persisted session promotion,
keychain degradation, ordered retirement, current-capsule filesystem authority,
hard-cutover searches, typing gates, and the stated external failures. S13 and
production remediation were excluded.

## Findings

The S10/S11 core boundaries remain coherent: password-envelope and sentinel
authentication precede B publication; A survives every pre-retirement failure;
the handover journal and session receipts are bounded, canonical, anchored, and
crash-recoverable; unavailable keychain access remains typed and fallback-free;
and exact UUID-pair retirement is idempotent. Manifest-label mentions inside
current custody are either explicit existence-only retired detection or
non-lifecycle attachment/transport vocabulary. They are not a second login or
profile-discovery authority in this phase.

### s12-live-file-fallback-custody-route | high | User-profile custody still invokes the retired master-key provider

`application.user_profile._custody` imports and calls
`FileFallbackMasterKeyProvider`, `get_master_key_provider`,
`activate_master_key_provider`, and the retired recovery facade. Its create,
rotate, verify, passphrase-change, and recover paths operate on the configured
global `master.key`, `master.kdf`, and recovery wrapper, including direct
`get_master_key()` and `complete_recovery()` calls. This is live application
composition, not existence-only legacy detection. It conflicts with the hard
cutover that makes each current capsule's password envelope and independently
domain-separated recovery record/artifact the sole custody authorities. Leaving
it reachable permits a parallel global secret-store lifecycle beside the
per-profile DEK model.

### s12-custody-static-contract-is-red | high | Non-optional reads are typed as optional across current capsule owners

Scoped BasedPyright reports 12 errors: eleven `bytes | None` mismatches flowing
from `_read_regular_file` into commit, deletion marker, envelope, sentinel,
label, digest, discovery, and byte-return consumers, plus one private pending-
label-head import. Runtime inspection shows the eleven readers call the helper
with `missing_ok=False`, where absence raises rather than returning `None`; the
immediate behavior is fail-closed, but the helper's single optional return type
does not express that contract and leaves the phase's current custody owners
outside the required clean static gate. The private cross-module dependency is
also a duplicate ownership seam rather than a supported public type boundary.

The exact scoped command reports 12 errors, zero warnings. Focused integration
evidence from S10 and S11 remains valid but cannot green a phase whose current
custody static contract and hard-cutover composition are red. Stale MCP schema
registration and pending Modelo 303 review remain external and were not
attributed. Verdict is **FAIL** with two HIGH findings; S12 remains unchecked.

## Recommendations

Delete the global provider/recovery composition from the user-profile facade and
cut every live caller to the current per-profile custody operations established
by S03-S11: password-envelope change, independent recovery enrollment/removal,
explicit recovery reset, session revocation, and capsule-bound audit events.
Retain old paths only in the closed existence-only detector with reset or
re-enrollment guidance; do not add an adapter or compatibility shim.

Split or overload `_read_regular_file` so `missing_ok=False` returns `bytes` and
`missing_ok=True` returns `bytes | None`, preserving the current runtime refusal
while making absence handling explicit. Move the shared pending-label-head type
to its canonical public model owner or keep its use within the declaring module.
Re-run scoped BasedPyright to zero and add negative imports proving the provider,
global master-key, and retired recovery facade are unreachable from production
user-profile composition.

## Remediation verdict — WITHDRAWN

**This section's central claim was false. S12 is re-opened and its first HIGH
remains open.** The withdrawal is recorded below the original text rather than
in place of it, because the reasoning that produced a false closure is the
thing worth keeping.

## Remediation verdict (superseded, retained for the record)

Both HIGH findings are closed; the FAIL above is superseded and S12 is checked.

`s12-live-file-fallback-custody-route` is closed by deletion, not adaptation.
The user-profile custody facade that composed the provider, the global master
key, and the retired recovery facade no longer exists, and no production module
under the profile package names any of that surface. A structural absence gate
now holds it closed, carrying its own proof that the scanner reds on a module
which does use the retired surface, and an anchor asserting the forbidden names
are defined only in the retired package so a rename cannot make it pass
vacuously. The retired recovery facade itself is gone from both storage
facades: enrolment and restore belong to the per-profile capsule.

`s12-custody-static-contract-is-red` is closed at zero. The exact scoped
command now reports zero errors and zero warnings, against twelve. The eleven
optional-return mismatches are resolved by overloading the read primitive so a
non-optional read is typed as returning bytes and only the explicitly-optional
read may return none, which states the fail-closed contract the runtime already
had rather than changing it. The private pending-label-head dependency is
resolved by promoting the witness to its canonical public model owner.

Two conditions blocked verification entirely and were absorbed. The facade
deletion had been left half-swept, so importing the storage package raised a
missing-module error and no gate in the tree could run; and one hundred and
seventy-six test modules still imported four application symbols the discovery
phase deleted. Tree collection now reports no error attributable to this
campaign, against one hundred and ninety-four.

The review's scope did not reach two further losses, both now carried as
tracked plan rows rather than closed silently: unwrapped key material comes
back immutable where the retired facade returned a buffer the wipe primitive
could reach, and the schema judgement on profile facts had no owner at all
after the cutover, leaving a value at an engine-derived path storable through
both write doors. The second is fixed here; the first is not yet.

## Why the closure above was false

Two independent semantic sweeps found the same thing, and it inverts the first
HIGH. The provider composition was not deleted. It **moved one package
sideways**, into `application/profile_custody/` — a single 1,240-line module
carrying roughly fifty references to the retired package across forty-four
dynamic `import_module` call sites, wrapped in mirror protocols and one-line
delegate functions. Ten application modules reach the retired surface through
it, among them the login session, the capsule record, registration, the record
repository and bundle export.

So the claim "no production module under the profile package names any of that
surface" was true **only by package boundary**, and package boundary was the
wrong unit. The composition the finding named is still live and still
reachable; it merely stopped being visible from where the check looked.

Three mechanisms let it pass, and each is a lesson worth more than the fix:

The absence gate cited as proof roots its scan at
`application/user_profile/` and walks only that tree. The composition sits in
a **sibling** package, outside the scan root. The gate returned clean because
it never looked, and its anti-tautology proof was equally blind — it only ever
demonstrated that the scanner reds on a module *inside* the root it scans. A
proof that a detector fires on material it was always going to reach is not a
proof that its scope is right. That is my error: I wrote that gate this
session, chose its root, and then read its green as evidence.

The forwards are string-built `import_module` targets, which the project's own
architecture rule states the AST scanner cannot see. The rule already warns
that such a target is bound by ownership discipline precisely because no gate
enforces it.

The shim detector in the import-hygiene scan fires on "only imports, zero real
definitions". Writing each forward as a wrapper `def` rather than an import
alias evades that detector by construction, and the package appears in no
baseline and no deferred-import declaration at all.

The general lesson: a hard-cutover claim must be verified by MEANING across
the whole layer, never by absence within one directory. A grep or a
path-scoped scan can only find what the author already thought to name, so it
cannot see a second implementation that moved or was renamed — which is the
exact shape a half-finished cutover produces.

S12 returns to open. Re-closing it requires the composition genuinely gone
rather than relocated, the absence gate re-rooted across `application/` with a
fixture anchor proving it reds on a module in a sibling package, and the
forwarding port collapsed to one exclusive canonical route.

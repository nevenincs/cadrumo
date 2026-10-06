---
tags:
  - '#adr'
  - '#application-sign-in'
date: '2026-10-04'
modified: '2026-10-06'
body_schema: 'body-v2'
body_hash: 'sha256:44e89a6d8fb4814f47baa4a4790399b8e9ac2864f28822b2a00730ff8b8aa175'
related:
  - "[[2026-10-04-application-sign-in-reference]]"
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
  - "[[2026-08-13-profile-session-lifecycle-successor-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - '[[2026-09-26-mcp-purpose-authentication-adr]]'
---

# `application-sign-in` adr: `Application sign-in` | (**status:** `accepted`)

## Problem Statement

Signing in to Cadrumo means unlocking a profile with its password through the runtime. It does not mean AEAT certificate or Cl@ve authentication. Today every TUI window asks for the password, and the desktop app has no sign-in.

On 2026-10-04 the operator chose application-level sign-in:
- The desktop app signs the user in through the runtime.
- The TUI first reuses a live sign-in.
- The runtime owns the authentication state.
- Only interactive surfaces reuse a sign-in automatically.

The existing cross-process mechanism, the human login receipt, cannot carry that role as it stands (`2026-10-04-application-sign-in-reference`):
- nothing a user can reach revokes it
- it survives OS logout and reboot
- it is minted before its session is published
- clients unwrap the DEK and delete it
- it never extends
- open windows learn about revocation only by polling
- every CLI command resumes it

This record decides the sign-in model, its owner, its lifecycle and synchronization, and the desktop's part in it.

## Considerations

- Authority is never ambient. Each connection proves itself with a password, a receipt or an API key, and session ids are never portable bearers. Human sessions depend on their originating OS login. Agents use enrolled API keys or explicit attended delegation (`2026-09-26-mcp-purpose-authentication-profile-access-adr`).
- The application lifecycle owner is authoritative, and frontends cannot publish authenticated state (`2026-08-13-profile-session-lifecycle-successor-adr`). A valid password is necessary and sufficient, and corrupt throttle state means clear (`2026-08-13-profile-password-custody-rollup-adr`).
- Two further constraints come from other records:
  - The shell holds no runtime connection or authority (`2026-10-04-desktop-shell-adr`), and the manager holds none (`2026-10-04-runtime-manager-architecture-adr`).
  - A Rust transport client is excluded (`2026-10-03-application-packaging-adr`).
- Native lock observers report `locked` whenever lock state is unknown:
  - Windows on any native error
  - Linux without a GNOME lock binding
  - macOS always

  Runtime human sign-in is therefore impossible today on macOS and non-GNOME Linux.
- On Windows, every same-account peer binds to the runtime desktop's logon (the reference record covers this).
- The transport is strictly request-then-response. Pushed events are new protocol.

## Considered options

- **Runtime-owned shared sign-in, hardened from the receipt, with the desktop driving the canonical CLI login.** Chosen. It needs no transport client, no delegation and no desktop authority.
- **The desktop holds a session and issues one-time child tickets to each TUI.** Rejected for now: the tickets are unimplemented, and the desktop would need a persistent runtime connection. It remains open if per-window scoping is ever required.
- **Sign in once and every client is admitted.** Rejected as ambient authority. Limiting automatic reuse to interactive surfaces keeps non-interactive clients on API keys.
- **TUI-only sign-in, resuming first.** Insufficient on its own. It is kept as the TUI's behaviour.
- **The manager tray signs the user in.** Rejected: the manager holds no authority.

## Constraints

**Ownership.**
- The runtime profile host, under the application lifecycle service, alone mints, extends and deletes the human sign-in, advances its generation, applies lock-down and emits events.
- A frontend may read only the keychain-held proof and the receipt locator, in order to present the proof. It never unwraps, extends or deletes a receipt, and never handles the DEK.

**The shared sign-in.**
- Each profile has one live human sign-in per OS user's runtime, persisted as the receipt.
- Signing in again from another login replaces it. Each client still admits its own session on its own connection by presenting the proof. Nothing is delegated or shared.
- The receipt's authenticated data binds the originating `login_id` and a durable per-profile sign-in generation.
- On Windows, `login_id` is the logon of the runtime's own desktop. Same-account sessions elsewhere bind to it until the runtime-manager ADR's per-session admission follow-on is decided, and this record follows that decision.
- Resume refuses when the generation differs or the bound login is positively absent or locked.
- The receipt is minted only after its session is published, and only for a session that is still published.
- The mint runs under the admission guard and stamps the generation captured when the session was published. If the session is no longer published at mint time, the receipt is discarded.
- A refusal before publication leaves no receipt.

**Generation.**
- The sign-in generation, not the deletion of the receipt, is what makes revocation durable.
- It is stored per profile outside the encrypted bucket, in the same way as `profile-lock.json`, so sign-out works without the DEK.
- It is written and fsynced before any deletion. A mint first creates and fsyncs the record.
- If it is missing or unreadable, resume refuses and the receipt is deleted. A missing record never resets the generation to zero.
- It is registered in the storage taxonomy so that reclaim never removes it.
- Failures to delete the receipt are returned as typed results, never swallowed.

**Automatic reuse.**
- Only the TUI and a CLI attached to an interactive terminal resume a live sign-in automatically. `aeat config login` resumes it first unless a secret is supplied.
- Non-interactive CLI invocations do not resume automatically: pipes and scripts. They authenticate with a password on the secret channel, or with an enrolled API key. `aeat config login` with no secret in a non-interactive context refuses with `passphrase_channel_absent` instead of resuming.
- This gate is a client-side default, not an authority control. It stops accidental reuse by pipes and scripts. Any same-user process can allocate a pseudo-terminal or declare a frontend, and the runtime cannot verify either.

**Lifetime.**
- The configured idle and absolute deadlines stay as they are: 15 minutes and 4 hours by default.
- The idle deadline is extended by the runtime on one event only: an operation submission from a human-kind session whose operation definition is declared interactive. The rate is bounded.
- Observe, result, page, status, contract and event traffic never extend it.
- Whether live sessions are re-clipped to an extended deadline is settled in the plan.
- Where the receipt-sealing key lives during extension is a named follow-on decision, because it is a security trade-off. One option is runtime memory for up to the absolute lifetime. The other is the runtime reading the keychain, which contradicts the current proof-presentation rule. Until that decision is made, the receipt is not extended, and the session deadline governs.

**Sign-out.**
- "Sign out" is global for the profile's human access on this runtime. It runs one runtime operation:
  1. Advance the generation.
  2. Delete the receipt.
  3. Retire every human and attended session of the profile.
- It reports the automation that remains enabled.
- API grants and AEAT authority sessions are untouched.
- A human-kind session, or a presented proof, may request it. An API-key session may not.
- "Lock this window" remains as the per-session lock, and closing a window ends only that window's session.
- The desktop Sign out, the TUI sign-out and `aeat config logout` invoke the global operation.

**Lock-down.**
- Lock-down is triggered by positive evidence of any of these:
  - lock everywhere
  - OS lock
  - OS logout
  - password rotation or reset
  - recovery
  - profile deletion
- Each advances the generation and deletes the receipt, then retires the affected sessions and fences admission.
- OS logout is best-effort within the platform's session-end budget, and the generation check makes any receipt left behind unusable.
- An unknown lock or login state only blocks admission. It never deletes the sign-in.
- Observers therefore report lock state as locked, unlocked or unknown. Today they report a boolean that conflates locked with unknown.
- After a positive OS lock the password is required again.
- `PROFILE_LOCKED` refusals are handed to the TUI, which owns the resume flow.

**Platform scope.**
- Supported where the runtime can positively observe login and lock: Windows, and Linux with GNOME lock binding.
- Elsewhere sign-in is reported as unavailable until an observer exists. That covers macOS and other Linux desktops.

**Synchronization.**
- The runtime pushes session events to the connections of the affected profile: `revoked{reason}`, `signed_out`, `profile_locked` and `custody_changed`.
- Emission happens after the commit, from the retire point, which carries a reason, including lazy retirements.
- Each connection has a bounded, non-blocking queue. Overflow closes the connection.
- Events never gate revocation. The generation fence does.
- Clients clear private views and return to sign-in on receipt.
- Polling remains as a fallback that never extends anything.
- The generation is checked at publication under the admission guard, so a logout that races a resume always wins.

**Refusals and throttle.**
- Typed refusals reach every sign-in surface, and none is collapsed:
  - `THROTTLED`, with the remaining seconds
  - `PROFILE_LOCKED`
  - receipt expired
  - receipt absent
  - custody changed
  - keyring unavailable
  - login mismatch
  - generation changed
- The throttle keeps clearing on missing or corrupt state, as the custody ADR requires, and reports a typed unreadable-state diagnostic.

**Desktop sign-in view.**
- It lives in the shell's own origin, never in the documentation frame. It is shown before the TUI pane starts whenever the active profile has no live sign-in.
- One dedicated token-checked host command takes the password in a raw IPC body. It spawns a fresh `aeat config login --secrets-stdin --json` with a piped stdin, which is closed after writing. The host zeroizes its own buffers, and stdout is kept out of diagnostics.
- Tauri and WebView2 copies of the password cannot be wiped, and the record says so.
- The command runs as the CLI frontend. The shell holds no session, receipt or credential, never retries automatically and has DevTools disabled in release builds.
- The view re-reads status after any failure. Recovery and `PROFILE_LOCKED` hand over to the TUI.

**Profiles in the desktop view (amended 2026-10-06).**
- Until this amendment the view covered the selected profile only, and first run and other profiles were handed to the TUI. On 2026-10-06 the operator ruled, on seeing the view, that showing the profile, choosing between profiles, creating a profile, signing in and signing out in the desktop window are the foundation of the application. That ruling is the authorization for this amendment.
- The view names the profile a password is for under a visible label.
- The view lists the profiles on this computer. A token-checked host command spawns `aeat --format json config profile list`, which needs no password, session or runtime. Only each profile's label and selected flag cross to the window: the product's output redacts profile identities, so the label, which is unique on a computer, is how the view knows a profile. A list the product reports as incoherent is shown as unreadable, never as empty.
- Sign-in may name a profile. The sign-in host command passes the profile's label as the positional argument of `aeat config login`, after `--` so that no label is read as an option, with the password on the same piped stdin as before. The product selects that profile only after its login succeeds. With several profiles and none selected, the view sends nothing until one is chosen.
- The view creates a profile, on first run and beside existing ones. One further dedicated token-checked host command takes the name and the password in a raw IPC body and spawns a fresh `aeat config profile create --quiet --secrets-stdin -- NAME`, writing the password and its confirmation to a piped stdin that is closed after writing. The rules of the sign-in command apply unchanged: zeroized host buffers, stdout kept out of diagnostics, one submission, no automatic retry, typed refusals shown undiminished. The name travels as an argument and is never logged.
- Creation leaves the new profile selected and signed out, as the product does. Whether the host goes on to sign in from the same buffer, so that the password is typed once, is a *hypothesis* left open; until it is decided the view asks for the password again.
- Signing in to another profile does not sign the previous one out, and `aeat config logout` acts on the selected profile only. The view therefore offers another profile only while signed out: the person signs out, then chooses.
- Recovery enrolment is not part of the view.
- The shell still holds no session, receipt, credential or runtime connection.

**Desktop status.**
- A new unauthenticated runtime `sign_in_status` request reports presence and deadlines only. It never resumes or extends.
- It is exposed under its own CLI leaf, `aeat config sign-in-status`, for the desktop to read.
- It creates no profile host or worker and never reads the keychain.
- It reports `present`, `absent` or `unknown`, evaluated against the generation, the bound login and the deadlines.

**TUI.**
- Resumes a live sign-in first, then falls back to its password screen.
- Its own login offers "Stay signed in", off by default.
- A sign-in through the desktop or `aeat config login` always persists the sign-in.

**Migration.**
- The receipt keeps the `session.v2.json` file and the `cadrumo:profile-session:v2` keychain service.
- The new binding uses a new `schema_version`. A record with an older version goes down the existing delete-only mismatch path.
- Users sign in once after upgrading.

**Legacy paths.**
- These are retired in the same change as the binding:
  - the registered in-process login and logout operations
  - the non-runtime CLI receipt extension
- Afterwards, no code other than the runtime owner mints, extends or deletes a receipt.

**Out of scope:** cross-client delegation, automation access, and ending AEAT authority sessions on sign-out.

## Implementation

We will harden the human login receipt into the runtime-owned shared sign-in and add the sign-in generation, global sign-out, positive-evidence lock-down and pushed session events. The TUI and interactive CLI will resume first. The desktop gets a sign-in view that drives the canonical CLI login through a dedicated host command. Event framing, field names, the extension rate and the queue bound are *hypotheses* within the constraints.

- **Runtime:**
  - receipt binding and generation record
  - minting after publication
  - proof-only borrowing
  - login sweep on positive evidence
  - extension on interactive submissions
  - `human_sign_out`
  - the `sign_in_status` request
  - lock-down paths
  - a reason-carrying retire point and event frames with client-side demultiplexing
  - typed refusals
- **CLI:**
  - interactive-terminal detection gates automatic resume
  - `config logout` invokes sign-out
  - `config sign-in-status`
  - the legacy in-process paths are retired
- **TUI:** automatic resume first, the "Stay signed in" opt-in, an event subscription that clears views, sign-out via the global operation, and "Lock this window".
- **Desktop:** the sign-in view, the dedicated host command, typed refusal rendering, status refresh when the TUI exits and on focus, and a "Start Background Services" path when the runtime is unavailable. By the 2026-10-06 amendment: the profile list command, the named profile on the sign-in command, and the profile creation command.
- **Acceptance:**
  - each lock-down event against open TUI and CLI windows
  - logout racing resume
  - crash before and after mint
  - reboot
  - an RDP or SSH second session on Windows
  - unknown lock state not deleting the sign-in
  - upgrade with a live older receipt
  - keychain unavailability
  - throttling
  - a non-interactive CLI not resuming
  - no receipt mutation outside the runtime owner
  - the desktop secret absent from arguments, environment, logs, diagnostics and the documentation frame

## Rationale

Hardening the existing receipt yields one runtime-owned sign-in without ambient authority. Each window still proves itself. Only interactive surfaces do so automatically. The proof cannot outlive a sign-out, a lock-down or the bound login, because the generation fence makes revocation durable even when deletion fails.

Driving the canonical CLI login keeps the desktop free of runtime authority and of a second login implementation. Positive-evidence lock-down avoids signing users out on observer noise. Pushed events end the polling window, and the fence keeps races safe. Global sign-out matches what a shared sign-in means to the user.

## Consequences

**Benefits:**
- One sign-in, in the desktop, an interactive CLI or the TUI, opens every interactive window until it expires or the user signs out or locks.
- Sign-out and lock-down take effect everywhere.
- Pipes and scripts stop reusing a sign-in by accident, which steers agents toward API keys.

**Accepted costs:**
- New runtime state (the generation), operations and an event protocol.
- One more sign-in after upgrade.
- Unwipeable WebView copies of a password typed into the desktop.
- Non-interactive scripts need a password or an API key.
- Sign-in is unavailable on macOS and non-GNOME Linux until lock observers exist.
- On Windows the binding follows the runtime desktop's logon until per-session admission is decided.
- Same-user native code can still present a live proof.

**Amendments required once accepted:**
- `2026-10-04-desktop-shell-adr`. Line 89, "The shell shows no authentication UI. Login stays in the TUI", becomes "The shell hosts the application sign-in view of `2026-10-04-application-sign-in-adr`, submitting only through its dedicated host command to the canonical CLI login, and holding no session, receipt or credential". Line 82 admits the sign-in view's sign-in state, typed refusals and the manager-start path. Line 263's reconsideration trigger is recorded as exercised.
- `2026-10-04-runtime-manager-architecture-adr`. "Authentication and approval prompts belong to the TUI" becomes "Approval prompts belong to the TUI. Application sign-in follows `2026-10-04-application-sign-in-adr`."
- `2026-09-26-mcp-purpose-authentication-profile-access-adr`: add a "Human sign-out" row. Lock everywhere and positive OS lock or logout also advance the sign-in generation and delete the receipt. Automatic resume defaults to interactive surfaces. This is a client-side default, not an authority control.
- `2026-08-13-profile-password-custody-rollup-adr`:
  - The human receipt binds the originating login and the sign-in generation.
  - It is minted after publication and is extended or deleted only by the runtime.
  - The keychain service is `cadrumo:profile-session:v2` with account `<profile UUID>:<session UUID>`.
  - The throttle rule is unchanged.

**Reconsider if:**
- per-window scoping is required
- WebView secret exposure becomes unacceptable, in which case the view moves to a dedicated window
- per-session admission changes the Windows binding
- lock observers arrive for macOS or other Linux desktops

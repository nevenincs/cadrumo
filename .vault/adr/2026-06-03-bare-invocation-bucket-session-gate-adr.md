---
tags:
  - '#adr'
  - '#bare-invocation-bucket-session-gate'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-wizard-catalogue-startup-ordering-adr]]"
  - "[[2026-06-02-m303-parser-engine-totals-impedance-adr]]"
  - '[[2026-06-04-bare-invocation-bucket-session-gate-research]]'
---


# `bare-invocation-bucket-session-gate` adr: bare CLI invocation does not require an active bucket session | (**status:** `accepted`)

## Authoring note

Authored via Write tool — same bash constraint as the prior seven ADRs this campaign. Commit-bot validates via `vault check all`.

## Problem statement

`aeat --language en --format json` (bare invocation, no subcommand) currently returns an `INTEGRITY_STORAGE_VALIDATION` refusal because no active bucket session is open. `test_profile_output_language` creates a profile via `config profile create`, then bare-invokes — the second call fails because the storage-validation gate now refuses bare invocation when no session is active.

Two shapes:

- **A**: bare invocation does NOT require profile-bound storage. The `--language` flag is operator-side preference; it should resolve against an in-process default. Exempt bare invocation from the session-required check, same as `--help`.
- **B**: bare invocation requires a session for design reasons (e.g. `--language` reads profile preference). Update the test to switch to the profile before bare-invoking.

## Decision: Option A — bare invocation is exempt from the bucket-session gate

The `aeat-architecture-boundaries` rule documents the CLI root surface as `config` + `app`. Bare invocation (no subcommand) is technically neither — it is a metadata-emitting introspection surface analogous to `--help` and `--version`. The `--language` flag at bare invocation governs the LANGUAGE OF THE INTROSPECTION OUTPUT (which language to render the help text / version banner / format-shape preview in), not the operator's persisted language preference.

Three grounding signals support this:

1. **`--help` already exempt.** The CLI bootstrap exempts `--help` from the session-required check because help-text rendering is a stateless operation. `--version` follows the same pattern. Bare invocation IS the same shape: emit static or operator-flag-controlled metadata without reading or writing persistent state.

2. **`--language` resolution order documented at `core/i18n/_render.py`.** The render layer's resolution chain is: `override_settings(aeat_output_language=...)` first, then `settings.aeat_output_language` (env-var / explicit CLI flag), then `DEFAULT_OUTPUT_LANGUAGE` fallback. The active-profile preference IS consulted but only for non-bare CLI paths that establish a profile context. Bare invocation never establishes a profile context, so the chain skips the profile branch and lands on env-var / explicit-flag / default. The flag at bare invocation is the explicit override.

3. **Cold-start UX continuity.** A cold-start operator with no profile yet should be able to type `aeat --help` (or `aeat --language en --format json` to preview the help payload shape) and get a response, not a session-required refusal. Forcing profile creation before any operator can read the help text inverts the discoverability semantic and breaks the documented cold-start flow (the cold-start guard at `test_cold_start_wizard_registration.py` exists specifically to guarantee bootstrap-without-session works).

## Why not B

Option B treats `--language` at bare invocation as if it were the persisted profile preference. That conflates two distinct concepts:

- **Operator-flag language**: the language of THIS invocation's rendering. Stateless. Resolved from the CLI flag.
- **Profile language preference**: the operator's persisted setting. Stateful. Resolved from the profile envelope.

The bare-invocation path needs only the former. Requiring a bucket session to surface the former (which lives in the CLI flag, not in storage) over-gates. Reject.

Additionally, B's test-side fix ("switch to the profile before bare-invoking") changes the OPERATOR contract to satisfy a recently-introduced storage-validation gate. That's the contract bending around the implementation, which is the wrong direction.

## Decision concrete shape

The bootstrap exemption list at `entrypoints/cli/__init__.py` (the same list that exempts `--help` and `--version` from the session-required check) gains the BARE-INVOCATION path. The check becomes: require active session WHEN a subcommand is invoked (config / app / etc.); SKIP the check when the invocation is bare (no subcommand, only top-level flags like `--language`, `--format`, `--help`, `--version`).

The detection at the bootstrap layer is whether Typer's resolved subcommand is None vs a registered command. None → exempt. Anything else → continue to the session-required gate.

## Consequences

- Bootstrap: ~5 LOC added to the exemption check at `entrypoints/cli/__init__.py`.
- `test_profile_output_language` passes without test rewrite — the existing test contract was correct; the recently-added gate over-broadened.
- Cold-start UX preserved: `aeat`, `aeat --help`, `aeat --version`, `aeat --language en --format json` all work without an active session.
- Subcommand UX unchanged: `aeat config ...`, `aeat app ...` still require an active session as they did before, because they're not bare.

Anti-tautology gate: a new test that asserts (a) `aeat --language en --format json` succeeds with NO active bucket session and emits the expected metadata payload, AND (b) `aeat app modelo ... ` STILL FAILS with the session-required refusal when no session is active. Proves the exemption is scoped to bare invocation only.

## Out of scope

- The persisted-profile-language preference resolution (still goes through the existing render layer for subcommand paths).
- The broader `INTEGRITY_STORAGE_VALIDATION` gate's design intent for subcommand paths (kept as-is).
- Cold-start wizard catalogue registration (separate ADR `2026-06-03-wizard-catalogue-startup-ordering`).

## Dispatch

Hand to coder. ~5 LOC bootstrap edit + 1 anti-tautology test. ~1 commit.

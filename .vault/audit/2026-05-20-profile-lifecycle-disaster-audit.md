---
tags:
  - '#audit'
  - '#profile-lifecycle-disaster'
date: '2026-05-20'
related: []
---

# `profile-lifecycle-disaster` audit: `operator blind re-test P06 testimonials and findings`

## Scope

P06 re-test gate of the profile-lifecycle disaster-recovery campaign.
Five blind operator personas each operated the `aeat` CLI in an
isolated clean install with no source access, scoring operator
friction 0 (effortless) to 10 (blocked). The campaign's close
condition is operator pain reduced from the original "heavy" baseline
toward zero. This document is the closing synthesis (P06.S42-S47); it
also records the three-axis semantic audit swarm run after the
reconciliation campaign's structural refactor.

## Findings

### Persona re-test — pain scores

- newcomer (first-time freelancer): 6/10.
- returning (Monday-morning re-orientation): 6/10.
- dual (two-client bookkeeper): 4/10.
- fumbler (error-prone usage): 2/10.
- curious (full-surface explorer): 5/10.
- Mean: ~4.6/10 — "moderate". Down from the original "heavy"
  baseline, but not zero.

### What is genuinely fixed (the original campaign's worst axes)

- Error paths: the fumbler recorded 13 of 14 deliberately-wrong
  inputs producing a clean, translated, actionable refusal, with
  ZERO raw Python tracebacks across the session. Did-you-mean fires
  at every command-tree level; every state guard names the bad value
  and the exact remedy command. Error handling — the heaviest
  original pain point — is now a strength.
- Cold-start refusal / no-active-profile guards: every persona hit a
  profile-data command with no profile and got a clean refusal with
  the exact create command, not a crash.
- Destructive-action safety: `delete` / `repair quarantine` /
  `reset-state` consistently refuse without `--yes` and print the
  exact re-run command; human-worded, not bureaucratic.
- Command-surface map: the two-root (`config` / `app`) structure is
  stated up front; `aeat` no-args and `overview status` give a real
  onboarding map.

### Real defects — HIGH

- `aeat config profile edit --quiet` is a destructive full rewrite,
  not a patch: unsupplied fields silently revert to defaults;
  `output_language` flipped `en`->`es` while editing an unrelated
  field. No `--set` / patch mode. Corroborated by returning + dual.
- Postcode `08001` stored as `8001` — integer coercion strips the
  leading zero; the field must be a 5-digit string.
- `aeat config profile create` can leave a torn / split-state
  profile — pointer file present, encrypted DB record absent
  (`repair profile` reports `missing_profile_record`). The curious
  persona's first-run profile then failed `duplicate` with "Perfil
  desconocido". The atomic-create contract (all-or-nothing with
  rollback) is not holding on every path; #33 hardened
  `initialize_workspace`, but the wizard `profile create` path can
  still strand a pointer without a record.
- `aeat --version` / `--help` cold start ~6 seconds — the fast-path
  (disaster-plan P04) has regressed; trivial dispatch eagerly imports
  the browser adapter and constructs pydantic-settings.

### Real defects — MEDIUM

- `profile create` silently promotes the new profile to active with
  no line in its output (dual + newcomer).
- `--activity` accepts arbitrary free text with no validation
  (fumbler created activity `pizza-delivery`).
- UTF-8 encoding corruption in `modelo casillas 303` output
  (`deducciXX` — UTF-8 bytes shown as Latin-1); operator-visible.
- `repair logs` emits a SQLAlchemy traceback to stdout mixed with the
  successful path output when run without an active session.
- `profile import` has no `--target-id`; re-importing an exported
  profile into the same storage root dead-ends on "ya existe".
- Help tables truncate long flag names (`--address-postco...`),
  making the real flag name unreadable.
- The post-create workflow is undiscoverable: `work create` returns
  an opaque 64-char SHA-256 id with no short alias / active-unit
  concept; `calculate` dead-ends with no casilla-id discovery path.
- `live portals list` emits raw i18n keys instead of resolved labels.

### Real defects — LOW

- `profile list` help text wrongly says it lists config keys.
- NIF validation error leaks the internal key path
  `wizard.setup.profile.tax-id.prompt`.
- Refusal text rendered in Spanish under an `output_language=en`
  profile (entangled with the edit-rewrite defect).
- `repair integrity` description is English-only — the lone i18n gap.
- The interactive-wizard refusal is the default onboarding path; the
  `--quiet` escape is buried below two irrelevant suggestions.
- Silent `iva.regime=GENERAL` / `tax_residence.ccaa=madrid` defaults.
- Tombstoned profiles still appear in `profile list`.

### Cross-campaign / transient

- A raw Pydantic `ExternalConstants` `ValidationError` traceback on
  `--help` of several lifecycle verbs (`profile census`,
  `modelo work verify` / `file` / `audit` / `filing-record` /
  `verification-report`). dual, newcomer, and curious all hit it;
  curious saw two different missing fields (`auth_gate_4033`,
  `census_g313_launcher`) across runs — the external-constants
  schema-hardening campaign is actively editing the model and the
  bundled data, which transiently disagree. Verified non-reproducing
  after that campaign settled. Latent fragility stands: a
  module-import-time `_Settings()` / `_BROWSER_DEFAULTS` must not be
  able to crash an unrelated command — lazy initialisation removes
  the failure class. Flag to the external-constants campaign.

### Semantic audit swarm

- persistence-boundary identity: clean — persisted strings stable
  across renames; 87 roundtrip tests with anti-tautology proofs;
  typed `Envelope` version discipline; SHA-256 identity helpers.
- cross-domain handoffs: two HIGH findings, both fixed (a
  silently-empty cross-domain check; two re-broken import-linter
  contracts). All four layered contracts now enforced.
- calculation grounding: clean — provenance, casilla coverage,
  referential integrity intact; one reported test gap verified moot.

## Recommendations

The re-test verdict: operator pain fell from "heavy" to "moderate"
(~4.6/10). The campaign does NOT close — the close criterion is
near-zero pain. The mutation/edit surface and the post-create
workflow discoverability carry the residual friction. Drive a
bounded fix wave (tracked task: P06 re-test fix wave):

1. `profile edit` becomes a true patch — write only explicitly
   supplied fields; preserve the rest. Add `--set key=value`.
2. Zero-significant identifier fields (postcode) typed and stored as
   strings, never `int`-coerced.
3. Audit the wizard `profile create` atomic-create path for the
   pointer-without-record torn state; guarantee all-or-nothing.
4. Restore the `--version` / `--help` fast-path (P04) — bypass
   browser-adapter and settings construction for trivial dispatch.
5. `profile create` emits the active-profile line; validate
   `--activity`; fix the `modelo casillas` UTF-8 encoding; gate
   `repair logs` DB-read behind a session; add `profile import
   --target-id`; resolve `live portals list` labels.
6. UX: stop truncating flag names; fix `profile list` description;
   strip the internal key path from the NIF error; honour
   `output_language` on every refusal; translate `repair integrity`;
   reorder the wizard-refusal recovery hint.
7. Robustness: make `ExternalConstants` / browser-defaults
   initialisation lazy (flag to the external-constants campaign).
8. After the fix wave, re-run the 5-persona blind re-test; the
   campaign closes when mean pain is near zero.

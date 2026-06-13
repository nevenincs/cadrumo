---
tags:
  - '#audit'
  - '#profile-lifecycle-disaster'
date: '2026-05-20'
modified: '2026-05-20'
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

## Round 2 re-test — invalidated

The round-2 re-test (post-#49 fix wave) scored a mean ~7.2/10, a
regression from round 1. The regression was conclusively attributed
to two foreign concurrent-campaign crashes, not the feature: a
CLI-wide `ExternalConstants` model/data drift crash (tracked and
fixed as #55) and a transient `ImportError` from the
profile-UUID-identity campaign's mid-edit working tree. Every round-2
persona independently confirmed the #49 fixes themselves were sound
in-scenario (edit-patch worked, postcode `08001` preserved, data
isolation held, error paths clean). Round 2 is therefore discarded as
a feature measurement; round 3 is the genuine post-#49 reading.

## Round 3 re-test — close measurement

Five blind operator personas, each in an isolated clean install
(`AEAT_LOCAL_STORAGE_ROOT` set to a fresh directory — no stale
buckets), operated the `aeat` CLI after the #55 crash fix and the
round-2 non-crash UX fix wave (#56) had landed.

### Pain scores

- newcomer: 2/10.
- returning: 2/10.
- dual: 3/10.
- fumbler: 2/10.
- curious: 2/10.
- Mean: 2.2/10 — "low". Down from the round-1 4.6 "moderate" and the
  original "heavy" baseline.

### What is confirmed fixed

- Zero raw Python tracebacks across all five sessions, including the
  fumbler's 30+ deliberate abuse cases. Error handling is a settled
  strength.
- `ExternalConstants` crash gone — `--help` on every lifecycle verb
  (`profile census`, `modelo work verify` / `file` / `audit` /
  `amend`) returns clean help, no `ValidationError`.
- Portal catalogue resolved — all 42 portals show real translated
  names; zero raw `Label NNNNNN` stubs.
- `profile edit` is a true single-field patch — unsupplied fields
  preserved, `output_language` not flipped, confirmed with and
  without `--accept-defaults`.
- Postcode `08001` round-trips with its leading zero intact.
- Profiles are identified by display name; the UUID is a secondary
  field, not the display identity.
- `overview status` renders in English under an `output_language=en`
  profile.
- Numeric-enum flags carry inline legends; help tables no longer
  truncate flag names; data isolation between profiles holds; atomic
  create leaves no torn pointer-without-record state.

### Residual findings — MEDIUM

- `modelo work create` accepts a nonexistent modelo code (`999`) and
  a nonexistent revision id without registry validation; `calculate`
  then silently falls back to modelo-303 defaults. A data-integrity
  gap — work-unit creation must validate modelo and revision against
  the registry.
- A year out of range (`1899`) is silently prepended to the period
  token and surfaces only the generic "command input failed
  validation — run `aeat config repair`" message, in English, never
  naming the year as the bad value.
- Two profiles can be created with the same tax id; no duplicate-NIF
  detection.
- The postcode field accepts arbitrary text (`BADPOST`, `99999`); no
  Spanish 5-digit postcode format validation.
- Creation-time errors render in Spanish even when `--output-language
  en` is supplied on the create command line — the flag is available
  at parse time and should be honoured before the profile exists.
- `did-you-mean` does not fire for `modify` (-> `edit`) or
  `aeat app status` (-> `aeat app overview status`).
- `overview status` prose appends the raw UUID in parentheses next to
  the display name — noise for an end user.
- `config repair connectivity` row keys render with a trailing
  "label" word (`Target label`, `State label`) — an i18n key
  `.label` suffix bleeding into the resolved string.

### Residual findings — LOW

- `aeat config profile` with no subcommand exits 2 instead of
  defaulting to a useful view.
- `modelo work discard` has no confirmation gate, asymmetric with
  `delete`.
- `modelo work amend` reports missing required options one at a time.
- `modelo describe --period 0A` rejects `0A` though the modelo-100
  registry declares `0A` as a valid period.
- `--tax-residence-ccaa` choice list wraps mid-bracket in the help
  table.
- `modelo list` titles render without accents (`declaracion`) —
  registry source-data issue, cross-campaign to schema-hardening, not
  a display encoding bug.

## Verdict

Operator pain fell from "heavy" to 4.6 (round 1) to 2.2 (round 3).
The campaign has not reached the near-zero close criterion: every
persona scored 2-3, a consistent residual band of UX polish plus a
small number of MEDIUM validation / data-integrity gaps. Drive one
more bounded fix wave (tracked task: R3 residual fix wave) over the
MEDIUM and LOW findings above, excluding the cross-campaign
registry-data accent issue, then re-run the 5-persona blind re-test.
The campaign closes when mean pain is near zero.

## Round 4 re-test — campaign close

Five blind operator personas, isolated clean installs, re-tested the
`aeat` CLI after the round-3 residual fix wave landed.

### Pain scores

- newcomer: 1/10.
- returning: 3/10.
- dual: 1/10.
- fumbler: 1/10.
- curious: 1/10.
- Mean: 1.4/10 — near-zero.

### Trajectory

Original baseline "heavy" -> round 1 4.6 -> round 3 2.2 ->
round 4 1.4. (Round 2's ~7.2 stays discarded — it measured a foreign
concurrent-campaign crash, not the feature.)

### Round-3 fixes confirmed by the personas

Every round-3 residual fix was independently verified in-scenario:
`modelo work create` now refuses an unknown modelo or revision and
names the valid set; an out-of-range year is refused naming the bad
year in the operator's language; a duplicate tax id is refused naming
the existing profile; malformed postcodes are refused with the
province-range rule; `modelo work discard` is gated behind `--yes`
with the exact re-run command; `modelo work amend` batch-reports all
missing flags; `modelo describe --period 0A` is accepted;
`config repair connectivity` row labels render clean; help tables do
not truncate and the CCAA choice list wraps cleanly; portal labels
all resolve; did-you-mean covers the new synonyms. Zero raw Python
tracebacks across all five sessions, including the fumbler's 23
deliberate abuse cases.

### Residual findings — for the round-4 fix wave

- `aeat_database_url` does not derive from `aeat_local_storage_root`:
  setting the storage root alone yields `aeat_database_url is empty`
  on first contact (four of five personas). Some cold-start command
  paths (`modelo work list` with no profile) leak this raw config
  error instead of the clean no-active-profile refusal that
  `ledger list` gives. The two settings must be coherent and no path
  may surface the raw empty-URL error.
- M100 annual period-token confusion: `--year 2024 --period 2024`
  is internally joined to `2024-2024` and refused with an opaque
  message; the annual token `0A` is not surfaced in the error.
- `profile edit` in a non-interactive context refuses with a recovery
  hint pointing at `profile create` (reads as destructive) rather
  than `profile edit NAME --quiet ...`.
- `overview status` greets by profile slug rather than the stored
  human identity name (debatable — the slug is the profile identity).
- LOW: `aeat --version` cold start ~2.7s (tracked separately as the
  lazy-registration task); `live filed list` accepts only `1` not
  `true`; `modelo work verify` wraps a workflow-gate refusal in a
  Click `Invalid value:` header; `modelo describe` period errors do
  not enumerate model-specific tokens; `config repair` labels stay
  Spanish under an English profile.

## Campaign close verdict

Operator pain fell from "heavy" to 1.4/10 — near-zero. The
profile-lifecycle disaster-recovery campaign has met its close
condition. Error handling, cold-start refusals, destructive-action
safety, the command-surface map, atomic create, true single-field
edit, registry-validated work creation, and provenance-preserving
output are all settled strengths confirmed across four re-test
rounds. The campaign is converged. The round-4 residual findings
above are handed to one final bounded fix wave and thereafter to the
ongoing codebase-health hardening cadence — they are polish on a
sound feature, not disaster-recovery work.

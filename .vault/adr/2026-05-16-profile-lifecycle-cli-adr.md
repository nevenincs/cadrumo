---
tags:
  - "#adr"
  - "#profile-lifecycle-cli"
date: "2026-05-16"
related:
  - "[[2026-05-16-profile-lifecycle-cli-research]]"
  - "[[2026-05-14-profile-bucket-lifecycle-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-14-secure-backend-passkey-custody-adr]]"
---

# `profile-lifecycle-cli` adr: operator-facing profile lifecycle, cryptic-verb retirement, and persistence-boundary cleanup | (**status:** `accepted`)

## Problem Statement

The shipped `aeat config` profile surface fails the first
non-technical operator who tries to use it. A live transcript of a
self-employed autónomo (no technical background) attempting to
create a second profile surfaced multiple defects in one session:

- The verb the operator instinctively looks for, `aeat config
  profile create`, does not exist. The actual creator is
  `aeat config init`, a name no kitchen-table user associates with
  "create a new profile". The operator does not say "init a new
  chapter" or "init a new account".
- `aeat config init` collapses three intents into one command
  (bootstrap, create, edit) and silently overwrites the active
  profile when invoked a second time with the default
  `--profile default`.
- The top-level `aeat config --help` summary advertises only four
  of eleven profile verbs, hiding `use`, `view`, `validate`,
  `preflight`, `status`, `remove`, and `duplicate` from operator
  discovery.
- Multiple shipped verbs use engineering jargon the operator
  cannot decode: `lock`, `unlock`, `validate`, `preflight`,
  `use`, `init`, `duplicate`. None reads as plain 2026 English.
- Three accepted ADRs overlap this surface and contradict each
  other. The May-12 `config-init-shape` ADR locks the
  silent-overwrite `init` behaviour without addressing it. The
  May-13 `config-profile-use-and-status` ADR adds
  `profile use` as an alias. The May-14
  `profile-bucket-lifecycle` ADR removes `profile use` and
  introduces an even larger jargon surface (`switch <bucket-id>`,
  `list-buckets`, `delete-bucket`, `export-bucket`,
  `import-bucket`, `lock`, `unlock`). The word `bucket` is
  engineering jargon no operator decodes.
- Six persistence-boundary findings on the same path (manifest /
  SQL row write-order non-atomicity, `WorkflowState.invoice_reviews`
  and `ledger_reviews` typed-envelope drift,
  `ProfileLifecycleService._iter_profiles` encapsulation breach,
  absent anti-tautology probe test on the profile boundary,
  shipped active-profile state encrypted instead of plaintext,
  dev-shaped `aeat config repair list NAMESPACE` on the operator
  surface) must close in the same rework, not as follow-ups.

The redesign must replace every cryptic verb with plain English,
collapse the active-profile state model to a single source of
truth, fold the May-14 architectural foundation (per-profile
storage slice, per-profile password, per-profile recovery code,
in-memory session lifecycle) into the same execution, de-conflict
and supersede the May-12 and May-13 ADRs, and land all six
backend findings together. No shims, no aliases, no follow-up
tickets, no deprecation warnings.

## Considerations

The operator the CLI serves is a Spanish autónomo or gestoría
clerk filling out paper tax forms in their working life. They
read CLI help text as instructions in a foreign language. Every
verb that does not pass the kitchen-table test — would a
non-technical relative understand this word in this context? —
is friction at the first interaction.

The comparable-tool survey (`2026-05-16-profile-lifecycle-cli-research`,
§5) shows the dominant lifecycle pattern across `gh`, `gcloud`,
`kubectl`, and `docker context` is `create` → switch verb →
`list` / read verb. Those tools serve engineers; their vocabulary
(`init`, `use-context`, `activate`) is acceptable to that
audience. The AEAT CLI cannot assume the same audience.

Plain-English alternatives exist for every shipped jargon verb
and decode without context:

- `init` → `create` (operator wants to make a new profile).
- `use` / `set active` / `switch <bucket-id>` → `switch` (the
  operator says "switch to my catering profile").
- `lock` / `unlock` → `logout` paired with `switch`'s implicit
  login (the universal 2026 vocabulary; Slack, Gmail, every
  SaaS uses this exact word for the same concept).
- `validate` + `preflight` → folded into `show` (the operator
  asks "what's in my profile" and the answer prominently flags
  anything missing). Filing-readiness `preflight` is a filing
  question, not a profile question, and moves under
  `aeat app modelo *` where it belongs.
- `view` + `status` → folded into `show` (one read verb that
  answers both "what's in this" and "is it ready").
- `duplicate` → `create --copy-from NAME` (the operator says
  "create a new profile based on the catering one").
- `remove` / `delete-bucket` → `delete` (universal English).
- `backup` / `restore` and `export-bucket` / `import-bucket` →
  `export` / `import` (the operator says "export my profile to
  a file"; this matches the operation, not the metaphor).
- `history` → moved to the engineer surface (`python -m
  aeat.diagnostics activity NAME`); not an operator concern, and
  "history" applied to a profile reads ambiguously in English.
- `bucket` as a structural noun on the operator CLI →
  eliminated. The word survives only in code, log lines for
  engineers, and the engineer-surface module entrypoints.

The May-14 ADR's terminology mandate (`profile` is the
user-facing identity; `bucket` is the encrypted storage slice
behind it) is honoured by extending it past where May-14 itself
stopped: the May-14 ADR added five `bucket`-named verbs on the
operator CLI (`list-buckets`, `switch`, `delete-bucket`,
`export-bucket`, `import-bucket`), which violates its own
mandate. This ADR completes the discipline.

Active-profile state has a chicken-and-egg problem the shipped
code does not solve. The current `WorkflowState.active_profile`
field lives inside the encrypted secure-object row, which means
the system has to be unlocked already to learn which profile to
unlock. The May-14 ADR §5 fixes this with a plaintext pointer
file at `<aeat-root>/active-bucket`; this ADR adopts that
mechanism and renames the file to `<aeat-root>/active-profile`
to keep the operator vocabulary consistent.

The May-14 architectural foundation (per-profile directory
layout, per-profile keystore, per-profile passphrase, per-profile
recovery code, `BucketSession` in-memory key material lifecycle,
explicit teardown on switch / logout, per-profile filesystem
lockfile, legacy `var/` refusal) is accepted but not yet
executed in code. The shipped surface still exposes
`profile use`, `profile duplicate`, `profile remove`,
`--profile` overrides on every google adapter verb,
`Settings.aeat_default_profile_name`, `WorkflowState.active_profile`,
and `ProfileBucketPointer`. This ADR folds the May-14
foundation into the same execution as the operator-surface
rework — partial states are forbidden by the project mandate.

## Constraints

The May-14 `profile-bucket-lifecycle` ADR's architecture remains
in force in its entirety: 1:1 profile↔bucket cardinality,
per-profile directory layout under `<aeat-root>/buckets/<bucket-id>/`,
per-profile KEK and Argon2id schedule, per-profile recovery
mnemonic, per-profile keystore, per-profile lockfile, in-memory
`BucketSession`, explicit teardown on switch, no backwards
compatibility for legacy `var/` layout, no migration tooling.
This ADR adopts those decisions unchanged and changes only the
operator-facing vocabulary surfaced on top.

The May-12 `config-init-shape` ADR is marked **superseded** by
this ADR. Its surviving non-conflicting decisions are lifted:
interactive prompts directly on the create wizard for omitted
fields, no separate `wizard` subcommand, atomic profile + storage
creation, every CLI command emits through `_emit`, every CLI
command supports `--format json|text`, the post-command
next-step hint rule (hints point at leaf verbs, never groups),
and the bucket-event-history emission contract on every
persisting verb.

The May-13 `config-profile-use-and-status` ADR is marked
**superseded** by this ADR. Its `profile use` alias is
extinguished — the canonical verb is now `switch`. Its
`list --with-status` enrichment columns (`last_activated_at`,
`draft_work_units_count`, `verified_unfiled_count`,
`last_filed_at`, `last_event_at`) are lifted into the new
`profile list` and `profile show` verbs. The May-13 ADR's
discoverability-hint contract is preserved.

The CLI root contract (exactly `aeat config` and `aeat app`, no
third surface) is inherited unchanged. The locale-via-CLI
mandate applies to every rename. The factory-direct mandate
applies: commits land on `chore/eliminate-shims`, no PRs, no
destructive git, no skip-hooks; every removed verb deletes in
the same commit as its replacement lands.

The roundtrip-discipline rule mandates an anti-tautology probe
on the new boundary. The calculation-grounding rule forbids
`dict[str, Any]` and `cast(...)` at boundaries. Both apply.

## Implementation

### 1. Operator-facing CLI surface — ten verbs under `aeat config profile`

The entire operator surface for profile management is exactly
the verbs below. The `profile` noun is the only operator-facing
storage-related noun in the CLI. `bucket` never appears.

```text
aeat config profile create NAME            new profile + activates it; prompts password
aeat config profile switch NAME            switch active profile; prompts password
aeat config profile logout                 sign out of active profile
aeat config profile list                   one-line summary of every profile
aeat config profile show [NAME]            display values; defaults to active
aeat config profile edit [NAME]            re-run wizard; defaults to active
aeat config profile rename NAME NEW        rename a profile
aeat config profile delete NAME            delete profile + its storage; double-confirm
aeat config profile export [NAME] --to F   write encrypted backup; defaults to active
aeat config profile import F               restore from encrypted backup
```

Verb-by-verb semantics:

- `create NAME` — interactive wizard for all profile fields
  (NIF, surnames, activity, IVA regime, tax residence CCAA,
  output language, drafts/submissions/manuals paths, etc.).
  Prompts for omitted required fields. Prompts the operator
  to choose a password — this password derives the
  Argon2id-wrapped KEK for the new profile's encrypted storage
  per the May-14 design. Optional `--copy-from NAME` clones
  operator-facing facts from an existing profile (replaces
  the deleted `duplicate` verb). Refuses if NAME collides
  with an existing profile. On success, the new profile is
  active; the plaintext pointer file is updated; the
  in-memory session is created and the operator can use the
  CLI immediately. Emits `profile.created` and
  `profile.activated` bucket events.

- `switch NAME` — switches the active profile. If a session
  is currently open, it is closed first (`BucketSession`
  teardown per the May-14 §6 contract — engine close, key
  material zeroised, adapter handles released). Prompts the
  operator for NAME's password, derives the KEK, opens a new
  `BucketSession`, updates the plaintext pointer file. The
  CLI does not require a separate "login" verb — `switch`
  always implies login. Emits `profile.activated` on the new
  profile.

- `logout` — closes the active in-memory `BucketSession`,
  zeroises key material, releases adapter handles. The
  plaintext pointer file is **not** modified — the configured
  default profile remains the same; the operator has only
  signed out of the current session. Next CLI invocation
  resolves the active profile from the pointer file and
  prompts for the password. Emits no bucket event (this is a
  session-state change, not a persisted mutation).

- `list` — one row per profile. Default columns:
  `name`, `active`, `last_switched`, `missing_fields_count`.
  With `--with-status` adds the May-13 enrichment columns:
  `last_activated_at`, `draft_work_units_count`,
  `verified_unfiled_count`, `last_filed_at`, `last_event_at`,
  all derived from bucket-event-history without new storage.
  Reads manifests only — does not unlock any profile.
  Operates correctly even when the operator is logged out.

- `show [NAME]` — defaults to the active profile when NAME is
  omitted. Displays every operator-visible field of one
  profile. Header line carries the profile name plus an
  active / inactive marker and a missing-fields warning if
  any required field is empty. Body renders every field. JSON
  output (`--format json`) includes `valid: bool` and
  `missing: [field, ...]`. Requires unlock when NAME is the
  active profile and a session is open; refuses with
  `ProfileLockedError` when the operator must `switch` to it
  first.

- `edit [NAME]` — defaults to the active profile. Re-runs the
  wizard against the existing profile's facts; presents
  current values as defaults; prompts for each field. Emits
  `profile.updated`.

- `rename NAME NEW` — renames a profile in the manifest, in
  the pointer file (if active), in the keystore key alias,
  and in every reference. NAME and NEW both required to
  prevent ambiguity. Refuses if NEW collides.

- `delete NAME` — destroys the profile, its encrypted SQL
  row, its keystore entry, its on-disk directory, and its
  pointer-file reference if active. Double-confirm: `--yes`
  flag plus the operator types NAME back verbatim at a
  second prompt. NAME is **always required** — never
  defaults to active. Emits `profile.deleted`.

- `export [NAME] --to FILE` — defaults to the active profile.
  Writes a sealed archive containing the profile's ciphertext
  tree, its `manifest.toml`, and its recovery-wrapped key.
  Does **not** include the passphrase or the unwrapped master
  key. Without the password or the recovery code, the archive
  is inert. Emits `profile.exported`.

- `import FILE` — registers a sealed archive as a new
  profile. The profile is visible in `list` but locked until
  the operator runs `switch <name>` against it and types the
  password (or recovery code). Refuses if the archive's
  profile id collides with an existing profile. Emits
  `profile.imported`.

### 2. Default-to-active rule

Verbs that operate on one profile and accept `[NAME]` default
to the active profile when NAME is omitted: `show`, `edit`,
`export`. The rule is documented once in `aeat config profile
--help` and signposted in every per-verb help.

Verbs that always require NAME: `create`, `switch`, `rename`,
`delete`. Reasons: `create` and `switch` target a non-default
profile by definition; `rename` reads confusingly with an
implicit subject; `delete` must never silently destroy the
active profile.

Verbs that take no NAME: `logout`, `list`, `import`.

### 3. Active-profile state model

Two pieces of state, with deliberately different lifetimes
and locations.

**Persistent (plaintext, on disk):** `<aeat-root>/active-profile`
— a one-line plaintext file containing the active profile name.
Survives between runs. Not sensitive — the name is a label the
operator chose. Plaintext is required because the system must
know which profile to ask the password for *before* any
unlock occurs.

Precedence chain when resolving the active profile (May-14 §5,
renamed to operator vocabulary):

1. `--profile NAME` CLI flag (per-invocation; never persisted).
2. `AEAT_ACTIVE_PROFILE` environment variable (per-shell;
   useful for CI and headless invocations).
3. `<aeat-root>/active-profile` pointer file (canonical
   default for interactive sessions; written only by `switch`,
   `create`, `delete`, `rename`, `import`).

If none resolves, the CLI refuses with a typed
`NoActiveProfileError`. The message lists known profiles and
points the operator at `aeat config profile switch NAME`.

**Ephemeral (in-memory only):** the unlocked key material for
the active profile lives in a `BucketSession` object inside
the running process. Holds the derived KEK, the SQLAlchemy
engine, the storage adapter providers, and any
bucket-scoped memoisation. Dies on `logout`, on `switch`
(replaced by the new profile's session), or on process exit
(via the existing atexit hook). Never persisted. Never
written to the OS keychain by default.

`WorkflowState.active_profile` is **removed**. Every read of
the active profile flows through the precedence chain.
`Settings.aeat_default_profile_name` is **removed** —
fallback is the pointer file, not a setting. The Google
adapter `_profile_binding.py` `--profile` override is
**removed**. The `--profile` flag on every
`aeat config google ...` verb is **removed**. Active-profile
selection is one chain, one source of truth.

### 4. Cryptic-verb retirement

Every verb in the shipped surface that fails the
kitchen-table test is removed and replaced. No aliases, no
deprecation warnings, no help-text breadcrumbs. The deletion
lands in the same commit as the replacement. Mapping:

```text
Shipped verb           Replacement
-----------------------+------------------------------------
aeat config init       aeat config profile create NAME
profile use NAME       profile switch NAME
profile duplicate ...  profile create NAME --copy-from SRC
profile remove NAME    profile delete NAME
profile validate       (folded into profile show)
profile preflight ...  (moved to aeat app modelo *)
profile view NAME      (folded into profile show)
profile status         (folded into profile show)
profile set / get /    (moved to python -m aeat.diagnostics
  unset KEY               profile set / get / unset)
config repair list NS  (moved to python -m aeat.diagnostics
                          secure-objects list)
```

May-14 verbs that this ADR renames to operator vocabulary
before they ever ship:

```text
May-14 verb (unshipped)    This ADR's verb
---------------------------+----------------------------------
aeat config list-buckets   aeat config profile list
aeat config switch <id>    aeat config profile switch NAME
aeat config delete-bucket  aeat config profile delete NAME
aeat config export-bucket  aeat config profile export NAME
aeat config import-bucket  aeat config profile import FILE
aeat config lock           aeat config profile logout
aeat config unlock         (collapsed into profile switch)
```

### 5. Engineer surface — `python -m aeat.diagnostics`

Verbs that serve engineers, forensic auditors, or scripted
automation do not belong on the operator CLI. They live under
a module entrypoint:

```text
python -m aeat.diagnostics profile get KEY [--profile NAME]
python -m aeat.diagnostics profile set KEY VALUE [--profile NAME]
python -m aeat.diagnostics profile unset KEY [--profile NAME]
python -m aeat.diagnostics profile activity [NAME]
python -m aeat.diagnostics secure-objects list [NAMESPACE]
```

The operator CLI never advertises these. The diagnostics
entrypoint produces JSON by default (for scripting) and
supports `--format text` for ad-hoc engineer use.

### 6. Show readiness folding

The dropped `validate` and the dropped `status` verbs both
answered fragments of "is this profile ready?". `show` carries
the full answer:

- Header line: `<name>   <active|inactive>` followed by, when
  any required field is empty,
  `⚠ <N> field(s) missing`.
- Body: every field with its value or `(not set)`.
- Footer: password-set indicator, created timestamp, last
  switched timestamp.
- JSON envelope: `{name, active, valid: bool, missing: [...],
  fields: {...}, metadata: {...}}`.

No separate readiness verb. The operator asks "show me this
profile" and gets the answer including readiness.

### 7. Persistence-boundary cleanup

Six findings ride the same execution as the CLI rework.

**7.1 — Manifest / SQL row write-order atomicity.** Today the
manifest is written before the encrypted SQL row, so a crash
between them leaves an addressable directory with no profile
record. New order: open a SQLAlchemy transaction; write the
encrypted SQL row inside it; write the manifest to a tmp path;
commit the transaction; rename the tmp manifest to the final
path. A crash before the rename leaves the row but no
operator-visible manifest, detectable by orphan-scan; a crash
after the rename is the successful steady state.

**7.2 — `WorkflowState.invoice_reviews` / `ledger_reviews`
typed-envelope drift.** The `dict[str, object]` union arm on
both fields collapses to the typed arm. Strict pydantic
validation at boundary load surfaces corruption rather than
silently degrading. The roundtrip test is extended to populate
both fields with non-default values.

**7.3 — `_iter_profiles` encapsulation.**
`UserProfileLifecycleRepository` gains a public
`iter_records()` method. The lifecycle service consumes the
public surface; private `_objects` access is removed.

**7.4 — Anti-tautology probe test.** A new test saves a
populated profile record, mutates the encrypted payload on
disk to delete a required field, reloads, and asserts
`ValidationError` raised or strict inequality. Real
`EphemeralMasterKeyProvider`, real SQLite engine, no mocks.

**7.5 — Active-profile state moves out of encrypted SQL.**
`WorkflowState.active_profile` deleted; `<aeat-root>/active-profile`
plaintext pointer file introduced; precedence chain authoritative.
(Inherits the May-14 §5 decision, applied with renamed
filename.)

**7.6 — Dev-facing `repair list NAMESPACE` retirement.** The
verb leaves `aeat config repair` and lands as
`python -m aeat.diagnostics secure-objects list`. The other
`repair` verbs (`logs`, `quarantine`, `reset-state`,
`integrity`, `connectivity`) stay — they are operator-facing
diagnostic flows.

### 8. May-14 foundation work absorbed into this execution

The May-14 ADR's architectural decisions remain authoritative
but unexecuted in code. This ADR commits to landing them in
the same plan as the operator-surface rework. Concrete items
(not exhaustive — see May-14 §"Code rewrites required" for the
full list):

- `ProfileBucketPointer` → `BucketPointer` rename in
  `application/workflow/_models.py`.
- `WorkflowState.active_profile` removed (replaced by pointer
  file + precedence chain).
- `Settings.aeat_default_profile_name` removed.
- `_acquisition_lock.py` and `_sessions.py` re-keyed to read
  the active profile from the precedence chain.
- Google adapter `_profile_binding.resolve_active_profile`
  loses its `profile_override` parameter; reads chain only.
- Every `aeat config google ...` verb loses its `--profile`
  flag.
- Per-profile directory layout under
  `<aeat-root>/buckets/<bucket-id>/{db,blobs,audit}/`
  introduced; legacy interleaved `var/` is refused on
  startup with `LegacyLayoutDetectedError`.
- `KeyringMasterKeyProvider._cache` and
  `FileFallbackMasterKeyProvider._cached_passphrase` /
  `_cached_master_key` (ClassVar caches) replaced with
  per-process `BucketSession` instance state.
- Per-profile SQLite engine teardown on switch / logout.
- Per-profile filesystem lockfile at
  `<aeat-root>/buckets/<bucket-id>/.lock`.
- Per-profile passphrase and per-profile BIP-39 recovery
  mnemonic.
- Google Drive mirror folder renamed `aeat-vault/` →
  `aeat-profile/` (operator-facing copy; storage-layer code
  continues to call the slice a `bucket`).

### 9. Locale strings

Every operator-facing string regenerates through
`python -m aeat.locales scaffold` followed by
`python -m aeat.locales audit`. The four catalogues
(es / en / ca / hu) update in the same commit as the verb
rename. No hand-edited yml. Every string that referenced
`profile use`, `profile duplicate`, `profile remove`,
`init`, `bucket`, `vault`, `lock`, `unlock`, `validate`,
`preflight`, `view`, `status`, `backup`, `restore`, or
`history` is rewritten.

### 10. Bucket event coverage

The new verbs emit events into the bucket-event history per
the May-12 bucket-event-history ADR (kept under the
storage-layer noun in the event vocabulary because the audit
log is an engineer surface):

- `profile create` → `bucket.created`, `profile.created`,
  `profile.activated`.
- `profile create --copy-from` → adds `profile.cloned`.
- `profile edit` → `profile.updated`.
- `profile switch` → `bucket.session.closed` on the previous
  profile (if any), `profile.activated` on the new one.
- `profile logout` → `bucket.session.closed` on the active
  profile.
- `profile rename` → `profile.renamed`.
- `profile delete` → `bucket.deleted`, `profile.deleted`.
- `profile export` / `import` → `bucket.exported`,
  `bucket.imported`.

### 11. Single-cut execution

The May-14 no-backwards-compatibility mandate forbids partial
states. The entire rework — the new ten-verb operator surface,
the May-14 foundation, the six backend findings, the locale
regeneration, the engineer-surface entrypoint, and the
supersession marks on the two predecessor ADRs — lands as one
execution plan. Each Step deletes its replaced predecessor in
the same commit it lands. No commit leaves the surface
half-migrated.

## Rationale

The kitchen-table test is the single design rule that produces
the right answer at every choice point. Every accepted verb
passes it: a non-technical relative reading
`aeat config profile create NAME` knows what it does; reading
`aeat config init --quiet --tax-id ...` does not. Every
rejected verb fails it: `init`, `use`, `lock`, `unlock`,
`validate`, `preflight`, `bucket`, `duplicate`. The test is
not subjective once you apply it.

Default-to-active for read / edit / export verbs and explicit
NAME for create / switch / rename / delete maps to operator
intent: when I run `show`, I mean my current profile; when I
run `delete`, I never want it to mean my current profile
implicitly.

Plaintext pointer file for active-profile state resolves the
chicken-and-egg defect documented in the May-14 ADR §5. Every
multi-account application solves this the same way —
usernames remembered plaintext, passwords not. The operator's
mental model already matches.

Folding May-14 foundation work into the same plan honours
both the May-14 no-partial-states mandate and the
operator-direct rule against follow-up tickets. Shipping the
operator-surface rework against a half-built architectural
foundation would land cosmetic improvements on top of a still-
broken state model.

Two supersessions resolve the May-13 vs May-14 collision and
extract the substantive surviving decisions from the May-12
ADR into one coherent surface. The May-14 ADR stays accepted
and authoritative for the architectural foundation; this ADR
extends it with the operator-facing vocabulary the May-14 ADR
did not get right.

The engineer surface (`python -m aeat.diagnostics`) is the
mechanical answer to the operator-CLI-is-not-dev-tooling
mandate. Diagnostic, scripted, forensic, and audit verbs all
have legitimate uses; they belong off the operator surface,
not removed entirely.

## Consequences

### Operator-visible behaviour change

- `aeat config init` ceases to exist. The operator types
  `aeat config profile create NAME` for first profile and
  for every subsequent profile. One verb, no special cases.
- `aeat config profile *` subgroup carries exactly ten verbs:
  `create`, `switch`, `logout`, `list`, `show`, `edit`,
  `rename`, `delete`, `export`, `import`.
- The verbs `use`, `duplicate`, `remove`, `validate`,
  `preflight`, `view`, `status`, `get`, `set`, `unset`,
  `history`, `lock`, `unlock` are gone from the operator CLI.
- The verbs `list-buckets`, `switch <bucket-id>`,
  `delete-bucket`, `export-bucket`, `import-bucket`
  (May-14, unshipped) never appear under those names.
- The top-level `aeat config --help` summary advertises every
  one of the ten profile verbs. No hidden verbs.
- `--profile` on every `aeat config google ...` verb is
  removed. Active-profile selection is one chain.
- The legacy `var/` layout is refused on startup with a typed
  error pointing the operator at `aeat config profile create`.

### Code rewrites

The May-14 ADR's "Code rewrites required" list is inherited
and extended with:

- New `src/aeat/domain/profile/_constants.py` (typed `ProfileName`
  alias; no `DEFAULT_PROFILE_NAME` constant — the literal
  `"default"` is eliminated, not preserved as a constant,
  because `create NAME` always requires an operator-typed name).
- New `src/aeat/application/profile/_lifecycle.py` consolidating
  `create`, `switch`, `logout`, `edit`, `rename`, `delete`,
  `export`, `import`.
- New `src/aeat/application/profile/_active_pointer.py`
  managing the `<aeat-root>/active-profile` plaintext pointer
  file and the precedence chain.
- New `src/aeat/application/profile/_clone.py` implementing
  `--copy-from` with fresh KEK, salt, recovery mnemonic, and
  keystore entry per the May-14 §8 mandate.
- New `src/aeat/application/profile/_errors.py` with typed
  errors (`NoActiveProfileError`, `ProfileLockedError`,
  `ProfileNameCollisionError`, `ProfileNotFoundError`,
  `LegacyLayoutDetectedError`).
- New `src/aeat/entrypoints/cli/_config/_profile.py` mounting
  the ten-verb subgroup.
- Rewrite of `src/aeat/entrypoints/cli/_config/__init__.py`:
  the `profile` subgroup, the `init` command, and every
  legacy lifecycle wiring are deleted in the commit that
  mounts the new subgroup; the top-level `_config_help`
  string is rewritten.
- Public `iter_records()` on
  `src/aeat/application/user_profile/_repository.py`;
  deletion of `_objects` access in
  `src/aeat/application/user_profile/_lifecycle.py:289-295`.
- Removal of the `dict[str, object]` union arms on
  `src/aeat/application/workflow/_models.py:152-153`.
- Reordered manifest / SQL row write in the lifecycle service.
- Anti-tautology probe test at
  `src/aeat/application/profile/test_lifecycle_anti_tautology.py`.
- Removal of `aeat config repair list NAMESPACE` from
  `src/aeat/entrypoints/cli/_config/__init__.py`.
- New `src/aeat/diagnostics/__main__.py` module entrypoint
  with subcommands `profile get|set|unset`, `profile activity`,
  `secure-objects list`.
- Removal of `Settings.aeat_default_profile_name` from
  `src/aeat/application/_settings.py`.
- Re-key of `src/aeat/application/auth/_acquisition_lock.py`
  and `_sessions.py` to read from the active-profile chain.
- Removal of `profile_override` from
  `src/aeat/adapters/outbound/google/_profile_binding.py` and
  every google CLI verb.
- All four locale catalogues regenerated through the locale
  CLI; no hand edits.

### Documentation and vault

- The May-12 and May-13 ADRs carry `superseded by
  [[2026-05-16-profile-lifecycle-cli-adr]]` in their status
  lines. Their bodies remain unmodified.
- The May-14 ADR's status is unchanged. Its `related:`
  field gains a link to this ADR via the curate sweep.
- Historical execution records that contain `aeat config
  init ...` smoke invocations remain unmodified. New smoke
  invocations in this plan use the new surface.
- No README or operator-facing doc surface change is in
  scope here — operator documentation regenerates from the
  CLI help text after this ADR's plan executes.

### Tests

- The full `entrypoints/cli/test_profile_lifecycle_verbs.py`
  test surface is rewritten against the new ten-verb subgroup.
- New tests: bootstrap-already-complete refusal (removed —
  no `init` means no bootstrap-only refusal needed; the
  collision case becomes `profile create NAME`'s
  `ProfileNameCollisionError`), label-resolution for
  `switch` and `delete`, default-to-active behaviour for
  `show` / `edit` / `export`, password-prompt UX, logout
  state-transition, anti-tautology probe, manifest / SQL
  row write-order atomicity, `WorkflowState.invoice_reviews`
  and `ledger_reviews` strict-validation, active-profile
  pointer file precedence chain.

### Operational complexity

- One verb learns the new operator: `aeat config profile
  create NAME`. Every other verb is universal English
  (`switch`, `list`, `show`, `edit`, `delete`, `export`,
  `import`, `logout`, `rename`).
- The operator chooses a password at `create` time; the
  password unlocks that profile on every subsequent `switch`.
  Each profile has its own password. Sharing passwords
  across profiles is not supported.
- Logging out before walking away from the machine is now a
  one-word command (`logout`). The pointer file remembers
  which profile is active; the password does not persist.

### Locale rollout

Four locale catalogues regenerate through the locale CLI in
the same commit. No hand-edited yml. Every operator-facing
string regenerates: command help text, error message
constants, hint footers, status emit lines, password prompts.

### Future considerations

- The May-14 deferred items (Option B.3 OS-keystore-stored
  bucket index, daemon-mode session protocol) remain
  deferred and out of scope.
- A future apex-CLI rework may shorten `aeat config profile
  ...` to `aeat profile ...` once the CLI root contract is
  re-litigated; this ADR does not change the root contract.
- A future password-policy ADR may add complexity
  requirements at `create` time. This ADR ships the
  prompt-and-derive flow; complexity is operator's choice.

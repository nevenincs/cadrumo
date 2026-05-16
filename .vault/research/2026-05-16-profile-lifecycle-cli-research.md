---
tags:
  - "#research"
  - "#profile-lifecycle-cli"
date: 2026-05-16
related:
  - "[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]"
  - "[[2026-05-14-profile-bucket-lifecycle-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
  - "[[2026-04-12-setup-wizard-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-14-secure-backend-passkey-custody-adr]]"
---

# `profile-lifecycle-cli` research: operator-facing profile lifecycle, the `init` overload, and the gap between accepted ADRs and the shipped surface

This research consolidates a live operator transcript (a non-technical
user trying to create a second profile), a four-agent codebase
discovery sweep, and a survey of comparable CLIs into one input for an
ADR that closes the profile-lifecycle UX defect end-to-end. The defect
is not abstract: the operator's first instinct on encountering the
shipped CLI is to look for `aeat config profile create`, finds nothing,
and is forced to discover `aeat config init` — a command that silently
overwrites the existing active profile if invoked without
`--profile <name>`.

Two recently accepted ADRs already overlap large parts of this
problem (`2026-05-12 config-init-shape`, `2026-05-14
profile-bucket-lifecycle`), and one (`2026-05-13
config-profile-use-and-status`) is in direct collision with the May-14
mandate. The shipped surface today predates all three: it still
exposes `profile use`, `profile duplicate`, and `profile remove`, all
of which the May-14 ADR removes. The purpose of this research is not
to re-decide what those ADRs decided, but to surface the gaps they
leave, the conflicts between them, the operator-discoverability
issues none of them address, and the secure-storage drift that
parallel work has uncovered.

## Findings

### 1. Current state — shipped CLI surface and the `init` overload

The shipped CLI defines the `config` group at
`src/aeat/entrypoints/cli/_config/__init__.py:31-37`. The direct
subcommands of `aeat config` are: `init`, `profile`, `auth`,
`apoderado`, `repair`, `bucket`, `google`, `reset`. The `profile`
subgroup carries eleven verbs: `list`, `get`, `set`, `unset`,
`validate`, `preflight`, `use`, `view`, `remove`, `duplicate`,
`status`. There is no `create` or `new`.

The top-level `aeat config --help` summary text lives in
`_config/__init__.py:117-149`. It groups commands into "First run /
Profile / Authentication / Diagnostics" but only advertises four
profile verbs: `list`, `get`, `set`, `unset`. The other seven
(`validate`, `preflight`, `use`, `view`, `remove`, `duplicate`,
`status`) are reachable only by reading `aeat config profile --help`.
A non-technical operator following the top-level help is
unaware that profile switching (`use`) or profile removal (`remove`)
even exist.

`aeat config init` is registered at `_config/__init__.py:706-709` and
delegates to `build_wizard_command(SETUP_FLOW)` at line 29. The wizard
command builder lives at `src/aeat/application/wizard/_commands.py`.
Its signature carries three fixed options (`--profile` defaulting to
the literal string `"default"`, `--quiet`, `--accept-defaults`) plus
forty-plus typed field options (`--tax-id`, `--activity`,
`--iva-regime`, `--tax-residence`, etc.) enumerated in
`_SETUP_OPTION_INFOS` at lines 64-225.

The wizard's behaviour on the active-profile question is what produces
Joan's experience: with `--profile default` (the default), `persist_answers`
in `application/wizard/_persistence.py:88-95` checks whether a pointer
exists. If none exists, it calls `register_active_profile` and creates
a fresh record. If one exists, it calls `set_active_fields` and **edits
the existing record in place**. The CLI does not warn the operator
that they are about to overwrite. There is no `--force` flag and no
confirmation prompt. This is the silent-overwrite defect the operator
transcript surfaced.

`profile duplicate` is at `_config/__init__.py:647-703` and accepts
`SOURCE TARGET` positional arguments plus `--display-name`. The
target must not already exist. It delegates to
`ProfileLifecycleService.duplicate(DuplicateProfileCommand(...))` at
`application/user_profile/_lifecycle.py:187-217`. The semantics:
`source.model_copy(update={...})` produces a new in-memory record;
`repository.save(target)` writes it. The new encrypted SQL row gets a
fresh AES-256-GCM nonce via `secrets.token_bytes(NONCE_SIZE)` at
`adapters/persistence/storage/sql/_crypto.py:128` — so the crypto
hygiene of `duplicate` is correct.

### 2. Current state — callers, blast radius for removal

The discovery agent inventoried every reference to `init` and
`duplicate` in production code, tests, vault docs, scripts, and CI.

Production callers of `init`:

- CLI registration at `entrypoints/cli/_config/__init__.py:706-709`.
- Wizard backend at `application/wizard/_commands.py` (the
  command builder).
- Application service `initialize_workspace` at
  `application/setup/_service.py:12` (delegated by the wizard).

Production callers of `duplicate`:

- CLI verb at `entrypoints/cli/_config/__init__.py:647-703`.
- Application service at `application/user_profile/_lifecycle.py:187-217`.
- Command model `DuplicateProfileCommand` at
  `application/user_profile/__init__.py`.

Test callers (durable production test path under `src/aeat/.../test_*.py`):

- `entrypoints/cli/test_profile_lifecycle_verbs.py:121-138` —
  positive and negative `profile duplicate` invocation tests.
- `application/user_profile/test_lifecycle.py` — unit tests for
  `DuplicateProfileCommand` via the service.
- `entrypoints/cli/test_apex_workflow_verification.py` — verifies
  `_wizard_init_command` is registered through the `__wizard_flow__`
  attribute.

Documentation / vault references: six ADRs document `aeat config init`
as the user-facing onboarding entry point; the canonical shape
authority is the `2026-05-12-config-init-shape` ADR. Multiple plan
documents reference `aeat config init` as the live smoke-test invocation
for fresh profiles. Fifteen-plus execution records contain
`aeat config init --quiet --tax-id ...` invocations. Removing or
renaming these commands requires sweeping the vault references in the
same commit as the code change (no half-done renames, per the project
mandate).

Scripts / CI: no CI workflow file (`.github/workflows/*.yml`) invokes
either verb. No shell scripts or Makefile / justfile usage. Blast
radius outside the vault is contained to four production sites and
four test sites per verb.

### 3. Current state — secure-storage path and persistence-boundary findings

The full call chain for profile creation, traced by the
secure-storage agent:

CLI (`init` or `profile duplicate`) → wizard or service command →
`ProfileLifecycleService.register` / `.duplicate` at
`application/user_profile/_lifecycle.py:75` / `:187` →
`UserProfileLifecycleRepository.save` at
`application/user_profile/_repository.py:117-132` →
`SecureObjectRepository.save` at
`adapters/persistence/storage/sql/secure_objects.py:576`.

The in-memory model is `UserProfileRecord` (typed pydantic v2 record
carrying `tuple[UserProfileFact, ...]`); the persisted form is
`Envelope[UserProfileRecord]` (`adapters/persistence/storage/envelope/_envelope.py`).
The envelope carries `schema_version`, `written_at`, `classification`,
and `payload`. JSON-serialised, encrypted as the ciphertext payload
in the SQL row. Boundary is clean — no `dict[str, Any]` and no `cast(...)`
on the profile lifecycle path.

The SQL row schema (`SecureObjectRow` at
`adapters/persistence/storage/sql/_orm.py:121-146`): `namespace`
(`String(128)`), `object_key` (`HashedLookup` HMAC-SHA256), `classification`,
`schema_version`, `written_at`, `payload` (`EncryptedBytes` — AES-256-GCM
ciphertext, 12-byte nonce prepended). Cipher implementation at
`_crypto.py:27`; nonce generation at `_crypto.py:128`; AAD `b"aeat.column.encrypted_bytes.v1"`
at `_encrypted_columns.py:49`. Master-key provider selection:
`KeyringMasterKeyProvider` (OS keychain) or
`FileFallbackMasterKeyProvider` (Argon2id-wrapped file backend) at
`adapters/persistence/storage/master_key/_master_key.py:88-96`.

The TOML manifest lives at
`<aeat-root>/buckets/<bucket-id>/manifest.toml`
(`adapters/persistence/storage/_manifest_io.py:21-27`,
`_layout.py:62`). The manifest model (`_manifest.py:81-111`) carries
only non-sensitive metadata: `bucket_id`, `label`, `created_at`,
`last_unlocked_at`, `kdf_params`, `recovery_enrolled`,
`schema_version`. Strict frozen pydantic v2 with `extra="forbid"`.

Three concrete persistence-boundary findings that the ADR must
address alongside the UX rework:

**Finding 3.1 — manifest and SQL row are not co-transactional.**
Manifest writes go through `write_manifest` at `_manifest_io.py:86-99`
(write-then-rename); SQL row writes go through the SQLAlchemy session
in `SecureObjectRepository._save_internal_in_session`. There is no
two-phase commit binding the two. A crash between them leaves the
bucket directory with a manifest but no profile row, or vice-versa.

**Finding 3.2 — typed-envelope drift in `WorkflowState`.** Two fields
on `WorkflowState` at `application/workflow/_models.py:152-153` carry
the type `dict[str, InvoiceReviewRecord | dict[str, object]]` and the
same for `ledger_reviews`. The `dict[str, object]` arm is a boundary
escape: a torn or partial payload silently loads as raw dict rather
than raising `ValidationError`. This violates the project rule against
`dict[str, Any]`-equivalent leakage at persisted boundaries, and it
sits on the same encrypted secure-object row as the active-profile
pointer map — so the profile-lifecycle boundary inherits the drift.

**Finding 3.3 — encapsulation breach in `_iter_profiles`.**
`ProfileLifecycleService._iter_profiles` at
`application/user_profile/_lifecycle.py:289-295` reaches into
`self._repository._objects` (private attribute access) to iterate
existing profiles. Not a type-system escape, but a layer violation
that complicates the service contract a future `profile create`
verb will need to reason about (collision detection on the new name).

**Finding 3.4 — no anti-tautology proof test for the profile
boundary.** A thorough roundtrip test exists at
`application/user_profile/test_repository_roundtrip.py:89-139`
(real master-key provider, real SQLite engine, non-default fields,
strict pydantic equality). What does not exist is the
roundtrip-discipline anti-tautology probe: save, mutate the on-disk
payload to delete a field, reload, and assert either
`ValidationError` or strict inequality. Without it, the existing
roundtrip's correctness proof carries no proof that a regression
into broken-boundary behaviour would surface as test failure.

**Finding 3.5 — `"default"` profile name is a hard-coded string.**
`build_wizard_command` at `application/wizard/_commands.py:434-435`
defaults `profile_name` to the literal string `"default"`. There is
no domain constant, no `BucketIdConstants.DEFAULT`, no typed alias.
A rename of the string in one place silently creates a new bucket
on the next invocation.

**Finding 3.6 — no shadow-default representation.** A vanilla install
has `WorkflowState()` with `active_profile=None` and `profiles={}`
(`application/workflow/_persistence.py:63-64`). There is no profile
record on disk until `init` runs. There is no concept of "ready-but-
empty shadow profile" — the operator-facing surface has nothing to
show between install and first `init`. The `profile status` verb
reports a not-configured state via `WorkflowStateRepository.load` and
the user-profile readiness aggregator, but there is no
`profile.shadow == True` discriminator on the manifest or the record.

### 4. Accepted ADRs that overlap this work, and the conflicts between them

The May-12 `config-init-shape` ADR locks the surface
`aeat config init [--profile NAME] --tax-id NIF --activity TEXT ...`
as the first-run command. It mandates interactive prompts for omitted
fields directly on `init` ("There is no `wizard` subcommand"). It
forbids aliases, deprecation routes, and `aeat config init wizard`.
It mandates atomic bucket-and-profile creation with bucket events
(`bucket.created`, `profile.created`, `profile.activated`,
`profile.updated`). It does not address: a `profile create` verb for
creating a second profile after first-run, a `profile edit` verb for
re-running the wizard against an existing profile, or the
silent-overwrite-on-second-`init` behaviour the operator transcript
exposes.

The May-13 `config-profile-use-and-status` ADR adds
`aeat config profile use NAME` as an alias of `set active NAME` and
extends `aeat config profile list` with a `--with-status` column set.
It explicitly preserves `profile use` and the existing profile-list
shape.

The May-14 `profile-bucket-lifecycle` ADR is execution-ready and is
the largest reframe in flight. It mandates: 1:1 profile↔bucket
cardinality with `bucket_id` as the single identifier;
`ProfileBucketPointer` → `BucketPointer`; `WorkflowState.active_profile`
→ `active_bucket_id`; per-bucket directory layout; per-bucket
keystore; per-bucket passphrase and recovery code. It adds five new
`aeat config` verbs: `list-buckets`, `switch`, `delete-bucket`,
`export-bucket`, `import-bucket`. **It removes `profile use`,
`profile duplicate`, `profile remove`, and the `--profile`
override on every `aeat config google ...` verb.** No backwards
compatibility, no migration tooling.

The collision: May-13 mandates `profile use`; May-14 removes
`profile use` and replaces it with `switch` at the `config` root.
Both are accepted. The later ADR (May-14) carries the day on date
ordering and on scope (May-14 is execution-ready and addresses the
deeper architectural defect), but the May-13 ADR's status field
has not been updated to `superseded`. This must be resolved before
the new ADR lands.

The May-14 ADR does not, however, surface the operator-discoverability
finding from the live transcript. It assumes `aeat config switch
<bucket-id>` is sufficient — but `<bucket-id>` is a system identifier,
not a human display name. The operator who types `aeat config list-buckets`
gets `bucket_id`, `label`, `last_unlocked_at`, `recovery_enrolled` and
must then re-type or copy `bucket_id` into a `switch` call. The
`profile use NAME` form was kinder to humans precisely because NAME
was the display name. The new ADR also has no `create-bucket` verb —
new bucket creation goes through `aeat config init`, which inherits
the same "is this create or edit?" overload from the May-12 shape.

### 5. Comparable-tool patterns

The CLI-pattern survey across `gh`, `aws`, `gcloud`, `kubectl`, and
`docker context` confirms a single dominant pattern: a three-verb
lifecycle of `create` (or `login` / `configure`) → `use` / `activate` →
`list` / `describe`, with `init` reserved exclusively as a one-time
interactive bootstrap that creates an implicit `default` entry.

`gh auth login` creates and `gh auth switch` switches; there is no
`gh init`. `aws configure --profile NAME` creates and writes a stanza
into `~/.aws/config`; there is no `use` verb — switching is via
`--profile NAME` or `AWS_PROFILE`. `gcloud config configurations create
NAME` creates and `gcloud config configurations activate NAME`
switches; `gcloud init` is the bootstrap wizard that creates and
activates an implicit `default` configuration on first run. `kubectl
config use-context NAME` switches and `set-context` composes from
prior cluster/user entries. `docker context create NAME` and
`docker context use NAME` mirror the gcloud / kubectl form exactly.

The synthesis: the AEAT CLI should follow the gcloud / Docker /
kubectl consensus. `<noun> create NAME` to write a new record,
`<noun> use NAME` (or `switch NAME`) to activate, with explicit
`--from <existing>` to replace duplicate. `init` is the one-time
bootstrap wizard, not the canonical creator. The one notable
exception is AWS, which conflates creation and bootstrap into one
overloaded `aws configure` command — exactly the anti-pattern the
shipped AEAT CLI inherits.

The May-14 ADR partially follows this pattern (`switch` is the
gcloud `activate` equivalent; `delete-bucket` mirrors `docker
context rm`) but breaks it on creation: `aeat config init` is
overloaded to handle both bootstrap and named creation. The AWS
anti-pattern carries forward.

### 6. Proposed target CLI tree

The proposal is presented as the reconciliation of the operator
transcript, the four discovery findings, and the three overlapping
accepted ADRs. It is the ADR-input — the ADR will decide.

Under `aeat config`:

- `init` — bootstrap-once wizard. Refuses to run if a real (non-shadow)
  bucket is already present; instructs the operator to use
  `aeat config bucket create` instead. Internally calls the same
  bucket / profile creation service that `bucket create` uses, on
  the literal `default` bucket-id, marking the bucket as
  non-shadow once any operator-typed field is committed.
- `bucket create NAME` — canonical creator for a second-or-later
  bucket. Interactive by default; accepts the full forty-plus typed
  flags `init` takes today (via the same wizard backend); accepts
  `--from <existing>` which replaces the deleted `profile duplicate`
  verb. Refuses if NAME collides unless `--force` is supplied.
- `bucket edit [NAME]` — re-run the wizard against an existing
  bucket (the read-then-write equivalent of the silent overwrite
  `init` currently performs). Defaults to the active bucket if
  NAME is omitted.
- `bucket use NAME` — operator-friendly alias of `switch <bucket-id>`
  that accepts the display `label` from `manifest.toml` (with
  collision handling: refuses if two buckets share a label).
- `bucket list` — supersedes `list-buckets`; `--with-status`
  inherits the May-13 ADR's enrichment columns.
- `bucket switch <bucket-id>` — preserved from May-14 as the
  precise identifier form; `bucket use NAME` is the discoverable
  human form layered on top.
- `bucket delete` / `bucket export` / `bucket import` — preserved
  from May-14, renamed to drop the `-bucket` suffix because they
  already sit under `bucket`.
- `bucket status` — supersedes `profile status`; reports active
  bucket label, readiness, shadow flag, last unlock.

Under `aeat config bucket`, the `profile` sub-noun is collapsed
entirely. Identity-layer concerns (NIF, activity, IVA regime,
language preference) are bucket-scoped facts edited through
`bucket set KEY VALUE`, `bucket unset KEY`, `bucket get KEY`,
`bucket list-keys` (the existing `profile list` / `set` / `get` /
`unset` verbs renamed).

The top-level `aeat config --help` summary must advertise every
verb under `bucket`, not just four. The current four-verb
advertisement was the proximate cause of the operator transcript's
confusion.

### 7. Secure-storage design for shadow-default and `--from`

The shadow-default concept introduces three design questions for the
ADR:

**Shadow representation on disk.** Two options. (a) Manifest-only:
ship a `manifest.toml` at `<aeat-root>/buckets/default/manifest.toml`
with `shadow: true` and no encrypted SQL row, no keystore entry.
`bucket list` reports it as `(shadow)`. `bucket use default` refuses
with a typed `BucketIsShadowError` whose message instructs the
operator to run `aeat config init`. (b) No-on-disk-presence: a
shadow bucket has no manifest. `bucket list` synthesises a
`(no buckets — run aeat config init)` line from the absence of any
manifest. Option (b) is the simpler model and matches the May-14
ADR's stance that a vanilla install has nothing in `buckets/`.
Option (a) gives the manifest schema a place to carry `shadow: true`,
which the operator-facing tooling can read without unlocking
anything. Recommend (b) — fewer states, no shadow-vs-real
discriminator drift, and a clearer "you have no real bucket yet"
operator narrative.

**`bucket create --from <existing>` cryptographic semantics.**
The current `profile duplicate` calls `model_copy` on the in-memory
record and `repository.save` on the new identifier. The new bucket
gets its own fresh AES-256-GCM nonce (confirmed at
`_crypto.py:128`). Under the May-14 per-bucket model, `--from`
must additionally provision a fresh KEK (its own Argon2id salt),
its own wrapped master key, its own recovery mnemonic, and its own
keystore entry. No cryptographic material may be copied from
source to target. The user-facing data (NIF, activity, IVA regime,
language) is copied; everything below the envelope boundary is
freshly generated. The ADR must call this out explicitly because
the natural reading of "duplicate" implies bit-for-bit copy.

**`init` writing on the shadow.** Under the recommended option (b)
above, `init` does not transform a shadow into a real bucket — it
creates a real bucket from scratch at `<aeat-root>/buckets/default/`.
The first invocation of `init` always lands on the `default`
bucket-id. Subsequent `init` invocations refuse (the May-14 ADR's
"refuses if buckets/ has any entries" stance). Second-or-later
buckets land through `bucket create NAME`.

**Manifest ↔ SQL row atomicity (Finding 3.1).** The ADR should
mandate a write-order: (i) write the manifest to a tmp path,
(ii) commit the encrypted SQL row in a SQLAlchemy transaction,
(iii) rename the tmp manifest to its final path. A crash at (i) or
(ii) leaves nothing visible; a crash at (iii) leaves the SQL row
present but no operator-visible manifest, which `bucket list` then
re-projects as orphan and `repair` can recover. The current
order (manifest first, SQL row second) is the opposite — a crash
after the manifest write leaves an addressable bucket with no
profile record.

**Typed-envelope drift (Finding 3.2).** The
`InvoiceReviewRecord | dict[str, object]` union must collapse to the
typed arm alone before any new boundary lands. This is unblocked
work — it does not depend on the profile-lifecycle redesign — but
the redesign cannot ship without it because the same encrypted
secure-object row carries the bucket pointer map.

**Anti-tautology probe test (Finding 3.4).** The ADR must require
the roundtrip-discipline anti-tautology test for the
`BucketPointer` + `UserProfileRecord` boundary. Without it, the
new code lands with the same hidden-regression exposure the
shipped code has.

### 8. Open questions for the ADR

The following are the decisions the ADR must make. They are
phrased as questions, not answers, because each carries a real
trade-off.

**8.1 — How does `init` and `bucket create` collide?** The
recommended target tree has `init` as bootstrap-once and
`bucket create NAME` as the canonical creator. Does `init` stay,
or does the bootstrap wizard collapse into `bucket create default
--first-run` to eliminate the third verb? Trade-off: keeping `init`
matches the well-known pattern (`gcloud init`, `npm init`,
`cargo init`); collapsing it removes one verb and makes
`bucket create` the only path to a new bucket.

**8.2 — Resolving the May-13 vs May-14 collision.** The May-13
ADR adds `profile use` as an alias of `set active`. The May-14
ADR removes `profile use` and replaces it with `switch`. Does
the new ADR formally supersede the May-13 ADR (marking it
`superseded`), or does it integrate the May-13 enrichment columns
(`--with-status`) into the new `bucket list` verb? Recommend the
latter — the enrichment work is sound and the May-13 ADR's
substantive contribution survives.

**8.3 — Display-name collisions in `bucket use NAME`.** Two
buckets with the same `label` in `manifest.toml` would break the
human-readable form. Options: (a) enforce label uniqueness at
`bucket create` time (refuse colliding label); (b) accept
collision and require `bucket use <bucket-id>` when ambiguous;
(c) prompt the operator to disambiguate. Recommend (a) — labels
are operator-typed and uniqueness is enforceable.

**8.4 — `bucket edit` vs `bucket set KEY VALUE`.** The wizard
form `bucket edit` walks the operator through every field; the
key-at-a-time form `bucket set KEY VALUE` matches the existing
`profile set` verb. Both are useful in different contexts (full
re-onboarding vs targeted correction). Keep both? Or collapse
into one with a `--wizard` flag?

**8.5 — `--from <existing>` semantics.** Options: (a) copy all
operator-facing facts verbatim; (b) copy facts but reset
lifecycle metadata (`created_at`, `last_unlocked_at`); (c) copy
facts but clear identity-bearing fields (NIF, surnames) on the
assumption that `--from` is for "I want the same activity / regime
but a different person". Recommend (b) — copy facts, reset
timestamps, retain identity (the operator is duplicating
deliberately).

**8.6 — Should the locale catalogues be migrated in the same
commit?** The May-14 ADR mandates `bucket` everywhere and
forbids `profile` as a structural noun in code. The locale rule
(operator-memory `locales-via-cli`) requires CLI-driven scaffolding. The new
ADR's execution path should bundle locale regeneration into the
first execution step so no rename is half-done.

**8.7 — Backend findings 3.1 through 3.6: in scope or follow-up?**
The user mandate is explicit that backend drift is in scope, not
a follow-up. The ADR should list which findings land alongside
the CLI rework and which (if any) are deferred. Recommend
landing 3.1 (manifest ↔ SQL row write order), 3.2 (workflow-state
typed-envelope drift), 3.3 (`_iter_profiles` encapsulation),
3.4 (anti-tautology probe), 3.5 (domain constant for default
bucket-id), 3.6 (shadow-default representation) in the same
plan as the CLI surface change. None are independently shippable
without the others; the boundary is single-cut.

**8.8 — Dev-facing surfaces to retire.** The operator CLI surface
review surfaced one candidate: `aeat config repair list NAMESPACE`
at `_config/__init__.py:210` accepts an internal namespace string
and dumps secure-object keys. This is debug-shaped, not
operator-shaped. The project rule against dev-facing CLI
(operator-memory `factory-direct-no-prs`) requires it to move to
`python -m aeat.<x>` or to be removed. The new ADR's scope
should decide.

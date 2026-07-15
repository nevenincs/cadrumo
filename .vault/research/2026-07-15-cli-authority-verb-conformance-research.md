---
tags:
  - '#research'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
related:
  - "[[2026-06-10-cli-operator-surface-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-auth-shape-adr]]"
  - "[[2026-05-14-secure-backend-passkey-custody-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
---

# `cli-authority-verb-conformance` research: `CLI authority and verb conformance`

This research audits the complete live CLI surface and the application,
domain, persistence, and adapter paths beneath commands whose names or effects
overlap.  The objective is deliberately narrower than a general vocabulary
rewrite: remove duplicate operator doors, restore one canonical writer per
state transition, and rename only where the current word materially misstates
the operation.  Every rename has a large translation, schema, documentation,
test, and conformance cost, so established and accurate verbs remain unchanged.

The audit began with Vaultspec-RAG searches over the vault and code indexes,
then verified each candidate against the full source and an isolated materialized
CLI.  The inspected revision was
`87b69b735adeefc9f35ad630e6fd81624c61a0ca` on 2026-07-15.  The RAG service
reported 25,610 vault documents and 35,008 source sections in its active index.
Three independent audit tracks covered current semantic duplication, external
CLI conventions, and backend single-writer authority.

## Findings

### Baseline and governing decisions

The materialized CLI contains 68 command groups and 282 leaf commands.  Every
leaf path is unique; the defect class is therefore not duplicate Click/Typer
registration but different paths that perform the same operation, or paths
that mutate the same state under different policy.

The accepted `cli-operator-surface` decision is binding: one verb per intent,
intent vocabulary rather than storage mechanics, hard replacement without
aliases or deprecation shadows, and newcomer guessability as the acceptance
test.  The accepted `config-auth-shape` decision currently assigns the broad
provider/session/lock reset to `auth clear`; changing that command requires an
ADR amendment, not a cosmetic edit.  The accepted evidence-bundle decision
requires replay to use stored inputs, traces, hashes, and snapshots and to
produce match, degraded, or corrupt outcomes.  The accepted profile-state
aggregate decision requires one profile repository as the sole writer across
physical stores.

The repository clone audit reports 65 clone clusters and 0.4 percent duplicated
lines.  Only two reported CLI clusters directly intersect this campaign:
repair rendering and profile export/subject-access serialization.  The
architecture linter cannot currently build its graph because `.importlinter`
still names the retired root package `aeat` while production imports are rooted
at `cadrumo`.  The operator brought this degraded gate into scope.  The
campaign must change the configured root package to `cadrumo`, run every
existing contract, repair any newly exposed contract or stale-ignore failure,
and make a green import-linter run a prerequisite for the feature waves.

An in-memory-only, uncached diagnostic changed the configured root to
`cadrumo` without editing the worktree.  The resulting graph analyzed 3,419
files and 16,149 dependencies across five contracts.  It first exposed two
stale, error-level ignore entries:
`cadrumo.application.live._censo -> cadrumo.adapters.**` and
`cadrumo.application.user_profile._censo_sync -> cadrumo.adapters.**`.
Removing only those entries in memory allowed the complete graph to render:
three contracts were kept and two were broken by exactly three root-cause
paths.

| Root-cause path | Classification | Required reconciliation |
|---|---|---|
| `cadrumo.core.tests.test_isolation_fixture_state_root_coverage -> cadrumo.tests.secure_sql -> cadrumo.adapters.*` | Accepted real-adapter fixture seam whose shared-helper edge was omitted during the package rename | Restore only the exact `core test -> cadrumo.tests.secure_sql` route required by the accepted test-carveout ADR; do not exempt production core or all shared test helpers. |
| `cadrumo.application.aggregation._irnr_income_ledger -> cadrumo.adapters.persistence.profile.transactions` | Dead second composition door | Remove the fallback concrete construction and require `TransactionCatalogueRepositoryProtocol` in both `aggregate_irnr_income_ledger_from_repositories` and the public `LedgerIrnrIncomeAggregationSourceResolver` constructor.  Its sole production caller already injects the one memoized repository shared by every ledger resolver, and both direct tests inject a real repository; retaining either optional path could bypass one-load authority.  No ignore is permitted. |
| `cadrumo.application.modelo._verification_actions -> cadrumo.adapters.persistence.profile.invoices` | Genuine type-only boundary defect | Replace every concrete annotation with the existing domain `InvoiceCatalogueRepositoryProtocol` and widen the receiving OSS/IOSS resolver annotations to that port.  The verification service never constructs the concrete, so no ignore is permitted. |

This disposition follows the accepted gates-ratchet policy: existing
application construction debt remains visible as individually named edges,
while newly exposed dead or type-only coupling is repaired rather than
registered.  It does not add a production pin or wildcard and does not weaken
`core -> outer` enforcement.

The accompanying ratchet is independently false-green.
`src/cadrumo/tests/test_importlinter_ledger.py:31` still parses only `aeat.*`,
so it currently finds zero of the Cadrumo ignore entries while comparing that
empty inventory with obsolete ceilings of 840 application edges, 78
application source wildcards, and 70 domain edges.  Parsing the live
`cadrumo.*` ledger yields 201 application-to-adapter entries, 81 application
source wildcards, and two domain test-carveout entries before reconciliation.
Wave 0 must retarget the parser, narrow
`application.diagnostics_run_health -> adapters.**` to its live
`adapters.outbound.llm` dependency, remove the two stale source wildcards, and
lower the ceilings to the reconciled live inventory: 199, 78, and 2.  A ceiling
may not be raised.  The prerequisite is complete only when the corrected
on-disk configuration reports all five contracts kept in a fresh uncached
process and the live ledger tests pass.

### Confirmed duplicate doors

| Surface pair | Classification | Evidence | Disposition |
|---|---|---|---|
| `config lock` and `config profile logout` | Exact operator alias | Both call `logout_active_profile`, which clears the active-profile pointer.  No distinct encrypted-but-authenticated locked state exists. | Remove `lock`; retain `profile logout`; no alias. |
| `config switch sandbox:NAME` and `config profile sandbox use NAME` | Constraint-subset duplicate | Both call `select_profile_with_lifecycle_span`; sandbox `use` only prefixes and validates the label. | Make `switch` the sole selector, adding an explicit sandbox short-name contract if needed, then remove sandbox `use`. |
| `config reset --scope data` and `config repair quarantine` | Exact action duplicate | Both call `quarantine_unreadable_secure_objects`. | Remove the DATA reset scope; ALL may compose the canonical repair service. |
| `app modelo audit check` and `app modelo audit replay` | Exact backend alias and contract violation | `EvidenceBundleService.replay` is literally `return self.check(...)`; only the output schema differs. | Remove replay until a distinct historical replay service exists, or implement the accepted replay contract before retaining the verb. |

### Parallel or bypassing authorities

#### Profile reset and pointer ownership

Profile orchestration and `ProfileRepository` both implement raw pointer
capture, restore, and clear.  Normal selection uses the atomic core
`write_pointer`, while rollback restoration uses direct non-atomic text writes
and repair performs another direct unlink.  More seriously,
`reset_config(PROFILE|ALL)` deletes lifecycle rows and bucket directories but
does not clear the active pointer.  A real-storage reproduction left the
pointer naming the removed bucket after the bucket directory disappeared.

The same reset path bypasses `BucketMaintenanceService.delete`, which owns
active-bucket refusal, retention-floor assessment and override, tombstone and
manifest state, and ordered deletion events.  This is a second destructive
authority, not merely duplicated syntax.  Pointer mutation must have one atomic
owner, and profile deletion/reset must compose the bucket-maintenance policy or
the PROFILE/ALL reset scopes must be retired.

#### Authentication reset

`reset_config(AUTH|ALL)` directly replaces `AuthState` and reports
`removed_auth_session=True`.  It does not delete persisted encrypted sessions,
clear acquisition locks, or emit the canonical provider/session/lock events.
`clear_operator_auth` already owns those operations.  The reset path therefore
claims an effect it did not perform and leaves live custody artefacts behind.
Any retained reset composition must invoke the canonical auth service before
profile deletion makes the active bucket unreachable.

#### Certificate credentials

Certificate-source selection stores a named path in workflow state.  Secret
set/remove supports secure storage or keyring, but the chosen backend is not
persisted.  Certificate check resolves named secrets through the default secure
storage backend, while login passes unchanged global settings to the
authenticator, which reads only `cadrumo_certificate_path` and
`cadrumo_certificate_password_secret`.  A named secret can therefore be stored
successfully yet never be consumed by live login; a selected path can pass an
application precondition while the authenticator receives no usable path.

One application credential resolver must derive the selected source path,
secret reference, and secret backend into a typed scoped credential bundle used
by check, status, test, and login.  The lower-cost resolution is to standardize
certificate passphrases on secure storage and remove the unpersisted keyring
choice; retaining keyring requires persisting its backend kind per source.

#### Ledger evidence

`ledger attach` calls `attach_manual_transaction_evidence`, which refuses an
implicit replacement of existing purchase evidence.  `ledger link
--evidence-id` writes the same field through the generic transaction patch and
bypasses that guard.  When invoice and evidence are supplied together, the CLI
performs sequential writes, so an evidence refusal can leave the invoice link
committed.

The canonical evidence policy owner is the attach application service.  The
`link` command should remain for invoice relationships but must drop or delegate
its evidence option.  If combined invoice/evidence mutation remains, it needs
one atomic application operation.  Explicit evidence replacement, if desired,
must be a named application policy rather than a generic-patch side effect.

#### Profile export and subject access

Portable cleartext export and `profile subject-access-request` independently
resolve the profile, open the storage session, serialize the same bundle, emit
the export event, create the directory, and write cleartext JSON.  Subject
access adds a legal-purpose catalogue and notices, so the two operator intents
can remain discoverable, but they must delegate one application export service.
The service should own serialization, atomic transport writing, and event
emission with a typed purpose such as `portable_transfer` or `subject_access`.

### Intentional sharing that must not be collapsed

- Passphrase change and recovery share a master-key rewrap tail but have
  different authorization: the former requires the current passphrase and the
  latter requires the recovery mnemonic.
- Google logout and profile logout terminate different sessions.
- `doclink` acquires and stores bytes before delegating to attach; it is a
  composition, not a second evidence writer.
- Sandbox discard and prune are single-item and bulk lifecycle operations.
- Portable profile export and full recovery archive have different contents and
  custody guarantees.
- Evidence export invoking check as a precondition is intentional composition.
- Ledger `list` and `review` are distinct read models: list owns pagination,
  grouping, sorting, and presentation controls, while review owns review-state,
  issue, import, classification, direction, and detail filters.
- Auth `status` and `test` share the state projection intentionally; test adds
  persisted-session and provider-bundle probes.

### Residual exact hashing implementations

The broader backend sweep found two exact SHA-256 implementations outside the
canonical `core.hashing.sha256_hex`: MCP telemetry hashes UTF-8 text directly,
and the review-package recipient registry hashes decoded public-key bytes
directly.  Both are layer-safe consumers of core.  Retain a domain-named
telemetry wrapper if useful, but delegate its body to `sha256_hex`; use
`sha256_hex` directly for the recipient fingerprint.  This low-cost P2 hygiene
is included because the campaign promises a backend duplication sweep, not only
operator-visible cleanup.

### Cost-aware verb disposition

| Current surface | Proposed target | Reason | Migration value |
|---|---|---|---|
| `config lock` | Remove; use `config profile logout` | Current implementation is logout, not a locked authenticated state. | High value, low-medium cost. |
| `config switch` | Keep | Conventional and already selected by accepted ADR. | Renaming again has no value. |
| `config profile sandbox use` | Remove after switch accepts the intended sandbox form | A second selector adds no intent. | Medium value and cost. |
| `config rekey` | `config passphrase change` | The master key is preserved; only its passphrase wrapping changes.  Security-critical vocabulary should be exact. | High value, medium cost. |
| `config show-recovery` | `config recovery status` and `config recovery rotate` | A read-looking command currently mints or rotates recovery material. | High safety value, high coordinated cost. |
| `config verify-recovery` | `config recovery verify` | Groups the recovery lifecycle under one noun. | Worthwhile only with the recovery redesign. |
| `config recover` | Keep, or move to `config recovery recover` only in the coordinated family migration | `recover` already names the operator intent accurately. | Avoid isolated churn. |
| `config auth clear` | Split into `config auth logout` and `config auth reset` | Session termination and provider/configuration/lock reset are distinct intents. | High value and cost; requires ADR amendment. |
| `ledger attach` | Keep | It is the accurate and guarded evidence operation. | No rename. |
| `ledger link` | Keep for invoice relations; remove/delegate `--evidence-id` | The noun is accurate once it no longer bypasses evidence policy. | Backend correction without migration churn. |
| `ledger doclink` | Optional `ledger attach-from-link` | Current custom compound hides byte acquisition and attachment. | Lower priority; defer unless editing the same family. |
| `modelo audit check` | Keep | Established non-mutating integrity vocabulary. | No rename. |
| `modelo audit replay` | Remove until real replay exists | A replay that is merely check is a misleading alias. | High value, low-medium cost. |
| `config repair quarantine` | Keep | Explicit confirmed repair mutation. | Canonical maintenance door. |
| `config repair reset-progress` | Keep | Accurately resets one saved progress envelope. | No rename. |
| `config reset --scope data` | Remove | Exact duplicate of repair quarantine. | High clarity, low-medium cost. |
| `config reset --scope auth` | Remove or delegate canonical auth reset | Current path bypasses sessions, locks, and events. | P0 authority correction. |
| `config reset --scope profile|all` | Retain only after composing canonical deletion/retention and pointer policy | Current path bypasses destructive safety authority and strands the pointer. | P0 safety correction, not a naming preference. |

### External convention checks

Official command documentation confirms that both `switch` and `use` are
normal active-selection words: GitHub uses `gh auth switch`, Docker uses
`docker context use`, and Kubernetes uses `kubectl config use-context`.
Consequently the accepted project choice `switch` should remain stable.

Bitwarden distinguishes unlocked, locked, and unauthenticated states, and
1Password uses `signout` for session termination.  This supports removing a
`lock` spelling whose only effect is logout.  Restic describes password change
under `key passwd`, while HashiCorp Vault `operator rekey` replaces unseal-key
shares; those meanings support `passphrase change` for a wrapping-only
operation.  Restic separates non-mutating `check` from mutating `repair`, and
Git replay actually reapplies commits rather than repeating a check.

### Proposed decision package

The smallest coherent implementation is:

1. Establish one atomic active-profile pointer owner and route profile reset and
   deletion through the canonical bucket-maintenance policy.
2. Establish one certificate credential resolver and one auth reset owner.
3. Remove the exact duplicate doors: `lock`, sandbox `use`, DATA reset, and the
   current fake replay.
4. Route all ledger evidence assignment through the attach policy and make any
   retained combined relation/evidence operation atomic.
5. Extract one application profile-export service while keeping the legal
   subject-access intent discoverable.
6. Hard-rename only the materially misleading custody vocabulary:
   `rekey` to `passphrase change`, and the overloaded recovery commands to a
   noun-group with separate status, rotate, verify, and recover actions.
7. Split auth session logout from destructive auth reset; no alias or
   compatibility spellings survive.
8. Restore the import-linter root to `cadrumo`, reconcile every surfaced
   contract or stale-ignore defect, and require a green graph before feature
   work.
9. Delegate the two residual SHA-256 implementations to `core.hashing`.

This package is larger than a verb-only patch because the audit proves that
several misleading verbs are symptoms of parallel backend authority.  Renaming
without consolidating those writers would preserve the maintenance defect under
cleaner wording.

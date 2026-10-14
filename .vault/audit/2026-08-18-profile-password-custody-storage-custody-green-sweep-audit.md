---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-10-14'
body_schema: 'body-v1'
body_hash: 'sha256:6754c103aef32f47f2ee4cd40d888ea9c06febf117de82ae3d514a10854d5a6f'
related: []
---
# `profile-password-custody` audit: `storage and custody green sweep`

## Scope and reading rules

This is a historical green-sweep of profile registration, password custody, recovery, encrypted
storage, persistence, and the CLI surfaces that operate them. The original append-only audit is
preserved verbatim in the external archive at
`<local-archive>/markdown-originals-2026-10-14.tar.gz`.
This summary consolidates repeated probes and changing snapshots while retaining final dispositions,
important corrections, evidence limits, source locators, and the unresolved handoffs. The source
uses descriptive finding headings rather than a severity scheme; it has one explicit `FINDING`
heading, retained below. Historic measurements are not current certification.

## Findings

### Custody and recovery outcomes

Profile creation now projects initial facts through the canonical setup flow and into the
registration door. The previously supported field-flag form had been routed to a create arm that
refused unconditionally, even though the operator-action catalogue advertised those flags as the
remedy for a clean-root refusal. Projection is pure and precedes passphrase resolution, so invalid
facts do not prompt for a secret or leave a capsule. The explicit foral-regime refusal remains
because it supplies the actionable Concierto Económico / tax-office guidance that a generic widget
failure does not.

Recovery enrolment is minted during registration. The 24-word phrase is delivered through the
handover channel before capsule publication; an undeliverable channel aborts rather than leaving an
enrolled but unrecoverable profile. The CLI create door has dedicated coverage. The full-screen
creation path remains narrower: its terminal-direct channel cannot render within the full-screen
display.

The real-storage lifecycle was driven end to end: create with facts, list, edit, logout, archive
export/inspect, delete, restore, and login. A complete fresh-root restore returned byte-identical
profile facts, including on a host with no keyring. The sealed archive was encrypted; its header
could be inspected without decrypting it. Deleting the active profile refuses with a logout remedy;
headless restore refuses to read a secret from a nonexistent terminal and names bounded stdin.
Restoring an archive under a new label on the originating host is correctly blocked by the retained
UUID-to-label lineage record, while the same archive restores under a new label on a fresh root.
Deletion intentionally retains journals, receipts, and holds so the audit trail outlives the data.

Login with no password channel now names the accepted channels only after custody has established
that authentication failed, no callback exists, and no configured passphrase is available. An
actual wrong password is not misdiagnosed as a missing channel. Restore errors derive accepted
payload keys from the strict model and never echo the submitted secret. The operator surface uses
`--format json` at the root, not a per-verb `--json`.

Two observed behaviours were deliberately retained. CLI redaction replaces every UUID-shaped
substring, including UUIDs in caller-supplied filesystem paths; the documented
`CADRUMO_CLI_REVEAL_IDENTIFIERS=1` opt-out exists, and the operator already knows a path they
supplied. The JSON option spelling is also unchanged.

### Key model, encryption boundary, and safety controls

The `master_key` package name outlived the shared-master-key model, but its substrate is live:
certificate secrets reach the encrypted blob store through the secret-store factory, and absent an
explicit provider the store uses the active per-profile bucket-session key. Four `MasterKeyProvider`
references are production-internal to storage; there are no consumers outside that package. The
protocol is not an extension point: `_provider_enter` admits only `UnsecuredMasterKeyProvider`,
which is the live discriminator inside `open_bucket`. The class remains important to the
published-key safety fence.

The retired `_rotation.py` path was removed only after the operator chose deletion. It contained
596 lines and three test modules; 38 tests and six facade exports were removed with it. It had no
production caller, and every accepted rotation supplied the same deterministic unsecured provider,
so the old “rewrap all stores from old master key to new master key” model was uncallable in a
meaningful sense. The live credential rotation is `config passphrase change` through
`rotate_profile_passphrase`; it re-wraps the same data-encryption key and preserves the DEK epoch.
Eleven taxonomy entries were made dormant with reasons, the facade/API stub was cleaned, and one
fixture string was intentionally retained because rewriting it would weaken its path-shape proof.
The decision was grounded in the creation path minting only the current per-profile schedule; it is
not permission for an agent to remove other key-schedule or DEK-derivation code.

The published deterministic unsecured key is guarded by `refuse_unsecured_with_real_nif` and
`refuse_unsecured_bucket_with_real_profile`. Both accepting and refusing directions now have
non-vacuous coverage and were mutation-proven from a pytest plugin outside the repository. A
whitespace-padded real NIF remains real; a number with a real NIF's digits but an invalid check
letter (`12345678A`) is treated as synthetic. That is an explicit parser-dependent boundary which
must be revisited if tax-ID parsing changes. The bucket canary checks activation, not later writes:
a real NIF written after activation into an empty bucket can land under the published key until the
next activation. This remains intentionally open because it requires a profile-write-path design
change and requires both `CADRUMO_ALLOW_UNENCRYPTED=1` and the unsecured backend; the opt-in marks
that data disposable. A gate now enumerates every production `BucketSession.open(...)` and requires
the canary; it has an empty-enumeration control and was shown to bite when the real call was removed.

`SecretStoreBackend` no longer advertises nonexistent `keyring` and `file` implementations. It
accepts `auto` and `unsecured`; stale values fail validation, and the generated environment page
was refreshed. The isolation recipe no longer tells operators to set a dead backend value. The
name `auto` is still arguably misleading because it means profile-password custody, but renaming
it would break existing environment files and remains an owner decision.

Concurrent failed logins once lost throttle increments because each process read and rewrote the
same sidecar. On Windows, the rename collision could raise `PermissionError` out of the
wrong-password handler. The increment now uses `core.exclusive_file_lock`; an unpersistable write
logs and returns on-disk state, matching reset semantics. The regression failed against HEAD before
the fix. Missing, unreadable, or version-mismatched throttle files still mean no active throttle by
design, protecting legitimate operators from local-CLI self-denial.

The cross-profile boundary is structural. Fourteen production paths use bucket-scoped resolvers,
but all require an active ready session and reject a requested bucket that differs from the bound
session. The only synthetic-session exception cannot collide with real UUID profile ids. Real
password envelopes and recovery artifacts refuse cross-profile opens. `BucketSession` uses a
context-local binding; concurrent thread isolation was proven using real sessions and a deliberately
broken process-wide holder. One test initially passed while broken because a single barrier allowed
one thread to unwind first; two barriers now keep both observations concurrent.

The bucket lockfile has real-process tests for busy detection, wait/acquisition, stale reclaim,
foreign-lock preservation, inheritance, and sharing violations. `pid_is_alive` fails closed when
permissions prevent probing, but that branch had no behavioral test: all 564 scanned live
processes allowed a query in this environment. Resumed sessions hardcode the secured backend. The
separate custody-root lock now has tests for second-process refusal, reacquisition after the holder
is killed, owner-thread reentrancy, and sibling-thread refusal. Its correctness depends on the
kernel releasing a process lock on exit; it has no PID reclaim path. A lock-order gate records 95
real acquisitions across 583 tests, including 17 root locks and 61 nested acquisitions; every
nested acquisition was root-first. A full concurrent CLI login against one profile remains
untested.

### Persistence and audit-trail integrity

The lost-update defect affected encrypted singleton catalogues: two writers could each read the
whole row, edit different entries, and overwrite the other's result. A green guarded repository is
insufficient if the live service bypasses it. Invoice catalogue mutators were moved inside a
revision-guarded unit of work; inventory creation now delegates to its guarded verb. Inventory
movement keeps its domain valuation check before persistence; routing it through a stale-read guard
without moving or ordering that calculation would allow invalid valuation to persist. Inventory
removal required a guarded verb. These were treated as design questions until the safe order and
capability existed.

Audit-trail emission was closed across standalone and co-commit paths. The standalone event emitters
use `append_guarded`; four direct emit sites were routed through that authority. A first gate
matched only the shape `save(append_bucket_event(...))` and missed calls bound through names,
annotated assignments, and intermediate results. It was replaced with a composing-write inventory
that requires `expected_revision_id` or an explicit disposition. The final storage gate measures
properties rather than source spelling. Repeated checks caught its own blind spots before they
could become false-green closure claims.

The guarded-composition seam re-reads the revision and re-composes the complete batch on conflict;
if retries are exhausted it raises rather than silently dropping an event. This made ledger and
reconciliation writes guardable while preserving atomic co-commit with the record they describe.
The calculation-revision path now threads the catalogue revision from `load_revisioned` through
`PreparedCalculation` into persistence. Domain protocols were widened because callers could not pass
a revision through an interface that omitted it. Work-unit catalogue input arriving as a parameter
still requires the caller to thread its observed revision; the gate documents that boundary rather
than pretending to infer a revision at the callee. A required parameter is necessary: an optional
`None` would look guarded to a keyword-only scanner while guarding nothing.

The original inventory had 18 composing writes, including six unclassified entries. Tracing found
one wrong exemption: invoice/reconciliation catalogues were locally loaded even though repositories
were passed as parameters; a transaction row is not a singleton and did not need the same guard.
A fifth detector blind spot was an attribute such as `result.invoices`, beyond name-taint tracking.
The test that failed after prorrata passed a revision keyword to a base that did not accept it; the
whole touched package surface (1,524 tests) was run to catch it. Filtering with `-k` had excluded the
failing test, and the standing lane did not include `adapters/persistence/profile`.

The audit trail itself is content-addressed, so a discarded event leaves no detectable gap. Receipt
stamping preserves the ordering: the justificante lands before a filing record cites it, so a crash
can leave a harmless, re-runnable orphan rather than a record claiming missing evidence. Some
paths initially lacked a bespoke concurrency proof; no thread-race was claimed where worker threads
cannot share the active-session `ContextVar`. Later guarded-composition tests stage the retry at the
repository seam. At final closeout, isolated storage and profile lanes were green, and all
persistence-boundary classes had a real refusal or strict-inequality proof.

The anti-tautology review started with 45 roundtrip modules and a keyword scan that falsely reported
18 gaps. Behavior review reduced this to three: a policy scan rather than a persistence boundary;
a corrupt cosmetic language hint correctly falling back to `None`; and a `SecureObject` boundary
covered by sibling corruption tests. No uncovered storage boundary remained. The six unused
`user_profile` command contracts were deleted with an anchor gate; thirteen names used only within
their module were over-exports, not classified as dead.

The sealed capsule payload gained its own durable schema enrollment and a module-specific
`CAPSULE_ARCHIVE_PAYLOAD_SCHEMA_VERSION`. The untrusted archive reader and restore-directory path
were separately reviewed; archive fixture bytes from AEAT were not edited to satisfy parsers. The
M130 submitted fixture's declared signed field at offset 143 contains 17 spaces, an allowed marker;
the failure was in record segmentation, so the sede parser/layout owners received the finding.

### Findings on operator surfaces, harness coverage, and measurement

The initially prescribed unit/integration lanes under-covered the tree: they omitted
`adapters/persistence/profile` and `src/cadrumo-harness`, and default markers also exclude harness
integration. One repository-wide enum change broke two harness tests before this was noticed; the
failure was fixed, and later harness-only runs showed 19 failures reduced to 3, then 4 failing / 317
passing while peer work was active. Several reds were stale subjects (warm local verbs measured as
slow subprocesses, renamed command keys, and a flat `tools/list` assumption); the remaining gate
questions were retained rather than “fixed” by loosening thresholds. A missing locale scan root had
left 15 harness strings untranslated; catalogue keys were added without altering the protected
`Cadrumo CLI` token.

The platform keychain failures were measured against Windows Credential Manager. At one point 14
unmarked resume cases failed with `WinError 1312`; later the `os_keychain` lane had 26 marked
failures, all attributable to unavailable network-logon credentials and downstream receipt
preconditions. Their marker boundary was corrected only after reading the rule's actual contract.
The later held-out set has 28 cases and needs one `just test-os-keychain` run from an interactive
desktop. This is operator verification, not an open storage defect. Serial coverage was 16/16
passing. Do not treat marker-deselected cases as disabled.

A risk-assessment gate was present and wired but red: 26 of 291 exposed commands lacked
`COMMAND_RISK` rows, and no command declared a live write. Five custody/storage entries were
classified from their implementations; the other 21 live, ledger, provision, and config commands
belong to their owners. The gate must stay red until those owners make the judgments; do not copy
neighbor classifications. The CLI command-risk entries distinguish destructive passphrase change
from non-destructive restore, which refuses to replace a live label.

A second coverage failure was the six 2020-era CLI JSON/rule gates named by `aeat-cli-contract`:
two no longer existed after `SCHEMA_REGISTRY` moved to command specs, and two test modules still
imported deleted helpers and failed at collection. The envelope contract (one typed diagnostic
action rather than bespoke `advisory` / `next` / `suggestion`) still needs an owner decision: re-gate
against the new command-spec kernel or amend the rule. Later contract changes restored
`config passphrase change` as required by the accepted
`2026-08-23-cli-machine-secret-channel-unification` ADR. The root-refusal `command` identifier,
label ambiguity guidance, and missing typed profile-list action were repaired. Both domain lanes
then passed: 361 integration and 1,705 unit tests; serial was 16 green.

Do not compare suite totals across a changing worktree or corrupted environment. One full-tree run
reported 784 failures after only 23,584 tests collected because 112 collection errors suppressed
modules; a later run collected 35,432 and reported 1,568. Other peer edits caused 84 transient
registry/CLI failures and xdist collection mismatches. A separate later whole-repository lane
reported 333 failed, 3,639 passed, 1 skipped, 32 errors; sequential rerun confirmed 314 real
failures across 120 modules and three flakes. The known environmental clusters were 35 live ECB
requests and 27 unmarked keychain cases. Failure sets, collection counts, environment integrity,
HEAD movement, and package `RECORD` integrity matter more than raw totals.

A uv install was interrupted while a live Python process held a native extension. Seven installed
distributions were missing 38 files. Only absent files were restored from uv's unpacked cache; no
locked file was touched. Any run during the broken environment was discarded; the 314-failure
sequential confirmation preceded the corruption and remains valid. A source edit during a run also
invalidates the portion after the edit. Never edit production while a suite is measuring.

### Later chronology and consequential corrections

The final append-only portion broadens from custody defects into repository, CLI, harness and
registry triage. Its conclusions are historical snapshots; live worktree measurements were
repeatedly invalidated by peer edits and damaged environments.

### Corrected CLI finding and resolution

### FINDING: HEAD refuses `config profile show` on an operator-surface contract violation

At a clean HEAD, `config profile show --format json` returned no stdout and refused with
`REFUSED_OPERATOR_SURFACE_CONTRACT`; `config profile list` and help still worked. The contract saw
both an ambiguous `config.profile.descendiente` leaf/group and a mounted `config passphrase` family
without a CLI door. `config check` also exited 2, but the audit did not attribute that separate
cause. The owner first considered deleting the declaration; reading the accepted
`2026-08-23-cli-machine-secret-channel-unification` ADR proved the opposite: `config passphrase
change` is in its closed required inventory. The verb had been removed during a command-spec
migration, not retired. The peer restored it on the new kernel; the contract cleared and `config
profile show` again returned the intended “No active profile” refusal. The associated 22 lane
failures collapsed to downstream effects of that single contract refusal.

Two login tests were then corrected to pass secrets through the ADR-required `--secrets-stdin`
strict-JSON channel. Four stale censo route tests were updated to traverse the lazy Click command
graph without materializing/mutating shared command state. Follow-up probes found a distinct
root-refusal defect: process-boundary errors lost the requested command ID after Click context
close. The bounded invocation scope was used to preserve the requested leaf; separate regressions
then exposed an ambiguity-guidance escape at a new preflight call site and a missing typed
`operator.profile.list` action on profile-not-found. Those were repaired while retaining the
original refusal code/message. The two domain lanes later measured 361 integration and 1,705 unit
tests green; a still later sweep recorded 361/1,703 plus 16 serial tests, so these are separate
changing-tree snapshots.

### Integration and attribution evidence

Twelve clean feature branches, 18–26 hours stale and eleven conflicting with main, were
consolidated. Resolving conflicts by comparing to merge base exposed three defects already on main:
a release workflow referenced a deleted `precondition` job; `_external_import_actions.py` shadowed
the richer `import_external_filing_source` definition; and merging issue 604 reintroduced ten M390
casillas already replaced by issue 636. The duplicate function and M390 fragment were removed and
the workflow job reference repaired. The M390 reintroduction was this campaign's own regression and
was corrected in the same pass. Locale conflicts were parsed YAML wrapping, not string divergence;
main's command-spec and benchmark census refactors remained authoritative. The peer's active edits
and index lock were preserved.

A separate 61-test cluster across six modules refused because directly seeded profiles lacked
`contact.postcode`. Adding the postcode to a common placeholder did not reach those direct seeds;
replacing them with complete profiles moved nine of ten evidence-draft cases to confirmation
blockers, while a narrow tax-ID/postcode profile left ten failures. Both experiments were reverted:
postcode was masking a second confirmation-contract gap, not fixing it.

Shared-tree counts were not stable evidence. One run reported 784 failures after collection stopped
at 23,584 tests with 112 errors; a later run collected 35,432 and reported 1,568. Another 84
CLI/ledger failures were a transient modelo 296 compilation break during peer work, and xdist
workers sometimes collected different tests as the tree changed. Sequential re-measurement and
failure-set comparison isolated a real dead verb: `aeat app ledger list` declared positional
`record_id` although its handler accepts none, so every invocation crashed before the body. The
original heading records 157 occurrences; the failure cluster reproduced alone and remained after
the tree settled, so it is an unresolved command-spec/handler mismatch rather than peer churn. The
guidance from this campaign is to compare collected populations, inspect recent commits and rerun
failing node IDs sequentially before attributing a moving count.

### Registry, CLI and harness handoffs

Several red tests were retained because the code/test contract was ahead of a deliberate authority
or product decision:

- Unsupported modelos 151, 210, 600, 620, 650, 660, 714 and 721 have correct in-handler refusal
  keys, but the root profile-bound write-policy preflight runs first. Ten tests expect the
  legal-route refusal before profile resolution. Reordering authentication/write policy is a CLI
  security decision; the audit left it with the CLI owner.
- The declared `renta_family.incremento_guarderia_2024` value does not yet feed Modelo 100 casilla
  0613; its formula still uses count-times-cap. The registry explicitly reserves formula change for
  separate Art. 81.2 grounding and end-to-end proof.
- Seven sede export failures involve official redacted AEAT submitted bytes. The M130 signed field's
  declared offset contains 17 legal spaces; record segmentation, not fixture bytes, is implicated.
  Fixtures were not edited.
- The `aeat-cli-contract` rule names JSON/schema and rule-surface gates that were removed when
  schema identity moved to command specs. Two remaining test modules still import deleted helpers
  and fail collection. Re-gating the envelope contract on the new kernel, or changing the rule,
  belongs to its owner.
- Harness-only measurements covered about 320 of roughly 4,000 repository tests. A harness pass from
  19 failures to 3 did not imply a green tree. Six failures came from stale subjects (a warm local
  verb treated as a subprocess, flat `tools/list` assumptions, and a renamed `app.quickfile` key);
  the remaining issues included profile creation's recovery-secret channel, twelve unpinned enum
  axes, localization, result size and ranking. Missing wiring of the harness scan root hid 15
  untranslated strings from all four catalogues; translations also had to retain the literal
  `Cadrumo CLI` token.

The MCP output-size work separated shared contract cost from per-verb payload. Thirty-six schemas
first exceeded 18,000 characters; an identical notice/action spine consumed 5,769 bytes in every one
of 295 schemas. The corrected accounting measures that spine under its own 6,500-character ceiling and
retains the complete action tree: the effective limit is 18,000 per verb plus 6,500 shared.
Twenty-nine verbs are over only because of the constant; seven remain over on their own payload:
`modelo.work.runs` (27,381), `app.quickfile` (27,240), `modelo.work.review` (25,513),
`overview.calendar` (21,230), `modelo.work.wizard` (18,866), `modelo.work.calculate` (18,725), and
`modelo.work.revisions` (18,400). Those require payload/contract owner decisions, not a higher
unmeasured ceiling. A separate warm-transport probe was corrected because its original local `list`
verb completed before the subprocess probe; the gate now rejects a warm-served subject rather than
falsely claiming a blocked event loop.

### Whole-tree measurements and remaining owner work

A later canonical full-tree run reported 333 failures, 3,639 passes, one skip and 32 errors. A
sequential rerun of the parallel failing set reproduced 314 failures across 120 modules and
identified three flakes; parallel runs on the shared drive are discovery only. Thirty-five failures
reached a live ECB endpoint, 27 OS-keychain cases were missing the marker that excludes them, and
mandatory recovery-enrolment work was still migrating. One stale minimal-spec test was fixed by
explicitly declaring required country; three English-word assertions were made language-stable. The
modelo 111/202/other export cluster remained redacted as `FilingProducerSnapshotError` until a
deliberate one-run probe identified the real Modelo 111 blocker: the producer supplies
`colegio_concertado=None` unconditionally although the filing model and export layout require an
operator fact and no profile, wizard, CLI or filing-election field stores it. Defaulting false would
invent taxpayer data; its declaration source is a product decision.

The virtualenv also corrupted repeatedly while live Python processes held native extensions. One
incident left `cryptography` missing 56 files; a later RECORD audit found seven distributions
missing 38 files. Only absent files were restored from uv's unpacked cache, without touching locked
files; measurements during corruption were discarded. The sequential 314 confirmation preceded the
damage. Verify installed RECORDs before trusting collection/import failures on this machine.

Core was measured bottom-up at 11 failures to 3 with 2,230 passing after deterministic clock, enum,
exception, period, rate, TOML and format-durability repairs. Later domain work reduced 97 failures
to 18; the remaining cases included applicability-versus-calculation grade claims for modelos
117/126/128/136, two missing legal-catalogue sources, three corpus-evidence proofs, the M303
duplicate-window defect, a one-line `_validate.py` ratchet, and a same-campaign
`iva.m303_regime_composition` gate conflict. Authority claims were handed off, never auto-attested.
A 2025 deadline probe returned 16 M303 obligations (four copies per quarter); only the 2022
revision's windows stayed within its period selector. The deadline-window owner accepted the
research/reference handoff; its three correct tests remain red until the authority/product decision
and invariant are resolved.

Other unresolved work handed to owners includes the seven genuinely oversized MCP payloads and
shared notice-schema contract; where to collect the Modelo 111 `colegio_concertado` fact;
unsupported-modelo preflight ordering; M303 window authority; the 0613 formula grounding; sede
parser segmentation; the deleted CLI-contract gates; `runbook_id` removal blocked by the harness's
published `ErrorEnvelope` schema; the CLI `deprecated_key` projection, which no command uses but
shares peer-owned files; gate wiring into `prek` / `just check-all`; registry legal refs/evidence;
and held-out OS-keychain verification from an interactive desktop. The dead `aeat app ledger list`
spec/handler mismatch also remained reproducible. Do not soften tests that are correctly reporting
unresolved contracts or infer legal/product policy.

## Recommendations

### Corrected findings and ownership handoffs

Several append-only entries were explicitly corrected or superseded. The profile-bundle export is
live through the TUI manager and maintenance reconciliation; only its import/decrypt half is
unreachable. The accepted `2026-08-20-profile-portability-data-subject-access` ADR keeps the export
capability; import requires decisions on collision handling, create-versus-merge, idempotency, and
export/import equality. Passphrase rotation was not retired: after the accepted CLI machine-secret
ADR exposed a deleted verb, the peer restored `config passphrase change` on the new command-spec
kernel, and the contract refusal cleared. Stale login test setup and censo route tests were corrected
against the ADR; later the domain lanes reached green.

The unsupported-modelo policy guard itself is early and covers the stub-only models. The profile-
bound root write-policy precondition runs before dispatch, so no-profile refusals take precedence.
A registry/CLI owner must decide whether to add ordered spec preconditions or change the test contract;
this audit does not change authentication posture. The process error funnel was later fixed to retain
the requested CLI leaf for command identifiers and typed actions, with lifetime reset and anti-stale
controls.

Other high-impact findings remain attributed, not solved here:

- **Modelo 111 export is blocked.** `application/modelo/_export.py` supplies
  `colegio_concertado=None` unconditionally, while the filing snapshot correctly refuses an
  undeclared fact and the export layout requires it. No profile, wizard, CLI, or filing-election
  field supplies the fact. The product owner must decide where an operator declares it; defaulting
  `False` would invent a taxpayer fact.
- **M303 deadline windows duplicate obligations.** 2025 produced 16 obligations, each quarter
  four times, because revisions declare windows outside their period-selector span and the accessor
  filters by year only. The three tests are correct and remain red until the registry/product owner
  decides whether windows belong only to the governing revision or the accessor resolves the
  governing revision per triple. The accepted research/reference pair owns it; only the 2022
  revision was self-consistent.
- **Authority and legal-corpus work:** applicability-grade revisions 117, 126, 128 and 136 are not
  calculation-grade attestations; two legal refs (`orden-hac-242-2025:modelo-303`,
  `rd-1624-1992:art-68-bis`) lack catalogue entries; three corpus-evidence proofs remain. These are
  source authority claims, not automated cleanup.
- **MCP output schemas:** 36 verbs first appeared above an 18,000-character cap. Measuring the
  identical shared action tree separately attributed 5,769 bytes to common machinery and reduced
  the true overage to seven verbs: `modelo.work.runs`, `app.quickfile`, `modelo.work.review`,
  `overview.calendar`, `modelo.work.wizard`, `modelo.work.calculate`, and `modelo.work.revisions`.
  The seven need owner decisions on response payloads. The other 29 require a notice-envelope
  contract ruling; the effective total is 18,000 per-verb plus 6,500 shared, guarded separately.
- **Gate/harness ownership:** twelve bare enum axes, the result-size gate, profile-creation secrets
  over MCP, five unreachable `dev/packaging` cases, import-hygiene ratchet, and wiring the core
  gates into `prek` / `just check-all` were handed to their owners. A live but unused CLI
  `deprecated_key` affordance still needs an atomic owner decision.
- **Error envelope API:** 636/636 codes carry `runbook_id=None`, but `cadrumo-harness` constructs
  `ErrorEnvelope` with the field and publishes its schema to MCP clients. Deletion is warranted on
  the merits but blocked on that cross-distribution contract change.
- **Retryability:** the field means repeating the identical call, unchanged, may succeed. Permanent
  causes must stay false; setting true for a permanent refusal can loop an autonomous agent without
  limit. The KDF refusal taxonomy stays `retryable=False`; recurrence guidance was shipped in all
  four language catalogues.
- **Repository line ratchet and environment:** `_validate.py` exceeded its line ceiling by one;
  virtualenv corruption recurred during the campaign. Do not bump a tally to force green; repair
  wiring/ownership and verify a healthy environment.

All these handed-off clusters were briefed to their owners. Do not re-investigate them, weaken the
assertions that expose them, or choose an authority/policy answer by inference. In particular, keep
the staged 0613 guardería formula separate from its declared binding until its Art. 81.2 basis is
re-grounded, and preserve the real AEAT submitted-file fixtures.

## Final reconciliation

On an isolated selection of `adapters/persistence/storage` plus `application/user_profile`, with no
CLI paths, final storage evidence was 172 integration and 1,545 unit tests with zero failures. The
full domain lanes later reached 361 integration and 1,705 unit tests green; a subsequent snapshot
was 361 integration, 1,703 unit, and 16 serial tests green. These are distinct scopes and
changing-tree snapshots. They do not make the whole repository green: the later sequential
whole-tree
measurement reproduced 314 failures across 120 modules, after environmental and flake cases were
separated.

Nothing remains open in storage itself. Remaining local actions are the interactive
`just test-os-keychain` run for 28 held-out tests and owner decisions listed above. Historical lane
counts include peer work and environment failures; each statement is bounded to its recorded run.
The audit records no live BOE/AEAT legal cross-check and no legal certification. Its value is the
implementation evidence, measurement caveats, and clear boundary between resolved storage defects,
known owner work, and claims only an authority can make.

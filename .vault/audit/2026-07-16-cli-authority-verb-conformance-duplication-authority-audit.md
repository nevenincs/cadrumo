---
tags:
  - '#audit'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-17'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-research]]"
  - "[[2026-07-15-cli-authority-verb-conformance-reference]]"
  - "[[2026-07-15-cli-authority-verb-conformance-adr]]"
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
  - "[[2026-07-15-cli-authority-verb-conformance-audit]]"
---

# `cli-authority-verb-conformance` audit: `Duplication authority and CLI conformance campaign`

## Product and campaign context

The CLI is an operator-facing authority surface, not merely a collection of command names. Each command must resolve to one canonical backend writer, resolver, custody boundary, or workflow, with matching schemas, locales, Model Context Protocol (MCP) mirrors, diagnostics, tests, and documentation. The campaign therefore limits renaming to a small pre-release hard cutover: only duplicate or materially misleading doors change, such as replacing weak `lock` behavior with strong profile `logout`, while the broader CLI remains stable.

Implementation proceeds backend first. The import architecture must be measurable and green before authority consolidation begins; profile, authentication, certificate, reset, evidence, export, and related services are then reduced to single owners before the accepted command grammar exposes them. Command removal and contract migration form one atomic batch, so no partially renamed or compatibility state can ship.

Duplication closure precedes verb conformance because conventional names cannot make duplicated behavior maintainable. A renamed command would remain misleading if another writer, parser, resolver, persistence path, or audit implementation could still perform overlapping work. The campaign therefore requires trustworthy duplication evidence, exact codebase searches, and canonical-owner proof before the final CLI surface is treated as authoritative.

## Audit purpose, status, scope, and substitutability

This audit determines whether the CLI exposes duplicate or misleading operator doors and whether those doors conceal parallel backend writers, weaker policy paths, or false-green governance checks. It is not a general vocabulary rewrite. Renames are justified only when a command materially misstates its effect or duplicates an existing intent; accurate, established verbs remain unchanged.

The governing decision in `2026-07-15-cli-authority-verb-conformance-adr` is accepted, but the implementation plan remains open. Recorded evidence covers the restored import-linter prerequisite and selected profile-logout work. Documentation evidence remains provisional. None of this constitutes a campaign-wide `PASS`, proves every backend authority is consolidated, or authorizes closure. Each remaining finding retains its own disposition until its implementation step, execution record, and verification evidence are complete.

The scope includes the materialized CLI, its application, domain, persistence, and adapter paths, and the infrastructure used to measure architectural and semantic duplication. It covers authentication and certificate custody, ledger evidence, profile export and subject access, hashing and replay, storage namespaces, filed capture, LLM review, registry projections, clone triage, and duplication reporting. It excludes a style-only rewrite of the broader command tree and preserves intentional distinctions such as logout versus destructive reset, portable export versus sealed recovery, scoped versus unscoped registry selection, and `classify --auto-split` versus `split --llm`.

Semantic search and clone reports provide candidate inventories, not duplication verdicts. Every candidate must be confirmed against the current tree through exact declaration, import, caller, consumer, and writer-path inspection. Previous research and audits are useful leads but do not replace current-source verification.

Before declaring duplication, apply the mandatory substitutability pre-filter: a proposed canonical authority may replace another path only if it accepts every input and state the existing path accepts and preserves the observable contract required by its consumers. Compare validation constraints, accepted formats, return and error shapes, defaults, provenance, persistence ownership, side effects, idempotency, and legal or safety guarantees. If the proposed replacement adds a restriction or changes policy, the paths are constraint-divergent and must remain separate or receive a specifically designed shared abstraction; similar names or implementation text are insufficient.

## Definitions

- `Canonical owner` — The single authoritative component that defines a behavior, policy, state transition, or metadata contract. Other surfaces may route to or project from it but must not independently reimplement its decisions.

- `Duplicate authority` — A second declaration or implementation that claims ownership of the same semantic contract as the canonical owner, even when its code, name, or layer differs.

- `Parallel writer` — Any additional path capable of mutating the same durable state outside the canonical writer's complete validation, transaction, locking, event, and failure policy.

- `Substitutability` — The condition in which two paths accept equivalent inputs, promise equivalent outcomes, enforce equivalent constraints, and can replace one another without observable policy or state differences. Similar implementation mechanics alone do not establish substitutability.

- `Constraint divergence` — A difference in authorization, validation, locking, atomicity, persistence, recovery, event sequencing, failure handling, legal intent, or output contract that makes superficially similar paths non-equivalent.

- `Compatibility shadow` — A retained alias, fallback, migration branch, legacy selector, dormant route, schema field, or documentation path that preserves an obsolete contract alongside its replacement. Under pre-release hard cutover, compatibility shadows are removed rather than maintained.

- `False-green` — A successful health verdict produced without valid evidence of the property being measured, such as treating an unavailable, failed, timed-out, empty, or unparseable duplication scan as an observed zero.

- `Duplication closure` — Evidence that one canonical owner remains, all duplicate authorities and unauthorized parallel writers are removed or explicitly classified as intentionally distinct, surviving consumers route through the owner, recurrence gates prevent reintroduction, and verification observed the complete intended production surface without false-green conditions.

## Evidence protocol

Each audit pass begins with fresh `vaultspec-rag` searches over the code and vault indexes to locate likely authorities, overlaps, governing decisions, and prior evidence. Semantic results are discovery inputs, not proof. Every candidate is confirmed against the current tree with exact searches for declarations, imports, exports, factories, callers, consumers, writers, persistence boundaries, CLI routes, schemas, tests, documentation, and generated surfaces.

Potential overlaps are then compared for substitutability. The review checks whether they accept equivalent inputs and enforce the same authorization, validation, locking, atomicity, recovery, event sequencing, failure policy, and observable result. Shared mechanics or similar text do not establish duplicate authority when constraints or intent differ.

Audit instruments are validated before their output is trusted. The review confirms that each scanner inspected the intended production scope, completed successfully, returned parseable evidence, and distinguished observed results from unavailable or invalid measurement. Clone output identifies candidates for semantic inspection; it is not, by itself, a duplication verdict.

Each candidate receives an explicit disposition: consolidate under a canonical owner, remove as a compatibility shadow, retain as intentionally distinct with the differentiating constraint recorded, or defer with a named blocker. Every actionable disposition is assigned to a specific plan step and cohesive implementation scope.

Closure requires attributable evidence after implementation: exact absence or routing checks, real-behavior tests, recurrence gates where appropriate, focused and whole-surface quality gates, execution records, and formal review. A cluster closes only when one canonical owner remains, surviving consumers use it, no unauthorized parallel writer or obsolete route survives, and the supporting instruments produced valid current-tree evidence.

## Instrument trustworthiness

The recorded import-linter run is trustworthy for its captured tree state. The isolated, frozen execution analyzed 3,425 files and 16,179 dependencies, kept all five architecture contracts, and reported zero broken contracts. The completed prerequisite also carries non-vacuous reconciled ratchet inventories. This is direct execution evidence over the intended `cadrumo` production package, not an empty parse or cached verdict.

The recorded direct clone run produced candidate evidence: `just audit-duplication` observed 65 clone groups and 0.4% duplicated lines in the current production tree. Those groups are candidates for semantic classification, not 65 automatic consolidation mandates.

The aggregate health report is not trustworthy for duplication closure. In the same working tree, `python -m dev.audit.report --json --full` reported duplication `green` with `no clones found`. Its separate Windows invocation renders the production path as `src\cadrumo`; `jscpd` can inspect no intended source files, return no summary, and still be reduced to zero. The report captures the scanner process result but does not inspect the return code or standard error, carry diagnostic state into its verdict, or require a parseable summary before assigning green.

Duplication closure therefore depends on repairing `dev.audit.duplication`, `dev.audit.report`, and the `justfile` integration first. One platform-neutral typed runner must own source selection, command construction, execution, timeout handling, standard output, standard error, return code, parsing, clone records, and availability classification. Only successful, parseable execution that demonstrably observes the production tree and finds no clone clusters is observed zero. Missing executables, timeouts, non-zero exits, failed execution, empty evidence, or unparseable output are unavailable evidence and must remain visibly amber rather than collapse into zero.

## Actionable cluster inventory

| Cluster | Current overlap or risk | Accepted authority or disposition | Priority | Plan ownership |
|---|---|---|---|---|
| Import-linter architecture gate | Architecture enforcement was previously degraded by the wrong package root and vacuous or stale ratchets. | `.importlinter` targets `cadrumo`; all five contracts and non-empty inventories must pass uncached before and after the campaign. | Critical | `W01.P01.S01-S11`, `W01.P02.S12-S17`, `W01.P03.S18-S23`, `W06.P19.S194` |
| Active profile, logout, and reset | Pointer mutation, teardown, deletion, and reset could diverge or leave active state dangling. | One reentrant pointer transaction; strong profile logout closes resources before clearing the pointer; all-profile reset composes the established profile, retention, auth, certificate, and pointer authorities. | Critical | `W02.P04.S24-S36`, `W02.P05.S54-S70`, `W04.P11.S96-S104`, `W06.P18.S177` |
| Authentication custody | Session logout and destructive reset were under-specified and could omit persisted sessions or locks. | Separate typed auth logout and reset operations with explicit provider or all scope and target-scoped cleanup. | Critical | `W02.P06.S37`, `W02.P06.S43-S46`, `W04.P13.S115`, `W04.P13.S117`, `W04.P13.S119`, `W06.P18.S179` |
| Certificate credential custody | A certificate-specific keyring backend, selector, exports, flags, schemas, tests, and documentation duplicate secure-storage custody. | Delete the certificate-specific keyring backend and compatibility surface; selected-profile secure storage is the sole certificate-secret authority. Independent master-key OS-keyring custody remains untouched. | High | `W02.P07.S47-S52`, `W04.P13.S116`, `W04.P13.S118`, `W05.P15.S238`, `W06.P18.S179` |
| Passphrase and recovery custody | Related custody operations risk sharing grammar or secret-handling paths without preserving distinct recovery semantics. | Keep passphrase change and recovery as distinct typed authorities with secure input, explicit file custody, and secret-free envelopes. | High | `W02.P21.S71-S80`, `W04.P12.S105-S114`, `W05.P15`, `W05.P16`, `W05.P17`, `W06.P18.S178` |
| Ledger evidence | Generic patches and combined invoice/evidence linking can bypass replacement policy or partially commit. | Evidence attachment owns validation, replacement, custody, catalogue mutation, and events; invoice linking remains invoice-only and atomic. | High | `W03.P08.S81-S83`, `W03.P08.S224-S225`, `W04.P14.S120`, `W04.P14.S122`, `W06.P18.S180` |
| LLM review workflow | Suggest, apply, reject, saturation, and split routing are distributed, and invocation provenance can default to CLI spelling inside application code. | One typed application workflow with mandatory invocation origin, delegating durable writes to ledger authorities while retaining distinct operator intents. | High | `W03.P24.S250-S253`, `W06.P18.S264` |
| Portable export and subject access | Two CLI-owned writers duplicate serialization, directory creation, publication, and event sequencing. | One durable `export_profile_bundle` service with portable and subject-access purposes, same-target locking, recoverable preparation, atomic publication, schema-derived categories, and equal cleartext handoff-risk classification. | High | `W03.P09.S84-S89`, `W04.P11.S237`, `W05.P16.S145`, `W05.P17.S239`, `W06.P18.S181` |
| One-shot and file hashing | Eighteen exact one-shot bodies and four reducible file-hash bodies repeat substitutable mechanics. | `core.hashing.sha256_hex` and `core.hashing.hash_file` own shared mechanics; callers retain byte projection, domain separation, truncation, streaming, and distinct cryptographic semantics. | Medium | `W03.P10.S90-S93`, `W03.P10.S226-S235`, `W06.P18.S241` |
| Evidence replay | `EvidenceBundleService.replay` duplicates integrity checking without reproducing stored-input outcomes. | Remove backend replay, CLI route, result schema, event/token, tests, documentation, and generated projections; retain evidence check and unrelated observability replay. | High | `W03.P10.S236`, `W04.P14.S121`, `W04.P14.S123`, `W05.P15.S238`, `W05.P17.S240`, `W06.P18.S182` |
| Secure-object namespaces | Namespace metadata is redeclared across consumers, and adoption checks can pass without proving binding. | `STORAGE_NAMESPACE_REGISTRY` is the sole metadata authority; production consumers bind to registered definitions through the canonical contract. | High | `W03.P22.S242-S246`, `W06.P18.S262` |
| Filed observation capture | Selection, ordering, persistence, and failure finalization are split between capture and persistence modules. | The persistence authority owns selection, ordering, and writes; one typed finalizer preserves fail-fast, best-effort, and separate strict IVA policies. | High | `W03.P23.S247-S249`, `W06.P18.S263` |
| Registry resolution and projections | Scoped and unscoped queries repeat report construction, while accepted unscoped `as_of` can be ignored. | Preserve distinct selectors, produce one typed resolved context, share only substitutable projections, and make `as_of` effective or reject it. | High | `W03.P25.S254-S257`, `W06.P18.S265` |
| Duplication audit infrastructure | `just`, `dev.audit.duplication`, and `dev.audit.report` independently invoke or parse `jscpd`; invalid evidence can become green. | One typed platform-neutral runner owns execution and evidence taxonomy; report and Just consume it; only observed zero is green. | High | `W03.P26.S258-S261`, `W06.P18.S266`, `W06.P19.S203-S207` |

## Intentional non-consolidations

- Custody operations remain distinct: passphrase change rotates access to the existing vault, while recovery creates, rotates, verifies, or consumes an independent recovery capability. Profile logout closes local profile resources. Auth logout removes scoped AEAT sessions while preserving provider and certificate configuration; auth reset destructively clears scoped provider configuration, sessions, locks, certificate registrations, and bound secrets. Google logout terminates a separate external OAuth session.

- Evidence operations retain different invariants: `doclink` acquires and stores bytes before delegating to canonical attach; it is composition, not a second evidence writer. Attach creates evidence custody, while invoice link establishes an atomic invoice-only relationship. Evidence export intentionally invokes evidence check as a precondition before publishing an artefact; check remains the verifier. Listing is read-only discovery, whereas review applies a decision workflow.

- Lifecycle and export families remain separate: sandbox discard removes a selected sandbox, while prune applies retention-based cleanup. Portable export and subject-access export share durable publication machinery but retain distinct purposes and legal discoverability; the sealed recovery archive has different confidentiality and restoration semantics.

- Authentication and identity checks are not interchangeable: auth status reports recorded state, while auth test performs a live provider check. GROI and NIF validation retain different identifier rules. Legal resolver families remain separate where tax, period, jurisdiction, evidence, or revision constraints differ.

- Similar interaction paths do not imply shared authority: Typer templates may share presentation structure without becoming one command implementation. The recipient registry manages authorized review-package recipients, while the replay guard prevents repeated processing. Invoice create performs the mutation; the wizard gathers and validates interactive input before invoking it.

- Registry and filing variants preserve meaningful policy differences: scoped and unscoped registry selection expose different resolution contexts. Strict IVA capture remains fail-fast and compensation-aware rather than inheriting bulk best-effort policy. `classify --auto-split` and `split --llm` share the typed LLM review workflow but retain distinct invocation origins and operator intent.

- Repeated iterator shapes and thin synchronous wrappers remain optional, low-priority review candidates. They are non-blocking unless exact evidence shows duplicated policy, state ownership, or persistence behavior rather than incidental structural similarity.

## Plan mapping and prerequisites

Execution follows a hard sequence: `W01` architecture recovery, `W02` core custody authorities, `W03` remaining backend consolidation, `W04` CLI cutover, `W05` contract migration, then `W06` verification. Backend phases may run in parallel only when exact file ownership is disjoint. Ledger evidence must precede LLM review where both modify split persistence. `W04` and `W05` execute sequentially but form one release checkpoint: no merge, release, or compatibility checkpoint may separate command removal from contract migration. Generated documentation follows the frozen live surface. Any corrective edit reopens its owning step and invalidates dependent verification evidence.

| Major cluster | Backend authority | CLI or contract cutover | Verification | Prerequisite |
|---|---|---|---|---|
| Architecture measurement | `W01.P01.S01-S11`, `W01.P02.S12-S17`, `W01.P03.S18-S23` | None | `W06.P19.S194` | Gates every later wave |
| Profile, logout, auth, certificate, reset, and recovery | `W02.P04.S24-S36`, `W02.P05.S54-S70`, `W02.P06.S37`, `W02.P06.S43-S46`, `W02.P07.S47-S52`, `W02.P21.S71-S80` | `W04.P11.S96-S104`, `W04.P12.S105-S114`, `W04.P13.S115-S119`, then `W05.P15`, `W05.P16`, and `W05.P17` | `W06.P18.S177-S179`, `W06.P19`, `W06.P20` | Pointer and logout precede reset; reset waits for auth and certificate authority |
| Ledger evidence and atomic splitting | `W03.P08.S81-S83`, `W03.P08.S224-S225` | `W04.P14.S120`, `W04.P14.S122`, then affected `W05` contracts | `W06.P18.S180` and whole-surface gates | Ledger evidence precedes overlapping LLM split persistence |
| Portable profile export and subject access | `W03.P09.S84-S89` | `W04.P11.S237`, `W05.P16.S145`, `W05.P17.S239` | `W06.P18.S181` | Stable profile and storage authorities |
| Hashing and replay retirement | `W03.P10.S90-S93`, `W03.P10.S226-S236` | Replay removal in `W04.P14.S121`, `W04.P14.S123`, `W05.P15.S238`, and `W05.P17.S240` | `W06.P18.S182`, `W06.P18.S241`, and recurrence checks | Canonical services must preserve byte and digest contracts |
| Secure-object namespaces | `W03.P22.S242-S246` | Consumers bind to the registry; no independent verb cutover | `W06.P18.S262` | Stable storage and custody boundaries |
| Filed observation capture | `W03.P23.S247-S249` | Existing routes delegate to one persistence authority | `W06.P18.S263` | Stable persistence boundaries |
| LLM review workflow | `W03.P24.S250-S253` | Both ledger CLI intents use the typed workflow | `W06.P18.S264` | Ledger evidence and split persistence land first |
| Registry queries and projections | `W03.P25.S254-S257` | Preserve supported query forms while removing duplicate projection mechanics | `W06.P18.S265` | Registry revision-selection authority remains distinct |
| Duplication audit infrastructure | `W03.P26.S258-S261` | `justfile` delegates to the typed Python runner | `W06.P18.S266`, `W06.P19.S203-S207` | Exclusive ownership of the peer-modified `justfile` |

Operational commands, recovery sequences, confirmation prompts, and exhaustive option tables remain owned by the operator how-to and generated CLI references. This audit records authority, dependency, and closure relationships only.

## Gathered and still-required closure evidence

| Area | Gathered evidence | Still required |
|---|---|---|
| Campaign status | The implementation plan reports `40/257` steps complete, one completed wave, four completed phases, and an execution-record identifier for every checked step. | `217` steps remain. The governing plan and `W02.P04.S31` execution record are modified; this audit and the `W04.P11.S98`, `W04.P11.S99`, `W04.P11.S103`, and `W05.P16.S223` records are untracked; the P26-owned `justfile` is modified. These artifacts remain provisional and do not provide durable final provenance. |
| Architecture prerequisite | W01 is complete with tracked execution records, independent review, a fresh uncached import graph, all five contracts kept, and focused real-behavior checks. | Rerun the uncached graph and ratchets after all implementation and contract changes. |
| Pointer and logout backend | The pointer/session phase is complete. Evidence covers atomic pointer handling, rollback, contention, session eviction, provider teardown, key zeroization, engine disposal, override refusal, and close-before-clear strong logout. | Revalidate these guarantees against the final integrated tree and any subsequent corrective edits. |
| Logout CLI, MCP, and documentation | Focused evidence exists for the canonical logout command, removal of `config lock`, MCP identity re-arming, generated references, executable documentation journeys, and rendered-page boundaries. | This evidence is provisional because relevant audit and execution records are untracked and affected surfaces remain dirty. Commit, attribute, reconcile, and rerun the final conformance lanes. |
| Remaining authority clusters | The accepted ADR, semantic research, exact source inventory, and expanded plan identify the required work for auth/reset, recovery, certificates, ledger evidence, portable export, hashing, replay, namespaces, filed capture, LLM review, registry queries, and duplication infrastructure. | These clusters remain open. Current-tree checks still find representative defects such as the certificate keyring backend and selector, backend evidence replay, duplicate export writers, direct hash bodies, split-then-patch LLM persistence, ignored unscoped `as_of`, and false-green duplication handling. |
| Contract migration | Target command grammar and required schema, locale, risk, help, MCP, documentation, sequence, reference, and terminology migrations are planned. | Most CLI cutover and contract-migration phases remain incomplete; removed spellings have not yet been proven absent across every source and generated surface. |
| Focused verification | Earlier completed steps carry attributable focused test and review results. | `W06.P18` is entirely open. Every amended cluster still needs its final real-behavior, failure-path, recurrence, and fresh-process verification. |
| Whole-surface conformance | W01 provides a trustworthy architecture baseline, and prior snapshots provide useful local evidence. | `W06.P19` is entirely open. CLI-tree, schema, locale, MCP, documentation, import, duplication, lint, test, collection, semantic, and exact-source audits must run against the final tree. |
| Formal closure | No current plan-structure error blocks continued execution. | `W06.P20` is entirely open. Formal code review, blocker resolution, invalidated-gate reruns, execution-record reconciliation, ADR requirement audit, Vault checks, feature-index rebuild, and fresh-context honesty review are all outstanding. |

Existing results are snapshot evidence from the revisions and working-tree states in which they were recorded. They reduce the remaining proof burden but cannot replace final reruns after the remaining implementation and reconciliation work. With `40/257` steps complete, `217` steps remaining, and `W06.P18`, `W06.P19`, and `W06.P20` wholly open, the campaign cannot be called closed.

## Authority sources and escalation

- Architecture authority: `2026-07-15-cli-authority-verb-conformance-adr` records the accepted decisions; `2026-07-15-cli-authority-verb-conformance-research` and `2026-07-15-cli-authority-verb-conformance-reference` hold the supporting evidence; `2026-07-15-cli-authority-verb-conformance-plan` controls sequencing, ownership, verification, and closure.

- Setup and operator guidance: `docs/workstation-setup.md` owns installation; `docs/how-to/quickstart.md` and `docs/how-to/onboarding.md` own first-use orientation. `docs/how-to/profile-setup.md`, `docs/how-to/protect-data-access.md`, `docs/how-to/authenticate-with-aeat.md`, `docs/how-to/ledger-evidence.md`, and `docs/how-to/import-bank-statements.md` own procedures. `docs/reference/commands-and-configuration.md` and `docs/reference/import-export-and-evidence.md` own stable command and artefact semantics. Live `aeat ... --help` owns exact syntax.

- Governing constraints: `aeat-architecture-boundaries`, `aeat-documentation-workflow`, `aeat-swarm-audit-cadence`, `aeat-swarm-orchestration`, `no-legacy-compatibility`, `service-imports-via-top-level-reexports`, `composition-service-no-parallel-write-path`, `plan-closure-requires-exec-records`, `full-tree-gate-must-distinguish-owner`, and `aeat-campaign-close-honesty-review` govern boundary direction, hard-cutover discipline, swarm discovery, audit method, documentation, evidence, and honest closure.

- Terminology authority: the curated sources and generated coverage under `src/cadrumo/_data/terminology/` control accepted product language. `terminology-single-declaration`, `terminology-scaffold-preserve-contract`, and `glossary-concepts-are-taxpayer-facing` prevent competing declarations. Generated terminology and CLI references are regenerated rather than hand-maintained.

- Normal escalation: defects, unclear behavior, and non-sensitive follow-up work belong in the project issue tracker with the affected command, canonical authority, observable evidence, and relevant plan step identified. Follow the redaction and diagnostic-gathering procedure in `docs/how-to/troubleshooting.md`.

- Architecture amendment: changes to accepted authority boundaries, command grammar, compatibility policy, or sequencing require an ADR amendment or superseding ADR before the implementation plan changes. They must not be introduced as incidental code or documentation changes.

- Formal acceptance: `vaultspec-code-review` reviews completed implementation steps and the complete feature diff. Closure requires zero blocker or major findings, attributable execution records, rerun conformance evidence, and the fresh-context honesty review.

- Security escalation: `SECURITY.md` owns the reporting channel and fallback policy. This audit does not restate it.

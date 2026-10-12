---
tags:
  - '#plan'
  - '#mcp-parity'
date: '2026-10-10'
tier: L2
related:
  - '[[2026-10-10-mcp-parity-parity-mechanism-adr]]'
  - '[[2026-10-10-mcp-parity-shared-sign-in-door-adr]]'
  - '[[2026-10-04-application-sign-in-adr]]'
  - '[[2026-09-26-mcp-purpose-authentication-adr]]'
  - '[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]'
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
  - '[[2026-06-30-ledger-add-idempotency-adr]]'
  - '[[2026-10-11-mcp-parity-full-parity-adr]]'
  - '[[2026-07-08-mcp-protocol-hardening-adr]]'
  - '[[2026-07-31-mcp-sdk-major-carry-adr]]'
  - '[[2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr]]'
modified: '2026-10-12'
body_schema: body-v2
body_hash: 'sha256:3a9a0b9a86c781f03a5d5454a53c27752164977306d7f4162cd77ff4e9574007'
---

<!-- RETIRED: P03, P07, S20, S21, S22, S23, S24, S25, S26, S31, S32, S36, S40, S41, S43 -->

# `mcp-parity` plan

Make the MCP server a full interface for the tax work the command line and terminal interface already implement, ending at a filing calculation and a local export, by deciding MCP admission per registered operation.

## Description

Approved 2026-10-10

The owner approved this plan first-hand on 2026-10-10, after reading its summary and the open decisions ("1 approved"), and set the execution pipeline: sonnet at high effort for well-defined, unambiguous tasks, opus for problem solving, and haiku for tool calls, testing and summarising code and context.

Amended 2026-10-11 on the owner's first-hand ruling, which is the authorization for phase `P08` and for retiring the Steps it replaces: "MCP should aboslutely NEVER refuse anyhting the cli can do. stop underminig the program", and "I want the cli tui and mcp to be partify. clic can do everythign so should the tui and mcp. no more qesitons". `2026-10-11-mcp-parity-full-parity-adr` records it and supersedes the admission rulings; the four proposed records on the approval step, file exchange, replay identity and agent provenance are rejected. The phases on the approval step and on admitting sensitive acts behind it are removed, with the Steps that waited on those records. Statements below that an operation is refused, held back, admitted behind approval or waits on file exchange describe the plan as first approved and no longer hold: every operation the command line can submit is submittable from the terminal interface and from MCP with the same decision, effect and result. Refusals built in earlier Steps of this plan are removed in `P08`.

Amended 2026-10-12: phase `P10` is authorized by the owner's first-hand ruling of 2026-10-12 recorded in `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`, which governs it: the agent never authenticates or manages authentication, never handles a secret, runs only inside the one signed-in profile, and does not run at all without a live sign-in or an API key the person issued and configured by reference. Only one profile is signed in at a time. API keys stay and the runtime manages them. That record narrows `2026-10-11-mcp-parity-full-parity-adr` to operations inside the bound profile, so the session and installation tools built in `P09.S59` and the secret carriage built in `P08.S50` and `P09.S62` are removed by `P10`, and statements below that MCP carries a secret or serves those acts no longer hold. The orchestrator applied four defaults while the owner was away. The owner confirmed all four on 2026-10-12 ("i followw your recommedation"), and they are no longer provisional; the agent-inside record carries them as binding (amended 2026-10-12 on the owner's ruling "i followw your recommedation"; before that each was provisional and the owner could confirm or change it):

- (a) MCP's `authorization_prepare`, `authorization_request` and `authorization_poll` key-request flow is removed. Keys are issued only by the person through `config automation` and given to the MCP server by reference in its launch configuration.
- (b) A sign-in to profile B while A is signed in signs A out everywhere: A's sessions, agents and key sessions that depend on A's sign-in. Keys issued for A that work without a sign-in are not ended by it.
- (c) With no live sign-in and no valid key, MCP answers only the handshake, the tool list and `status`, which says to sign in to Cadrumo. Everything else is refused, the public reference and corpus queries included.
- (d) An agent session timing out ends that agent session only. A resumed sign-in ends when the person's sign-in ends.

Amended 2026-10-12: phase `P11` is authorized by the owner's first-hand ruling of 2026-10-12, "i followw your recommedation", which accepted the orchestrator's recommendations, recorded in `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr` (constraints 7 and 9) and `2026-09-26-mcp-purpose-authentication-profile-access-adr` (enrollment step 2). The `status`, `session` and similar replies carry a count and a per-category summary of `effective_scope.disclosures`, with the full list read on request through a paged read, the same on every frontend; today these replies are about 125,000 characters, over agent client output limits. A key the person issues with `config automation create` on the CLI or the TUI names its use, for an agent (MCP), and its data categories, and its results are released to whichever local MCP client presents it; today a CLI-issued key carries no disclosure, so its MCP server submits work but reads no value back. The same ruling settled the receipt-sealing key for `P02.S18` and confirmed (a) to (d) above. It left the off-host consent record unchanged, since MCP can no longer give off-host consent, and it does not cover admission refusals inside the person's own profile, which stay open. The idle extension itself, re-sealing the receipt with the sealing key, is lifetime work of `2026-10-04-application-sign-in-plan`, which has no Step for it; this plan adds none.

The goal is the owner's: the MCP server reaches every tax capability that the command line and terminal interface offer, through the operation registry and the sixteen existing tools, and never through the command line. The end of the work is a calculated and verified declaration and a local export. Fixed boundary, not open to any Step: nothing here designs, builds or supports sending data to the tax agency in a way that changes its state. `modelo.export` writes a local file and `modelo.work.file` writes a local record. The only work that touches that boundary is `P01.S01`, which adds a test that fails if any operation or tool ever declares a submission.

Decision coverage. Three accepted records of this feature govern, with the accepted records they amend:

- `2026-10-10-mcp-parity-parity-mechanism-adr` governs the recorded decision and its check (`P01.S01`), refusal at submission and the named surface (`P01.S05`, `P01.S06`), confined host paths and discovery (`P01.S07` to `P01.S09`), and the admission checklist used by every Step of `P04` to `P07`.
- `2026-10-10-mcp-parity-shared-sign-in-door-adr` governs `P02`, with `2026-10-04-application-sign-in-adr` and `2026-09-26-mcp-purpose-authentication-profile-access-adr` as amended on 2026-10-10.
- `2026-10-10-mcp-parity-admission-rulings-adr` governs which operations are refused until the approval step exists (`P01.S02` to `P01.S04`), admitted (`P04`, `P05`, `P06`) or admitted behind the person's approval (`P07`), and the hand-off rule applied to the packaged agent material (`P01.S10`), with `2026-07-02-agent-harness-refoundation-adr` as amended. Its rule is the owner's, given first-hand on 2026-10-10: every ledger operation is operable by an agent, an agent has full control of the person's data and operations, and the person approves the sensitive ones.
- `2026-06-30-ledger-add-idempotency-adr` governs the caller-supplied key that `P03.S22` extends and `P05.S31` requires.

Four decisions are not covered by any accepted record. `P03.S20` to `P03.S23` record them, and the Steps that depend on each wait for its acceptance: the approval step taken in Cadrumo (`P03.S24`, `P03.S25` and all of `P07`), file exchange (`P06.S36`, `P06.S43`), the replay identity (`P05.S31` onward) and the provenance of amounts an agent states (`P05.S31`).

The approval step is on the critical path. Under the owner's rule every sensitive operation is admitted, and each is refused on MCP until that step exists, so `P03` follows `P01` directly and `P07` follows `P03`.

Owner rulings received on 2026-10-10 and carried by the Steps named:

- An agent can and should be able to originate `modelo.reconcile.import`, and the person always reviews or approves its findings (`P01.S11`).
- A message the person sends to the assistant counts as their activity; the assistant's own calls, commands and scripts do not (`P02.S18`). Until the idle extension of the sign-in record is built, every session from a sign-in, the MCP server's included, ends 15 minutes by default after the password was typed.
- Approval of a sensitive act applies to operations submitted through MCP, and an admitted write that is not sensitive lands with nobody confirming each one (`P05`, `P07`).

Still open with the owner, each gating only the Step named:

- Ruled on 2026-10-10: an MCP client may end only its own session; it may not sign the person out or lock another session (`P02.S17`).
- Ruled on 2026-10-12 ("i followw your recommedation"): the receipt-sealing key lives in the profile worker's memory beside the session's DEK only while a live session exists, zeroised with it when the last lease ends, and the runtime never reads the keychain (`P02.S18`). (Amended 2026-10-12 on that ruling; before that it was open, a security choice the sign-in record named as a follow-on.)
- Which acts count as sensitive is the rulings record's own classification, for example the three prorrata elections; the owner corrects it by naming an operation.

Evidence is in the six reference and research records of this feature. All of it is static reading at commit `85f84a2680`; nothing was run. Each record's "Not verified" list names what a Step must establish before it relies on it, in particular whether operations repeat the validations the command line performs, and what the verify executor exchanges while checking provider readiness (`P06.S38`).

Overlap with plans in flight, to coordinate and not to duplicate: `2026-10-04-application-sign-in-plan` owns the sign-in generation, global sign-out, session events and the interactive-terminal gate, and implements no receipt extension; `P02` builds on that work and `P02.S16` and `P02.S18` change behaviour it owns. `2026-09-26-mcp-purpose-authentication-plan` still lists the MCP adapter and its cross-interface proof as open Steps, and its proof of an MCP reconnect after a human time-out now holds for the key route only. The worktree is shared with other sessions; each Step stages only its own files.

## Steps

### Phase `P01` - make the already-open MCP surface safe

Delivers the recorded MCP decision for every operation, the refusal of the sensitive operations that are open today with no approval, refusal at submission, and confined host paths, so that opening the shared sign-in exposes nothing unguarded.

- [x] `P01.S01` - Add the recorded MCP decision table, one row per registered operation with its ruling, reason and whether it changes records or reaches the network, seeded from the admission rulings, and extend the catalogue test to fail on an operation with no row, an admitted row the real access resolver refuses to the MCP frontend, an excluded row that still lists MCP, a human-only policy that admits MCP, and any operation or tool that declares a submission to the tax agency; creates src/cadrumo/application/operations/mcp_admission.py; `src/cadrumo/entrypoints/tests/test_operation_catalogue.py`.
- [x] `P01.S02` - Refuse on the MCP frontend, until the approval step exists, the sensitive operations that are open today with no approval: ledger.invoice.remove, auth.session.reset, the writes of ledger.own_account, the declare and remove actions of modelo.m360_solicitud and the three prorrata elections, with a refusal test for each and one contract cutover; also auth/operation_definitions.py, ledger/own_account_operation.py, modelo/m360_solicitud_operation.py and prorrata_register/registered_operations.py; `src/cadrumo/application/invoices/catalogue_remove_operation.py`.
- [x] `P01.S03` - Refuse on the MCP frontend, until the approval step exists, a capability opt-in whichever operation writes it (the capability paths of user-profile.field-mutation and the capability answers of user-profile.patch) and the census review, whose apply cannot be held back alone because apply, reject and inspect evaluate as one access action; also user_profile/censal_operation.py; `src/cadrumo/application/user_profile/profile_operation_access.py`.
- [x] `P01.S04` - Remove the MCP claim from the seven definitions that cannot run: the four automation proposals, export.google-sheets, local-reader.provision and user-profile.bundle-export; also export/google_operation.py, local_reader_operation.py and user_profile/operations.py; `src/cadrumo/application/user_profile/automation_operations.py`.
- [x] `P01.S05` - Refuse at submission, where the frontend list is refused today, a mutating operation to a session whose scope lacks the commit action, so that no browser, classifier or subject lease is taken first; `src/cadrumo/application/user_profile/operation_access_policy.py`.
- [x] `P01.S06` - Define the named served surface as tool names, declared properties and an operation list held by Cadrumo, carry its name from the server launch to the runtime, and refuse at submission an operation outside it or one that changes records or reaches the network on a read-only or local surface, with a test over the whole operation list; also src/cadrumo_harness/mcp/main.py and protocol_contract.py; `src/cadrumo/application/user_profile/operation_access_policy.py`.
- [x] `P01.S07` - Create a shared host-path confinement guard that verifies the opened handle against roots taken from existing settings, and apply it to modelo.reconcile.import and the six live capture operations that take an output root; applies under src/cadrumo/application/live and modelo/reconciliation_import_operation.py; `src/cadrumo/core/path_confinement.py`.
- [x] `P01.S08` - Repair discovery in the generic tools: bound and page search, filter it by family, cache contracts within a session, report a refused operation without failing the search, and read a result by operation identifier alone; also operation_search.py and protocol_contract.py; `src/cadrumo_harness/mcp/admitted_operations.py`.
- [x] `P01.S09` - Generate the join from command-line commands to the operations they submit, from the command graph and the registry, and check it in the catalogue test; `src/cadrumo/entrypoints/cli/operator_surface_reconciliation.py`.
- [x] `P01.S10` - Bring the packaged personas and skills into line with the amended hand-off rule: no persona or skill tells an agent to export or record the filed marker without the person approving, and the stale provider-configuration instruction and capability-manifest inputs are removed; also skills/cadrumo-exportar-declaracion/SKILL.md and skills/cadrumo-alta-contribuyente/SKILL.md; `src/cadrumo_harness/_data/agent/personas/cadrumo-verifier.md`.
- [x] `P01.S11` - Record in the decision table the owner ruling that an agent may originate modelo.reconcile.import, and keep it admitted with its findings presented for the person to review or approve; `src/cadrumo/application/modelo/reconciliation_import_operation.py`.
- [x] `P01.S45` - Declare a typed subject-reference form on the operation definition and its public contract, filled from the validator of each family, and state it in describe, with one contract cutover for every definition; `src/cadrumo/application/operations/operation_definition.py`.

### Phase `P02` - open the shared sign-in door to the MCP server

Delivers an MCP server that resumes the person's sign-in for the exact profile, answers its tool list with no session, and stops when the sign-in ends.

- [x] `P02.S12` - Admit the receipt login method from the MCP frontend in the runtime login validation, keeping the password method and receipt persistence refused there; `src/cadrumo/entrypoints/runtime/profile_connection_admission.py`.
- [x] `P02.S13` - Give the MCP adapter a resume path used when it holds no credential reference, require the profile launch argument only with a credential reference, and answer initialization, the tool list and public queries with no session and no profile; also runtime_admission.py, main.py and server.py; `src/cadrumo_harness/mcp/runtime_adapter.py`.
- [x] `P02.S14` - Handle session retirement in the MCP adapter from the pushed session events: refuse with the existing refusal shape, drop the session, and resume only when a later call finds a live sign-in; `src/cadrumo_harness/mcp/runtime_adapter.py`.
- [x] `P02.S15` - Trace whether a sign-in lease is bound through the worker five-minute in-process idle window, record the finding in the sign-in doors reference, and correct the window if a long-lived session would be refused before its lease ends; `src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py`.
- [x] `P02.S16` - Settle with the owner of the sign-in work whether a login or generation mismatch may delete the stored sign-in before the presented proof is verified, and verify the proof first if not; `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py`.
- [x] `P02.S17` - Refuse the global sign-out and the lock of a session other than its own to a session on the MCP frontend, which may end only itself, as the owner ruled, with a refusal test for each; `src/cadrumo/entrypoints/runtime/profile_connection_sessions.py`.
- [x] `P02.S18` - Record as an amendment to the application sign-in record the owner ruling that a message the person sends to the assistant counts as their activity and the assistant own calls, commands and scripts do not, together with the decision, ruled 2026-10-12, that the receipt-sealing key lives in the profile worker memory beside the session DEK only while a live session exists, so the idle extension can be built; `.vault/adr/2026-10-04-application-sign-in-adr.md`.
- [x] `P02.S19` - Prove the door against a running runtime with a synthetic encrypted profile: resume, refusal with nobody signed in, the tool list with no session, sign-out and idle expiry ending the MCP session, no MCP submission advancing the deadline, the password refused, and the key route unchanged; `src/cadrumo_harness/mcp/tests`.

### Phase `P04` - admit the reads

Delivers the ratio, work, workflow and evidence reads on the MCP frontend, each through the admission checklist, with one contract cutover per family.

- [x] `P04.S27` - Admit ledger.ratios.list, ledger.ratios.eligible, ledger.ratios.validate and ledger.rule.list to the MCP frontend through the admission checklist, with one contract cutover for the family; `src/cadrumo/application/ledger/ratios_operation.py`.
- [x] `P04.S28` - Admit the work reads ruled admitted, from modelo.work.list to modelo.work.filing_record and profile.history, with the three workflow reads, config.collab.recipient.list and the three Google configuration reads, each after its result is checked fit for an agent host and with an agent-facing sibling where it is not, with one contract cutover per family; starts at work_inventory_operation.py and revision_selection_operation.py; `src/cadrumo/application/modelo`.
- [x] `P04.S29` - Admit the eight evidence reads ruled omissions once each result is shown, inside the operation, to carry no evidence bytes, with one contract cutover for the family; `src/cadrumo/application/ledger/evidence_read_operation.py`.
- [x] `P04.S46` - Give an agent-facing projection to each read whose result carries a host path, verbatim document text, an open payload or a human-only resolver, and admit it: ledger.evidence.list, ledger.evidence.view, ledger.evidence.review.view, ledger.evidence.reader-readiness, modelo.filing_record.view, profile.history and the three Google configuration reads; `src/cadrumo/application/ledger/evidence_read_operation.py`.

### Phase `P05` - admit every ledger write that is not sensitive

Delivers the ledger entry, ratio, rule, attachment, evidence and reversible lifecycle writes on the MCP frontend with their command-line safeguards moved into the operations, so that an agent can operate the whole ledger.

- [x] `P05.S30` - Move the validations the command line performs before submitting ledger add, update and single classification into those operations, with the same refusals; `src/cadrumo/entrypoints/cli/_ledger.py`.
- [x] `P05.S33` - Admit ledger.ratios.set, its inverse ledger.ratios.unset, ledger.rule.add and ledger.rule.apply; also rule_operation.py; `src/cadrumo/application/ledger/ratios_operation.py`.
- [x] `P05.S34` - Admit ledger.attach and ledger.detach, which act on stored evidence by identifier, after the evidence reads; `src/cadrumo/application/ledger/attachment_mutation_operation.py`.
- [x] `P05.S35` - Move the confirmations of the manual split and of archive, stash, restore and exclude into their operations and admit all five; also lifecycle_mutation_operation.py; `src/cadrumo/application/ledger/split_operation.py`.
- [x] `P05.S42` - Admit ledger.evidence.update, ledger.invoice.wizard and ledger.participation.rebuild, and ledger.evidence.extract for the reader on the machine with the off-machine read refused until the approval step carries that consent; also invoices/catalogue_intake_operation.py, participation_rebuild_operation.py and invoice_evidence_extract_operation.py; `src/cadrumo/application/ledger/evidence_mutation_operation.py`.

### Phase `P06` - admit document intake and declaration preparation

Delivers statement, invoice-book and evidence intake and the file exports under the file-exchange decision, and declaration create, calculate, amend, rename and verify, ending at a calculated and verified revision.

- [x] `P06.S37` - Admit modelo.work.create, modelo.work.calculate and modelo.work.rename with the actor taken from the session and not from the caller; the applicability gate already lives in the create operation, a recalculation deletes nothing and its result names the revision it replaced, and a calculation that states its own inputs, the joint-return election or the Modelo 390 attestation is refused on MCP until the approval step exists; modelo.work.amend moves behind the approval step because it records a local filing; also work_create_operation.py and metadata_operation_access.py; `src/cadrumo/application/modelo/operation_definitions.py`.
- [x] `P06.S38` - Read the modelo.work.verify executor end to end, record what it reads and what it exchanges while checking provider readiness, and admit it only if it changes nothing and sends nothing that alters remote state; `src/cadrumo/application/modelo/operation_definitions.py`.
- [x] `P06.S39` - Remap the packaged skills from command-line verbs to operations through the generated join, and prove one quarterly and one annual declaration prepared through MCP alone equal to the command-line result for the same inputs; `src/cadrumo_harness/_data/agent/skills`.
- [x] `P06.S44` - Admit modelo.observation.local, modelo.m145.create and modelo.m145.validate, refusing on MCP the variants that discard a figure or stand for a signature; modelo.filing_record.import moves behind the approval step because it writes a record marked as confirmed by the tax agency from values the caller states; also local_observation_operation.py and m145_communication_operation.py; `src/cadrumo/application/modelo/filing_record_import_operation.py`.

### Phase `P08` - parity with no frontend-specific refusal

Delivers the owner's rule of 2026-10-11: the command line, the terminal interface and MCP are at parity. Every operation is submittable from every frontend with the same decision, effect and result; every refusal, narrowing and reduced result built for one frontend is removed; and MCP is given the means to carry what the command line carries. Replaces the approval, file-exchange and held-back admission work, which that rule rejects.

- [x] `P08.S47` - Make every registered operation submittable from the command line, the terminal interface and MCP, reduce the decision table to the two facts the opt-in surface needs, and replace the tests that held rulings with tests that hold parity: every operation on every frontend, the same resolver decision for the same request, and no comparison of a frontend inside an access path outside a short allow-list; `src/cadrumo/application/operations/mcp_admission.py`.
- [x] `P08.S48` - Remove every frontend-specific refusal, guard and reduced result from the ledger, invoice, inventory and prorrata operations, keeping attribution and the recorded origin of a classification as facts; `src/cadrumo/application/ledger`.
- [x] `P08.S49` - Remove every frontend-specific refusal and reduced result from the modelo, workflow, live and export operations, and give a resolver to any operation that had none so it can be submitted; `src/cadrumo/application/modelo`.
- [x] `P08.S50` - Remove every frontend-specific refusal from the profile, authentication and Google operations and from the runtime's release of results and session acts, and give the MCP harness the means to carry a typed secret and to answer every interaction kind; `src/cadrumo_harness/mcp`.
- [x] `P08.S51` - Rewrite the user documentation, its translations and the packaged agent text to say that an agent runs every operation the command line can, keeping the agent's own conduct before a destructive act as guidance and not as a product gate; `src/cadrumo_harness/_data/agent`.

### Phase `P09` - give every command-line command a form all three frontends reach

Delivers the rest of parity: about forty-five command-line commands do their work in the command-line process, with no registered operation and no runtime request, so the terminal interface and MCP cannot do what they do. Each becomes a registered operation, a sessionless runtime request with a tool in the harness, or a query of the published authority, and the command line submits the same thing. Authorized by the owner's ruling of 2026-10-11 recorded in the full-parity record.

- [x] `P09.S52` - Build the sessionless runtime door for installation acts: the request family, its admission as the bootstrap delete handler admits, secrets in and the recovery code out, the client on the verified connection, and the command line's submitter; `src/cadrumo/application/runtime/installation_requests.py`.
- [x] `P09.S53` - Make provisioning a registered operation for every verb: widen local-reader.provision, add local-reader.status, local-reader.report and browser-runtime.provision, and have the command line submit them; `src/cadrumo/application/local_reader_operation.py`.
- [x] `P09.S54` - Register the repair operations that need a profile (secure-object check and quarantine, workflow progress reset, connectivity probe) and build the repair acts that need none (report, logs, profile pointer); `src/cadrumo/application/diagnostics.py`.
- [x] `P09.S55` - Build the storage acts and the acts of the reset of all profiles, and have the command line send them; `src/cadrumo/application/storage_management/service.py`.
- [x] `P09.S56` - Build the profile acts (list, archive inspect and import, recovery enrolment), register recovery revocation, and move into the operations what the censo import, archive export and profile delete commands did on the caller's side; `src/cadrumo/application/user_profile`.
- [x] `P09.S57` - Serve the reference reads (modelo catalogue, categories, portals, authentication providers, apoderado scopes) from one application service through the extended authority query, for all three frontends; `src/cadrumo_harness/mcp/authority_query.py`.
- [x] `P09.S58` - Build the review-package and report verification acts and move into the reconcile pull and report verify operations what their commands did on the caller's side; `src/cadrumo/application/modelo`.
- [x] `P09.S59` - Give the MCP harness an installation tool for the installation acts, with secrets on the protected frame and recovery enrolment on the session tool; `src/cadrumo_harness/mcp/protocol_contract.py`.
- [x] `P09.S60` - Give the terminal interface a destination that runs every registered operation, with typed secrets and the input and choice interactions it refused, and destinations for the installation acts, reachable before sign-in, and the reference reads; `src/cadrumo/entrypoints/tui`.
- [x] `P09.S61` - Wire the new operations and acts into composition and the surface facts, regenerate the command table to record runtime-request rows, and prove with one suite that every command-line leaf has an operation or a runtime request and that the three frontends agree on each result; `src/cadrumo/entrypoints/operation_composition.py`.
- [x] `P09.S62` - Let a tool call name a secret the person stored at a terminal by reference beside the typed argument, report an unresolved outcome as an outcome and not a tool error, mark the pure reads read-only, and test the handshake-free protocol revision; `src/cadrumo_harness/mcp/protocol_contract.py`.
- [x] `P09.S63` - Carry the request model's faults, without values, on the runtime's invalid refusal so MCP names the field and the rule, and answer search and describe from the public contracts with no session, as the command line's help does; `src/cadrumo/entrypoints/runtime/operation_host.py`.

### Phase `P10` - keep the agent inside the one signed-in profile

Delivers the owner's ruling of 2026-10-12: MCP carries no secret and offers no authentication, session, access or installation act; the runtime refuses those acts and every operation that needs a typed secret on the MCP frontend; one profile is signed in at a time; an MCP server is bound to one profile and does nothing but answer its handshake, tool list and status without a live sign-in or a key the person configured; and the desktop shows its sign-in view on every loss of sign-in.

- [x] `P10.S64` - Remove from the MCP server every tool and argument that signs in, administers sessions or access, carries or names a secret, or acts outside the bound profile: the session, installation, authenticate and authorization tools, the secret arguments of execute and the held-secret commands, keeping the key named by --credential-reference in the launch configuration, and replace the tests that proved them with tests of their absence; `src/cadrumo_harness/mcp/protocol_contract.py`.
- [x] `P10.S65` - Refuse on the MCP frontend, in the runtime, the password login, enrollment, password reset, recovery, profile resume and deletion, session inventory, lock, sign-out, automation denial and installation acts, and every operation whose contract requires a typed secret, with one typed refusal that names the act as the person's, keyed on the act through one predicate the frontend scan lists with its reason; `src/cadrumo/entrypoints/runtime/profile_connection_admission.py`.
- [x] `P10.S66` - Keep one profile signed in at a time: a human sign-in to a profile ends every other profile's stored sign-in and the human sessions resumed from it on every frontend, and leaves key sessions that need no sign-in; `src/cadrumo/application/user_profile/login_session.py`.
- [x] `P10.S67` - Bind each MCP server to one profile for its life, the key's or the first resumed sign-in's, refuse every call when the signed-in profile later differs, and answer nothing but the handshake, the tool list and status without a live sign-in or a valid key, with one typed result that tells the person to sign in to Cadrumo; `src/cadrumo_harness/mcp/runtime_adapter.py`.
- [ ] `P10.S68` - Show the desktop sign-in view on a locked profile instead of handing it to the terminal interface, and on the pushed expiry and lock events as well as the status poll; `native/desktop/frontend/src/shell/signIn.ts`.
- [x] `P10.S69` - Regenerate what derives from the tool list and the surfaces, the surface pins, the shipped contract document and the agent command reference, and rewrite the packaged agent text and user documentation so the agent asks the person to sign in to Cadrumo when refused and never asks for a secret; `src/cadrumo_harness/_data/agent`.
- [x] `P10.S70` - Prove against a running runtime with a synthetic encrypted profile that MCP works inside the signed-in profile and through a configured key, is refused without either, after sign-out and after a sign-in to another profile, and cannot reach a credential act; `src/cadrumo_harness/mcp/tests`.

### Phase `P11` - carry disclosures and key release so an agent can read its results

Delivers the owner's ruling of 2026-10-12: replies summarise the session's disclosures with a paged full read on every frontend, and a key the person issues for an agent releases results to the MCP client that presents it, so an agent admitted by a key reads values back.

- [x] `P11.S71` - Carry in the status, session and similar replies the count and a per-category summary of the session effective_scope disclosures instead of the full list, add a paged read of the full list served alike on the command line, the terminal interface and MCP, and regenerate the contracts, surface pins and agent command reference that derive from them; `src/cadrumo/application/user_profile/access_contracts.py`.
- [x] `P11.S72` - Let the person issue a key for an agent (MCP) with its data categories from config automation create on the command line and the terminal interface, bind the release destination to the key in the runtime enrollment so results go to whichever local MCP client presents it, and prove against a running runtime with a synthetic encrypted profile that the MCP server of a key issued on the command line reads a profile value back; `src/cadrumo/application/user_profile/automation_administration_service.py`.
- [ ] `P11.S73` - Extend the live agent lane so the access-api-key phase checks that the agent reads profile values back through the issued key, not only that its submissions are accepted; `dev/agent_eval/live/access.py`.

## Parallelization

The phases that ordered work around an approval step, `P03` and `P07`, were removed on 2026-10-11 with the Steps that depended on them, and nothing waits on an approval, a file-exchange folder, a replay identity or a provenance mark. What follows describes how the remaining work was sequenced and what a later Step must respect.

Hard ordering:

- `P01` landed before `P02`, and `P08` reverses every refusal `P01` to `P06` built on the frontend. A Step that reopens code from those phases works to the criteria of `P08`, not to the text of the earlier Step.
- Within `P09`, the runtime door `S52` comes first, because the act families `S54`, `S55`, `S56` and `S58`, the harness tool `S59` and the terminal-interface destinations `S60` are written against it. The four act families share the door's models file and land in one commit. `S61` wires every family into the installed composition and regenerates the derived records, so it follows them; `S63` follows `S61`.
- A change to the act table, the operation registry or the command tree is followed in the same Step by the regeneration of what derives from it: the command table, the agent's command reference, the shipped contract document and the import inventories.

May run in parallel:

- `S53` and `S57` are independent of the door. `S54`, `S55`, `S56`, `S58` and `S59` have disjoint files apart from the door's models file, which each changes only for its own acts. The two halves of `S60` split the terminal interface between the operations destination, which solely edits the navigation files, and the installation and reference destinations.

Within `P10` the Steps run in order, because `S64`, `S67` and `S70` share the MCP adapter and `S69` regenerates what the earlier Steps change. `S68` edits the desktop tree, which another session holds with uncommitted work; it stays open until that tree is free and blocks nothing else.

`P02.S18` recorded the sealing-key decision in the application sign-in record on 2026-10-12 and blocks nothing; the extension it enables is built under `2026-10-04-application-sign-in-plan`. Within `P11`, `S71` and `S72` touch disjoint code and may run in parallel; `S73` follows `S72`, because the live lane reads values back only once a key carries its destination.

## Verification

The project forbids test doubles for the behaviour under test, so "proved" means a real runtime with a synthetic encrypted profile, and a refusal that is the same on every frontend is tested as well as a success.

- Every registered operation resolves alike on the command line, the terminal interface and MCP for the same request, and a scan fails on a comparison of a frontend inside an access path outside a short declared list: attribution, and the surface a person chose to narrow.
- Every executable command of the command line either submits a registered operation, sends a runtime request or an installation act, or does its work in process and is paired with the operation, act or authority query that does the same work for the other two frontends; the few with nothing to share are declared with a reason. No command is left without a counterpart, and the pairing is checked in both directions.
- For each paired command, the family's own test holds the command's printed result to its counterpart's reply or result, with identifiers revealed and with the command line's redaction applied.
- Nothing is taken from any frontend. The command line does what it did before this plan, with or without a session and with or without a running runtime; the tests of its commands that existed before the plan pass unchanged.
- No operation is refused, narrowed or answered with less because the caller is an agent, and no operation waits on a person's approval inside Cadrumo. An agent's conduct before a destructive act is guidance in the packaged agent text.
- No operation, tool, act or command declares or performs a submission to the tax agency. Export writes a local file and the filed marker writes a local record.
- A surface a person narrows when starting the MCP server refuses, at submission, every operation and act that changes records or reaches the network, shown over its whole list. The default surface is everything, and each surface name is pinned to its tool list.
- With nobody signed in and no runtime running, the MCP server answers its tool list, the reference reads and the discovery of operations, and refuses only what needs a session. After sign-out or the idle deadline it refuses those again.
- A secret reaches the runtime on the protected frame from every frontend and appears in no log, error or result. On MCP it can be named by reference so that it does not pass through the model.
- An outcome that is not known is reported as unknown on every frontend and is never resent. Two legitimate identical entries remain expressible, and a caller-supplied replay identity makes a repeat safe.
- One quarterly and one annual declaration are prepared through MCP alone and equal the command-line result for the same inputs, down to the exported bytes; the recorded actor and the recorded origin of a classification are the intended differences.
- `just check-code`, `just check-import-boundaries`, `just check-types` and the covering tests pass for the files each Step touches.

Input and choice interactions cannot be answered on any frontend: the application projects them as unsupported and the response request carries no value. `S50` and `S60` gave MCP and the terminal interface what the command line has, which is the answer to a review, and show the other two kinds as pending.

Review follows the system cadence: one integrated review at each Phase close and at plan close, against the full-parity record and the records it leaves accepted. A reviewer's observation that an agent has a second route to an act describes parity and is not a finding. The plan is complete when every Step is closed and the final review passes.

---
tags:
  - '#plan'
  - '#mcp-parity'
date: '2026-10-10'
tier: L2
related:
  - '[[2026-10-10-mcp-parity-parity-mechanism-adr]]'
  - '[[2026-10-10-mcp-parity-shared-sign-in-door-adr]]'
  - '[[2026-10-10-mcp-parity-admission-rulings-adr]]'
  - '[[2026-10-04-application-sign-in-adr]]'
  - '[[2026-09-26-mcp-purpose-authentication-adr]]'
  - '[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]'
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
  - '[[2026-06-30-ledger-add-idempotency-adr]]'
modified: '2026-10-10'
body_schema: body-v2
body_hash: 'sha256:0fc266ce15ed7bb416168ad3bb69129fc7b608448ffa3b59f48fb339181ecd39'
---

# `mcp-parity` plan

Make the MCP server a full interface for the tax work the command line and terminal interface already implement, ending at a filing calculation and a local export, by deciding MCP admission per registered operation.

## Description

Approved 2026-10-10

The owner approved this plan first-hand on 2026-10-10, after reading its summary and the open decisions ("1 approved"), and set the execution pipeline: sonnet at high effort for well-defined, unambiguous tasks, opus for problem solving, and haiku for tool calls, testing and summarising code and context.

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
- Where the receipt-sealing key lives while the sign-in is extended, a security choice the sign-in record names as a follow-on (`P02.S18`).
- Which acts count as sensitive is the rulings record's own classification, for example the three prorrata elections; the owner corrects it by naming an operation.

Evidence is in the six reference and research records of this feature. All of it is static reading at commit `85f84a2680`; nothing was run. Each record's "Not verified" list names what a Step must establish before it relies on it, in particular whether operations repeat the validations the command line performs, and what the verify executor exchanges while checking provider readiness (`P06.S38`).

Overlap with plans in flight, to coordinate and not to duplicate: `2026-10-04-application-sign-in-plan` owns the sign-in generation, global sign-out, session events and the interactive-terminal gate, and implements no receipt extension; `P02` builds on that work and `P02.S16` and `P02.S18` change behaviour it owns. `2026-09-26-mcp-purpose-authentication-plan` still lists the MCP adapter and its cross-interface proof as open Steps, and its proof of an MCP reconnect after a human time-out now holds for the key route only. The worktree is shared with other sessions; each Step stages only its own files.

## Steps

### Phase `P01` - make the already-open MCP surface safe

Delivers the recorded MCP decision for every operation, the refusal of the sensitive operations that are open today with no approval, refusal at submission, and confined host paths, so that opening the shared sign-in exposes nothing unguarded.

- [x] `P01.S01` - Add the recorded MCP decision table, one row per registered operation with its ruling, reason and whether it changes records or reaches the network, seeded from the admission rulings, and extend the catalogue test to fail on an operation with no row, an admitted row the real access resolver refuses to the MCP frontend, an excluded row that still lists MCP, a human-only policy that admits MCP, and any operation or tool that declares a submission to the tax agency; creates src/cadrumo/application/operations/mcp_admission.py; `src/cadrumo/entrypoints/tests/test_operation_catalogue.py`.
- [ ] `P01.S02` - Refuse on the MCP frontend, until the approval step exists, the sensitive operations that are open today with no approval: ledger.invoice.remove, auth.session.reset, the writes of ledger.own_account, the declare and remove actions of modelo.m360_solicitud and the three prorrata elections, with a refusal test for each and one contract cutover; also auth/operation_definitions.py, ledger/own_account_operation.py, modelo/m360_solicitud_operation.py and prorrata_register/registered_operations.py; `src/cadrumo/application/invoices/catalogue_remove_operation.py`.
- [ ] `P01.S03` - Establish which paths user-profile.field-mutation accepts, refuse the capability opt-ins on the MCP frontend until the approval step exists, and move the per-field confirmation of the census review into user-profile.censo-review; also user_profile/censal_operation.py; `src/cadrumo/application/user_profile/operations.py`.
- [x] `P01.S04` - Remove the MCP claim from the seven definitions that cannot run: the four automation proposals, export.google-sheets, local-reader.provision and user-profile.bundle-export; also export/google_operation.py, local_reader_operation.py and user_profile/operations.py; `src/cadrumo/application/user_profile/automation_operations.py`.
- [ ] `P01.S05` - Refuse at submission, where the frontend list is refused today, a mutating operation to a session whose scope lacks the commit action, so that no browser, classifier or subject lease is taken first; `src/cadrumo/application/user_profile/operation_access_policy.py`.
- [ ] `P01.S06` - Define the named served surface as tool names, declared properties and an operation list held by Cadrumo, carry its name from the server launch to the runtime, and refuse at submission an operation outside it or one that changes records or reaches the network on a read-only or local surface, with a test over the whole operation list; also src/cadrumo_harness/mcp/main.py and protocol_contract.py; `src/cadrumo/application/user_profile/operation_access_policy.py`.
- [ ] `P01.S07` - Create a shared host-path confinement guard that verifies the opened handle against roots taken from existing settings, and apply it to modelo.reconcile.import and the six live capture operations that take an output root; applies under src/cadrumo/application/live and modelo/reconciliation_import_operation.py; `src/cadrumo/core/path_confinement.py`.
- [x] `P01.S08` - Repair discovery in the generic tools: bound and page search, filter it by family, cache contracts within a session, report a refused operation without failing the search, and read a result by operation identifier alone; also operation_search.py and protocol_contract.py; `src/cadrumo_harness/mcp/admitted_operations.py`.
- [ ] `P01.S09` - Generate the join from command-line commands to the operations they submit, from the command graph and the registry, and check it in the catalogue test; `src/cadrumo/entrypoints/cli/operator_surface_reconciliation.py`.
- [x] `P01.S10` - Bring the packaged personas and skills into line with the amended hand-off rule: no persona or skill tells an agent to export or record the filed marker without the person approving, and the stale provider-configuration instruction and capability-manifest inputs are removed; also skills/cadrumo-exportar-declaracion/SKILL.md and skills/cadrumo-alta-contribuyente/SKILL.md; `src/cadrumo_harness/_data/agent/personas/cadrumo-verifier.md`.
- [ ] `P01.S11` - Record in the decision table the owner ruling that an agent may originate modelo.reconcile.import, and keep it admitted with its findings presented for the person to review or approve; `src/cadrumo/application/modelo/reconciliation_import_operation.py`.
- [ ] `P01.S45` - Declare a typed subject-reference form on the operation definition and its public contract, filled from the validator of each family, and state it in describe, with one contract cutover for every definition; `src/cadrumo/application/operations/operation_definition.py`.

### Phase `P03` - decide and build the approval step and the other first-release prerequisites

Delivers accepted decision records for the approval step taken in Cadrumo, file exchange and the replay identity, and builds the approval step, the hosted assistant's process identity, the runtime refusal of reserved operations from it, and the stored sign-in for a command run without a console.

- [ ] `P03.S20` - Record and have accepted the decision on the approval step taken in Cadrumo: where it is shown, how it binds the exact act, how it attaches to an operation submitted through MCP and to a command run in the assistant terminal, and the reserved set Cadrumo publishes for the command line; `.vault/adr`.
- [ ] `P03.S21` - Record and have accepted the file-exchange decision: the per-profile folder, the standing consent, the lifetime of plaintext, and which documents an agent may originate; `.vault/adr`.
- [ ] `P03.S22` - Record and have accepted the decision on the caller-supplied replay identity for effectful submissions on the MCP frontend, extending the accepted ledger-add idempotency ruling without a content-derived key; `.vault/adr`.
- [ ] `P03.S23` - Record and have accepted, for both doors, the provenance rule for amounts an agent states: marked from the session as entered by an agent, with the registry still deriving the regulated figure wherever it can; `.vault/adr`.
- [ ] `P03.S24` - Build the hosted assistant process identity and the runtime refusal of reserved operations from it unless the person approved, including the fact carried forward by the Cadrumo process that serves a relayed surface; `src/cadrumo/entrypoints/runtime`.
- [ ] `P03.S25` - Build the approval step in Cadrumo as the accepted decision defines it, shown with the exact act and enforced by the runtime; `src/cadrumo/entrypoints/runtime`.
- [ ] `P03.S26` - Admit the stored sign-in for a command the hosted assistant runs without a console, and amend the automatic-reuse rule of the sign-in record to match; `src/cadrumo/entrypoints/cli/runtime_profile_admission.py`.

### Phase `P07` - admit the sensitive acts behind the approval of the person

Delivers local export, the local filed record and every destructive, election, attestation, consent and publication operation on the MCP frontend, each runnable only after the person approves that exact act in Cadrumo.

- [ ] `P07.S40` - Attach the approval step to operations submitted through MCP and admit modelo.export, modelo.work.file and modelo.quickfile behind it, with the elections and the bank account as inputs only the person supplies; all three end at local artefacts and submit nothing; also quickfile_operation.py; `src/cadrumo/application/modelo/operation_definitions.py`.
- [ ] `P07.S41` - Admit behind the approval step the other sensitive operations of the rulings: the four destructive ledger operations, ledger.invoice.remove, ledger.evidence.confirm, the off-machine read of ledger.evidence.extract, the writes of ledger.own_account and modelo.m360_solicitud, the three prorrata elections, modelo.work.discard, the three IVA wallet writes, the attestation and marker operations, review-package signing and sharing with the recipient add and remove, Google publication, the profile archive operations, auth.session.reset and the capability opt-ins; `src/cadrumo/application`.

### Phase `P02` - open the shared sign-in door to the MCP server

Delivers an MCP server that resumes the person's sign-in for the exact profile, answers its tool list with no session, and stops when the sign-in ends.

- [ ] `P02.S12` - Admit the receipt login method from the MCP frontend in the runtime login validation, keeping the password method and receipt persistence refused there; `src/cadrumo/entrypoints/runtime/profile_connection_admission.py`.
- [ ] `P02.S13` - Give the MCP adapter a resume path used when it holds no credential reference, require the profile launch argument only with a credential reference, and answer initialization, the tool list and public queries with no session and no profile; also runtime_admission.py, main.py and server.py; `src/cadrumo_harness/mcp/runtime_adapter.py`.
- [ ] `P02.S14` - Handle session retirement in the MCP adapter from the pushed session events: refuse with the existing refusal shape, drop the session, and resume only when a later call finds a live sign-in; `src/cadrumo_harness/mcp/runtime_adapter.py`.
- [ ] `P02.S15` - Trace whether a sign-in lease is bound through the worker five-minute in-process idle window, record the finding in the sign-in doors reference, and correct the window if a long-lived session would be refused before its lease ends; `src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py`.
- [ ] `P02.S16` - Settle with the owner of the sign-in work whether a login or generation mismatch may delete the stored sign-in before the presented proof is verified, and verify the proof first if not; `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py`.
- [ ] `P02.S17` - Refuse the global sign-out and the lock of a session other than its own to a session on the MCP frontend, which may end only itself, as the owner ruled, with a refusal test for each; `src/cadrumo/entrypoints/runtime/profile_connection_sessions.py`.
- [ ] `P02.S18` - Record as an amendment to the application sign-in record the owner ruling that a message the person sends to the assistant counts as their activity and the assistant own calls, commands and scripts do not, together with the decision on where the receipt-sealing key lives during extension, so the idle extension can be built; the key decision is still open; `.vault/adr/2026-10-04-application-sign-in-adr.md`.
- [ ] `P02.S19` - Prove the door against a running runtime with a synthetic encrypted profile: resume, refusal with nobody signed in, the tool list with no session, sign-out and idle expiry ending the MCP session, no MCP submission advancing the deadline, the password refused, and the key route unchanged; `src/cadrumo_harness/mcp/tests`.

### Phase `P04` - admit the reads

Delivers the ratio, work, workflow and evidence reads on the MCP frontend, each through the admission checklist, with one contract cutover per family.

- [ ] `P04.S27` - Admit ledger.ratios.list, ledger.ratios.eligible, ledger.ratios.validate and ledger.rule.list to the MCP frontend through the admission checklist, with one contract cutover for the family; `src/cadrumo/application/ledger/ratios_operation.py`.
- [ ] `P04.S28` - Admit the work reads ruled admitted, from modelo.work.list to modelo.work.filing_record and profile.history, with the three workflow reads, config.collab.recipient.list and the three Google configuration reads, each after its result is checked fit for an agent host and with an agent-facing sibling where it is not, with one contract cutover per family; starts at work_inventory_operation.py and revision_selection_operation.py; `src/cadrumo/application/modelo`.
- [ ] `P04.S29` - Admit the eight evidence reads ruled omissions once each result is shown, inside the operation, to carry no evidence bytes, with one contract cutover for the family; `src/cadrumo/application/ledger/evidence_read_operation.py`.

### Phase `P05` - admit every ledger write that is not sensitive

Delivers the ledger entry, ratio, rule, attachment, evidence and reversible lifecycle writes on the MCP frontend with their command-line safeguards moved into the operations, so that an agent can operate the whole ledger.

- [ ] `P05.S30` - Move the validations the command line performs before submitting ledger add, update and single classification into those operations, with the same refusals; `src/cadrumo/entrypoints/cli/_ledger.py`.
- [ ] `P05.S31` - Admit ledger.add, ledger.update, ledger.classify.single and ledger.allocate with attribution and provenance taken from the session and the replay identity required; also update_operation.py, classify_operation.py and allocate_operation.py; `src/cadrumo/application/ledger/add_operation.py`.
- [ ] `P05.S32` - Admit ledger.classify.bulk by changing its access resolver, which refuses every frontend but the command line, together with its frontend list; `src/cadrumo/application/ledger/bulk_classify_operation.py`.
- [ ] `P05.S33` - Admit ledger.ratios.set, its inverse ledger.ratios.unset, ledger.rule.add and ledger.rule.apply; also rule_operation.py; `src/cadrumo/application/ledger/ratios_operation.py`.
- [ ] `P05.S34` - Admit ledger.attach and ledger.detach, which act on stored evidence by identifier, after the evidence reads; `src/cadrumo/application/ledger/attachment_mutation_operation.py`.
- [ ] `P05.S35` - Move the confirmations of the manual split and of archive, stash, restore and exclude into their operations and admit all five; also lifecycle_mutation_operation.py; `src/cadrumo/application/ledger/split_operation.py`.
- [ ] `P05.S42` - Admit ledger.evidence.update, ledger.invoice.wizard and ledger.participation.rebuild, and ledger.evidence.extract for the reader on the machine with the off-machine read refused until the approval step carries that consent; also invoices/catalogue_intake_operation.py, participation_rebuild_operation.py and invoice_evidence_extract_operation.py; `src/cadrumo/application/ledger/evidence_mutation_operation.py`.

### Phase `P06` - admit document intake and declaration preparation

Delivers statement, invoice-book and evidence intake and the file exports under the file-exchange decision, and declaration create, calculate, amend, rename and verify, ending at a calculated and verified revision.

- [ ] `P06.S36` - Build file exchange as the accepted decision defines it and admit ledger.import, ledger.invoice.import, ledger.evidence.add and ledger.evidence.batch over it, with the digest hand-off enforced in the operation; also invoices/catalogue_intake_operation.py, ledger/evidence_add_operation.py and ledger/evidence_ingestion_operation.py; `src/cadrumo/application/ledger/import_operation.py`.
- [ ] `P06.S37` - Move the applicability bypass and the confirmation before an at-risk recalculation into modelo.work.create and modelo.work.calculate, derive the actor from the session, and admit them with modelo.work.amend and modelo.work.rename; also work_create_operation.py; `src/cadrumo/application/modelo/operation_definitions.py`.
- [ ] `P06.S38` - Read the modelo.work.verify executor end to end, record what it reads and what it exchanges while checking provider readiness, and admit it only if it changes nothing and sends nothing that alters remote state; `src/cadrumo/application/modelo/operation_definitions.py`.
- [ ] `P06.S39` - Remap the packaged skills from command-line verbs to operations through the generated join, and prove one quarterly and one annual declaration prepared through MCP alone equal to the command-line result for the same inputs; `src/cadrumo_harness/_data/agent/skills`.
- [ ] `P06.S43` - Admit over file exchange the operations that read or write a file: ledger.export, modelo.spreadsheet.export, modelo.reconcile.export-xlsx, export.calculation-review-xlsx, modelo.m145.export, modelo.audit.export, modelo.review_package.build, modelo.work.report_verify, live.borrador.100.import and user-profile.censo-file-import; `src/cadrumo/application/ledger/export_operation.py`.
- [ ] `P06.S44` - Admit modelo.filing_record.import for values the caller states, with its findings presented for the person to review, and modelo.observation.local, modelo.m145.create and modelo.m145.validate; also local_observation_operation.py and m145_communication_operation.py; `src/cadrumo/application/modelo/filing_record_import_operation.py`.

## Parallelization

Hard ordering:

- `P01` lands before `P02`. The moment the shared sign-in opens, every operation that lists MCP runs with the person's full scope, so the refusal of unapproved sensitive operations, the refusal at submission and the decision check come first.
- Within `P01`, `S01` comes first because every later Step updates the table it creates. `S02`, `S03` and `S04` each change frontend sets and share one contract cutover, so they land together or in sequence, never interleaved with a stored invocation of those definitions. `S06` follows `S05`.
- `P03` follows `P01` and `P07` follows `P03`, because every sensitive operation waits on the approval step. `P07` needs `P03.S24` and `P03.S25`. Whether an approval can be given for a key session with nobody signed in is settled in `P03.S20`; if it cannot, `P07` also needs `P02`.
- `P04` needs `P01.S01` and `P01.S06`. `P05.S34` needs the evidence reads of `P04.S29`. `P05.S31` needs `P03.S22` and `P03.S23`. `P06.S36` and `P06.S43` need `P03.S21`. `P06.S39` needs `P01.S09`.

May run in parallel:

- `P03.S20` to `P03.S23` are decision records and can start at once, beside `P01`.
- `P01.S07`, `P01.S08`, `P01.S09` and `P01.S10` touch disjoint files and can run beside one another after `P01.S01`.
- `P02` can run beside `P03` and `P07`. Within it, `P02.S15` and `P02.S16` are independent of the adapter Steps `P02.S13` and `P02.S14`.
- `P04.S27`, `P04.S28` and `P04.S29` are separate families with separate cutovers, and `P04` can run beside `P03`.

`P02.S17` waits on an owner ruling and `P02.S18` on the sealing-key decision; neither blocks the Steps around it.

## Verification

The project forbids test doubles for the behaviour under test, so "proved" means a real runtime with a synthetic encrypted profile, and refusals are tested as well as successes.

- The catalogue test fails for an operation with no recorded MCP decision, for an admitted operation the real access resolver refuses, for an excluded operation that lists MCP, and for any operation or tool that declares a submission to the tax agency. It passes on the tree at each Step close.
- Every sensitive operation refused in `P01` is refused on the MCP frontend, still works for a person on the command line and terminal interface, and runs on MCP after `P07` once the person approves it.
- Every ledger operation is operable on the MCP frontend at plan close: admitted outright, or admitted behind the person's approval.
- A read-only or local surface refuses, at submission, every operation in the registry that changes records or reaches the network, shown over its whole operation list.
- With nobody signed in the MCP server answers its tool list and refuses every call that needs the profile. After sign-out or the idle deadline it refuses again. No submission on the MCP frontend advances the deadline. The key route behaves as before.
- Each admitted operation completes a round trip on the MCP frontend and enforces inside the operation every safeguard the command line applied for it.
- No result of an admitted operation carries evidence bytes.
- An effectful submission replays exactly once under its caller-supplied identity, and two legitimate identical entries remain expressible.
- One quarterly and one annual declaration are prepared through MCP alone and equal the command-line result for the same inputs.
- No sensitive operation runs on the MCP frontend without the person's approval of that exact act, and an approval given for one act does not carry to another.
- `just check-code`, `just check-import-boundaries`, `just check-types` and the covering tests pass for the files each Step touches.

Review follows the system cadence: one integrated review at each Phase close and at plan close, against the three decision records. The plan is complete when every Step is closed and the final review passes.

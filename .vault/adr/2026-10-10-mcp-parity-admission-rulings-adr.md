---
tags:
  - '#adr'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-10'
body_schema: 'body-v2'
body_hash: 'sha256:7fceed684cebbca7c33902c81321b5aaeb7b6f24c2db5a1168da4b5b18e23558'
related:
  - "[[2026-10-10-mcp-parity-exclusion-intent-evidence-research]]"
  - "[[2026-10-10-mcp-parity-closed-operations-reference]]"
  - "[[2026-10-10-mcp-parity-admitted-surface-defects-reference]]"
  - "[[2026-10-10-mcp-parity-sign-in-doors-reference]]"
  - "[[2026-10-10-mcp-parity-parity-mechanism-adr]]"
  - "[[2026-10-10-mcp-parity-shared-sign-in-door-adr]]"
  - "[[2026-07-02-agent-harness-refoundation-adr]]"
  - "[[2026-06-30-ledger-add-idempotency-adr]]"
  - "[[2026-06-10-llm-evidence-classification-adr]]"
---
# `mcp-parity` adr: `Which MCP exclusions are omissions to correct and which are deliberate, family by family` | (**status:** `accepted`)

## Problem Statement

143 of Cadrumo's 266 registered operations do not admit the MCP frontend, and for 65 of
them the code states no reason. The owner could not say from memory which exclusions were
intended, and asked that the judgement be made from the rules that drive the app and from
the sessions that have read it: "get a proper ruling on what is a mistake and what
isn't" (2026-10-10). Without that ruling no operation can be opened or left closed for a
stated reason, and the recorded decision that
`2026-10-10-mcp-parity-parity-mechanism-adr` requires for every operation has
nothing to start from.

Records named `2026-10-10-cadrumo-integration-...` belong to the vault of the cadrumo-agent repository, a separate project that drives this application through its MCP server; they are cited by name and are not in this vault.

## Considerations

Evidence is in `2026-10-10-mcp-parity-exclusion-intent-evidence-research`; the
operations are listed in `2026-10-10-mcp-parity-closed-operations-reference`.

- History does not show intent for the ledger and declaration families. Seven lifecycle
  definitions predate the MCP frontend. About sixty closed definitions were created
  inside the MCP feature series, in the same commits as open siblings, with no reason in
  any commit message. MCP was withdrawn after being granted only for authentication and
  grant administration.
- Cadrumo's rule files reserve review, confirmation and filing to a person. One sentence
  reserves a class of operation: workbench reads are human-only. Nothing reserves entering
  ledger data or preparing a declaration.
- The product ships agent material that tells an agent to add, update and classify ledger
  entries, set ratios, and create, calculate, verify and amend a declaration. An accepted
  Cadrumo record on ledger-add idempotency names an autonomous agent as the command
  line's operator.
- The same material and an accepted Cadrumo record keep a hand-off: export and the local
  filed record are irreversible steps that the preparer may not self-certify, and
  destructive actions need explicit human confirmation.
- The runtime gives no reason of its own to keep ledger writes or declaration preparation
  off MCP; the structural limits are secrets, interactions other than a review, workbench
  generation and access administration
  (`2026-10-10-mcp-parity-sign-in-doors-reference`).
- An MCP session will be the person's own sign-in with no grant to narrow it
  (`2026-10-10-mcp-parity-shared-sign-in-door-adr`), so this list is the only
  limit on what an MCP client may call.
- The consuming agent is a single agent; a second run cannot stand in for an independent
  verifier. Only the person can hold the hand-off.
- The owner, on destructive or irreversible commands, first-hand in another session:
  "Assistant, after asking each time". The owner also ruled that the approval is taken in
  Cadrumo and shown with the exact command, and that before a first release Cadrumo's
  runtime refuses reserved operations to anything inside the assistant's process tree
  unless the person approved (`2026-10-10-cadrumo-integration-owner-rulings-research`).
- The owner, on what the product delivers: "the end results for us is a filing
  calculation, an exported BOE artefact or a google sheet but not an actual AEAT write.
  We pull and sync information (one directional, never bi-directional)" (same record,
  typing lightly corrected).
- Some operations that already admit MCP are open in the other direction by mistake: they
  are destructive, or carry an account number or a consent as a plain argument
  (`2026-10-10-mcp-parity-admitted-surface-defects-reference`).
- The owner, first-hand on 2026-10-10 after reading the rulings as first accepted
  (typing lightly corrected): "all ledger ops must be possible to be operated by the
  agents - I disagree that these are to be dropped. Agent generally speaking should have
  full control over the user data and ops. User will be required to approve sensitive
  ops."

## Considered options

- **Treat every unexplained exclusion as deliberate.** Safe and static. Rejected: it
  contradicts the product's own shipped agent material and an accepted record, and leaves
  the MCP server unable to do the work the owner asked for.
- **Treat every unexplained exclusion as an omission.** Rejected: it would open
  destructive and hand-off operations that the product's rules reserve, with no grant in
  front of them.
- **Rule per family on three tests: is the act reserved by a rule, an accepted record or
  a human-only policy in code; is it structurally unable to run from MCP; does the
  product itself expect an agent to do it.** Chosen at first acceptance, with a class of
  operations left closed for lack of a stated need. The owner overruled that class.
- **Admit every operation over the person's data, and put the sensitive ones behind the
  person's approval.** The owner's rule of 2026-10-10, and the rule of this record now.

## Constraints

The rule of judgement, binding for these rulings and for any later one. It is the
owner's rule quoted above, and it replaces the earlier default under which an operation
nobody had asked for stayed closed:

- **Admit** every operation over the person's data. No operation stays closed for lack
  of a stated need, and every ledger operation is operable by an agent.
- **Admit behind the person's approval** where the act is sensitive: destructive,
  irreversible, a hand-off, a taxpayer's election or attestation, a consent, a transfer
  of data outside the machine, or a change to who is paid or who can read. The agent may
  perform it only after the person approves that exact act, each time, in a step taken
  in Cadrumo and shown with the exact act. Until Cadrumo has that step for MCP the
  operation is refused on the MCP frontend, so building the step comes before
  everything that depends on it.
- **Excluded** only on one of four grounds: the act cannot run from MCP by construction
  (a secret the person types, an interaction other than a review, a terminal-only
  flow); it administers access itself (authentication, certificates, keys and grants,
  locking and resuming); it administers the machine or its storage, which the owner
  ruled is not an MCP responsibility; or it is a projection written for a person whose
  content an agent-facing sibling already serves.
- The mechanism is unchanged. Admission is still explicit per definition, recorded, and
  passes the checklist of the mechanism record. What changed is the default of
  judgement, not the registry's rule that a frontend is never granted silently.
- Which acts count as sensitive is this record's classification under the owner's rule,
  and the owner corrects it by naming an operation.
- The operations this record reserves to the person's approval are a subset of the
  reserved set that the accepted `2026-10-10-cadrumo-integration-terminal-access-adr` has
  Cadrumo define and publish for the command line. That set is wider: it also holds
  commands exempt from the sign-in gate, ones that start other programs or install
  components, and the operations Cadrumo reserves to a person that need no secret, which
  this record rules deliberate and which the person's own session no longer holds back on
  the command line. An act reserved here and free on the command line is a defect in the
  command line's set.
- The owner's rule settles two points this record had left to them. The approval of a
  sensitive act applies to operations submitted through MCP as it does to commands run
  in the assistant's terminal. An admitted write that is not sensitive lands with nobody
  confirming each one.
- The writes that accept amounts from their caller (`ledger.add`, `ledger.update`,
  `ledger.classify.single`, `ledger.classify.bulk`) are admitted under the owner's rule.
  What is still to be recorded is their provenance: a taxable base, a rate or a tax
  amount an agent states is marked, from the session, as entered by an agent, and the
  registry still derives the regulated figure wherever it can, as the accepted record
  requires. The same rule holds on both doors, because the hosted assistant can run the
  same writes through Cadrumo's command line.
- The MCP frontend is declared by the client, and the runtime cannot verify the
  declaration (`.vault/adr/2026-10-04-application-sign-in-adr.md:93`). These rulings state
  what Cadrumo offers on the typed path to a client that says it is an MCP client. They
  are not a barrier against a same-account process that declares another frontend; the
  owner has ruled that such reach is not a security concern, and the refusal of reserved
  operations to the hosted assistant is keyed on its process tree, not on the frontend.
- Whether the reversible lifecycle operations, which hide a record without removing it,
  belong in the command line's reserved set is decided where that set is defined.
- A ruling to admit is a ruling that the operation may be admitted. Admission itself
  still passes the checklist of the mechanism record, including moving any safeguard that
  lives in a command handler or a screen into the operation.
- The operations that edit a declaration's values belong to the person's workbench and
  need an interaction the MCP frontend cannot perform. Whether another path lets an
  agent change those values was not established. Under the owner's rule a missing path
  is a capability to add as an agent-facing operation, not an admission of the workbench
  operations.
- An operation that takes or writes a host path is admitted only once file exchange is
  decided, which this record does not do.
- A verification the assistant ran does not stand in for the hand-off. The hand-off is
  the person's approval of the export or of the local filed record.
- A condition on a read, such as "no result carries evidence bytes", has to hold inside
  the operation. Scope gives no help: a sign-in session's disclosure ceiling is every
  schema in every category.
- Admitting `ledger.classify.bulk` changes its access resolver as well as its frontend
  list, because the resolver refuses any frontend but the command line itself.
- No operation admitted to MCP returns evidence bytes that are in Cadrumo's custody, on
  any surface, as the accepted MCP record requires
  (`.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:161`). The surface for the
  hosted assistant therefore offers no operation that returns them.
- The two model-backed review operations, `ledger.classify.review` and
  `ledger.split.review`, stay admitted in the registry. Whether a
  surface served to a particular client offers them is decided by that surface's
  operation list; the surface for the hosted assistant leaves them off.

Rulings for operations closed today:

| family | operations | ruling |
|---|---|---|
| Ledger entries | `ledger.add`, `ledger.update`, `ledger.classify.single`, `ledger.classify.bulk`, `ledger.allocate` | Admit |
| | `ledger.attach`, `ledger.detach` | Admit with the evidence reads; they tie stored evidence to a transaction by identifier only |
| Ratios and rules | `ledger.ratios.set`, `.unset`, `.list`, `.eligible`, `.validate`, `ledger.rule.list`, `ledger.rule.add`, `ledger.rule.apply` | Admit |
| Reversible ledger lifecycle | `ledger.split.manual`, `ledger.archive`, `.stash`, `.restore`, `.exclude` | Admit, with the confirmation moved into the operation |
| Destructive ledger lifecycle | `ledger.merge`, `ledger.remove`, `ledger.reset`, `ledger.evidence.remove` | Admit behind the person's approval |
| Statement and invoice-book import | `ledger.import`, `ledger.invoice.import` | Admit, pending file exchange |
| Evidence | `ledger.evidence.add`, `ledger.evidence.batch` | Admit, pending file exchange |
| | `ledger.evidence.list`, `.view`, `.attachment_queue`, `.attachment_view`, `.reader-readiness`, `.consent.list`, `.review.list`, `.review.view` | Admit as reads, on the condition that no result carries evidence bytes |
| | `ledger.evidence.update`, `ledger.invoice.wizard`, `ledger.participation.rebuild` | Admit |
| | `ledger.evidence.confirm` | Admit behind the person's approval. The agent prepares one resolution per blocking finding and the person approves each document's confirmation, which keeps the per-finding human review before an invoice is created |
| | `ledger.evidence.extract` | Admit for the reader on the machine. A read off the machine is a consent: behind the person's approval each time, never a field the caller sets |
| | `ledger.export` | Admit, pending file exchange, which decides where the file may be written |
| Declaration preparation | `modelo.work.create`, `.calculate`, `.amend`, `.rename` | Admit, with the applicability check and the recalculation confirmation moved into the operations |
| Verification | `modelo.work.verify` | Admit only after its executor is read and shown to read and nothing more |
| Work reads | `modelo.work.list`, `.metadata`, `.review`, `.dependencies`, `.revisions`, `.revision`, `.revision_snapshot`, `modelo.work.filing_record`, `modelo.filing_record.list`, `.view`, `modelo.verification_report.list`, `.view`, `modelo.iva-wallet.balance`, `modelo.work.compare_taxation`, `.preview_maritime_exemption`, `profile.history`, `workflow.run.read`, `.list`, `workflow.resume.context`, `config.collab.recipient.list` | Admit as reads, each after a check that its result is fit for an agent host |
| Hand-off | `modelo.export`, `modelo.work.file`, `modelo.quickfile` | Admit behind the person's approval. The elections and the bank account in an export are the person's inputs. Quickfile ends at the same local export |
| | `modelo.work.discard` | Admit behind the person's approval |
| | `modelo.audit.read`, `modelo.036.read`, `live.borrador.100.read`, `modelo.history`, `modelo.work.history`, `modelo.bindings.resolve`, `modelo.readiness` | Excluded: projections written for a person, served to an agent by their agent-facing siblings |
| IVA wallet | `modelo.iva-wallet.override`, `.seed`, `.correct` | Admit behind the person's approval; an accepted record requires the taxpayer's explicit override |
| Workbench | `workbench.generation`, `modelo.work.form`, `.casilla_help`, `modelo.edit.renew`, `.preflight`, `.apply_prerequisite`, `.apply` | Excluded: the person's projection, and an interaction the MCP frontend cannot perform |
| Wizards | `modelo.work.wizard_context`, `.wizard_attempt`, `.amendment_context` | Excluded: terminal-only |
| Files | `modelo.review_package.build`, `modelo.work.report_verify`, `modelo.spreadsheet.export`, `modelo.reconcile.export-xlsx`, `export.calculation-review-xlsx`, `modelo.m145.export`, `modelo.audit.export`, `live.borrador.100.import`, `user-profile.censo-file-import` | Admit, pending file exchange |
| Signing and sharing | `modelo.review_package.sign`, `.counter_sign`, `.encrypt_for_recipient`, `.decrypt`, `.encrypt_feedback`, `.import_feedback`, `config.collab.recipient.add`, `.remove` | Admit behind the person's approval, pending file exchange where a file is read or written: they sign in the person's name or decide who can read an exported package |
| Evidence-grade records | `modelo.filing_record.import` | Admit, as the owner ruled for the reconciliation import: the agent originates the record and the person reviews its findings. Its file source waits on file exchange |
| Local records | `modelo.observation.local`, `modelo.m145.create`, `.validate` | Admit |
| Attestations and markers | `modelo.work.m303_attestation`, `modelo.036.record`, `modelo.m145.mark_delivered_to_payer`, `.mark_locally_completed` | Admit behind the person's approval: each records the person's statement that something is true or happened outside Cadrumo |
| Publication and archive | `export.google-review`, `profile.archive.export`, `.push`, `.reconcile`, `config.google.folder.organize`, `config.google.logout` | Admit behind the person's approval: each sends or moves the person's data outside the machine, or ends access to it |
| | `config.google.status`, `.probe`, `.folder.view` | Admit |
| | `config.google.login` | Excluded: a consent the person gives in a browser |
| Authentication, certificates, grants, workstation | all operations of those families | Excluded: access administration, typed secrets and machine administration |

Rulings for operations that admit MCP today with no approval in front of a sensitive act:

| operations | ruling |
|---|---|
| `ledger.invoice.remove`, `auth.session.reset` | Destructive. Behind the person's approval; refused on MCP until that step exists |
| `ledger.own_account` writes, the declare and remove actions of `modelo.m360_solicitud` | They change who is paid and carry account numbers. Behind the person's approval |
| `ledger.prorrata.elect_especial`, `.elect_general`, `.revoke_especial` | The taxpayer's elections. Behind the person's approval. The four other prorrata operations stay admitted |
| the capability toggle within `user-profile.field-mutation` | A consent. Behind the person's approval |
| `user-profile.censo-review` apply | The per-field confirmation the command line shows moves into the operation |
| `user-profile.bundle-export` and the six definitions without an access resolver | Not runnable. Their MCP claim is removed until they are made runnable |

Ruled by the owner on 2026-10-10 (typing lightly corrected): "agent can and should be
able to call reconciliation records yes. It is important automation and user will always
need to approve findings or review findings." `modelo.reconcile.import` therefore stays
admitted to MCP, and an agent may originate it although it creates evidence-grade
records. What the import produces are findings the person reviews or approves; the
agent's import does not stand in for that review. Its host path is confined like the
other open path operations.

Fixed boundary, not open to any decision: nothing here opens, designs or supports any act
that sends data to the tax authority and changes its state. `modelo.work.file` writes a
local record and submits nothing; `modelo.export` writes a local file that the person
uploads themselves.

Affected prior rulings. The accepted agent-harness record's hand-off rule is kept in
intent and applied to a single agent, with the person as the holder of the hand-off. Two
passages of `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md` need an amendment
the owner approves:

- D3 (line 96), "the verifier owns export and the record marker so the preparer cannot
  self-certify the irreversible handoff", becomes "export and the record marker belong
  to the person. An agent performs either only after the person approves that exact act
  in Cadrumo. A verifier's clean result informs that approval and does not stand in for
  it; the same agent run a second time is not an independent verifier."
- R6(i) (line 172), which enforces the confirmation tier through MCP elicitation and
  falls back to a client's confirmation hint, becomes "the approval of a reserved act is
  taken in Cadrumo and enforced by Cadrumo's runtime. An elicitation answer or a
  client's confirmation hint is not that approval. Until the step exists for an
  operation submitted through MCP, reserved operations do not admit the MCP frontend."
  R6(iii)'s per-verb deny rules for the hand-off are met by that exclusion. R6(iv) and
  the invariant of zero submission attempts are unchanged.

The packaged agent personas that tell an agent to export and to record the filed marker
are brought into line with the amended D3. The packaged skill that tells an agent to configure the AEAT
provider is stale; the exclusion stands.

## Implementation

We will record, for each of Cadrumo's operations, the ruling above as its MCP decision,
admit the operations family by family through the admission checklist, and put the
person's approval in front of every sensitive one.

- The rulings seed the recorded-decision table that the mechanism record requires.
- The sensitive operations that are open today with no approval are refused on MCP
  first, because the session behind MCP will be the person's own.
- The step in which the person approves a sensitive act is ruled by the owner to be
  taken in Cadrumo and to be enforced by Cadrumo's runtime. How that step reaches an
  operation submitted through MCP is not designed here. It is decided and built early,
  because every sensitive operation waits on it.

## Rationale

The owner's rule is the reason: an agent has full control of the person's data and
operations, and the person approves the sensitive ones. The evidence supports the same
line. Entering and preparing are what the product's own agent material and an accepted
record ask an agent to do, the rules reserve nothing there, and the runtime has no
objection. The hand-off, destruction, elections and consents are what the rules, the
shipped operator rule and an accepted record keep with the person, and a single agent
cannot certify its own work, so those run only on the person's approval. What stays
excluded is what cannot run from MCP, what administers access or the machine, and what an
agent-facing sibling already serves.

## Consequences

- An MCP client can do everything to the person's data that the command line and
  terminal interface can. It exports, records a declaration as filed, destroys data,
  changes who is paid or who can read, gives a consent or sends data off the machine
  only after the person approves that exact act.
- The approval step is on the critical path. Every sensitive operation is refused on
  MCP until it exists, including a few that are open today, so it is built early.
- The packaged skills and personas need correcting where they contradict the rulings.
- These rulings bind the MCP frontend. They do not limit an agent that also holds
  Cadrumo's command line; what is reserved there is decided in
  `2026-10-10-cadrumo-integration-terminal-access-adr`.
- Reconsider a ruling when the evidence behind it changes: a rule or record is amended, a
  need appears for an operation left closed, or reading an executor shows a read is not
  one.
- Accepted 2026-10-10 on the owner's advance authorization of that day: "if all findings
  converge we treat that as the approved state and continue onto plan writing". Two of
  the three reviewing sessions the owner named agreed to the rulings; the third, limited
  by its owner to the runtime, custody and native layer, found no contradiction with the
  runtime and gave no view on the rulings.
- Amended 2026-10-10, after acceptance, on the owner's first-hand rule quoted under
  Considerations. The class "stays closed for now" is gone, every ledger operation is
  operable by an agent, and exclusion is limited to the four grounds of the rule of
  judgement. The owner's rule also answers the two points the first acceptance left to
  them. The reviewing sessions agreed to the earlier text and have not re-read this one;
  the change rests on the owner's ruling, and the classification of which acts are
  sensitive is this record's own, open to the owner's correction.

# Orientation: where to look for each kind of question

This table names `aeat` command families. Through the tool server, `search` finds the
operation that does the same work and `describe` gives its input schema (see the
operating rules). A command with a secret or a profile-wide effect is the person's act.
Where the host supplies the generated `command-operations.md`, it lists for each command
the operations and queries that do its work, and which commands are the person's act;
read it rather than relying on memory. Without that file, `search` instead.

## Capability and result shape

- "Which operations can I use?" -> `search`, then `describe`, under a session. Read the
  registered contract and schema before `execute`; never infer permission.
- "How do I read a result?" -> the envelope-reading rule.

## Obligations and calendar

- "What is due, and when?" -> `aeat app overview calendar` (deadline window),
  `aeat app overview agenda` (due-today, due-soon and overdue around a reference date),
  `aeat app overview backlog` (overdue obligations not yet filed).
- "Does this modelo apply to this taxpayer?" -> `aeat app overview explain`. Read its
  applicability indicator and registry-grounded rationale; never infer applicability
  from a modelo's absence in another output.
- "What is the workspace's state?" -> `aeat app overview status`.

## Modelo lifecycle

- "What are this modelo's casillas and their legal basis?" -> `aeat app modelo describe`
  and `aeat app modelo casillas`; read them before you create a work unit.
- "What is a casilla's value and where does it come from?" ->
  `aeat app modelo work calculate`; see the lifecycle-ordering rule.
- "Is a draft clean enough to export?" -> `aeat app modelo work verify`.
- "What did a past revision store?" -> `aeat app modelo work revision` (one revision, no
  recomputation) and `aeat app modelo work observations` (typed per-casilla provenance).
- "Produce the fileable artefact" -> `aeat app modelo export` (local fichero-BOE) and
  `aeat app modelo work file` (local filed marker). Neither submits to AEAT. Each needs
  the person's go-ahead; record the marker only after they have filed outside the
  application.
- "Did AEAT receive it?" -> `aeat app modelo reconcile pull` or
  `aeat app modelo reconcile import --file`. A local export alone never answers this.
- "What blocks a filing that depends on a prior period or another modelo?" ->
  `aeat app modelo work dependencies`.

## Ledger and evidence

- "Record or import a transaction" -> `aeat app ledger add` (one) or
  `aeat app ledger import --file` (a bank statement or export).
- "Is a transaction ready to feed a calculation?" -> `aeat app ledger review` and
  `aeat app ledger classify`.
- "What needs attention across the ledger, purchase evidence or modelo issues?" ->
  `aeat app review queue`, then `aeat app review view` for one item.

## Live AEAT reads

- "Pull what AEAT holds" -> the `aeat app live` family: `aeat app live justificante pull`,
  `aeat app live filed pull`, `aeat app live notifications pull`,
  `aeat app live expedientes pull`, and `pull-history` in the `iva-wallet` family of
  `aeat app live`. Every verb reads and none submits.
- `aeat app live notifications document pull` stores the served document only when AEAT
  already reports the notification as read, and refuses an unread one: the taxpayer must
  decide when to open it.
- "What history does AEAT hold, and did we get all of it?" ->
  `aeat app live filed discover` first (lists the modelo and ejercicio pairs a sweep would
  walk, persists nothing), then `pull-all` in the `filed` family of `aeat app live`. It has
  no completeness percentage on purpose: part of the walked grid comes from AEAT's own
  option list, whose scoping to this NIF is unconfirmed, so read the report's denominator
  note. A pair marked REFUSED is not a pair with no filings: the read failed, so re-run
  before concluding nothing was filed.

## Law and registry

The application uses its bundled registry when it calculates and files; it does not
expose registry authoring or legal-corpus browsing as commands. For the law itself, use
`corpus_search` or `authority`, or cite the governing official source; a product
command is not legal authority.

## Profile and AEAT access

- "Inspect the taxpayer profile" -> `aeat config profile view` and
  `aeat config profile status`. Creating a profile or anything that takes a password
  is the person's act.
- "Configure AEAT read access" -> ask the person to inspect
  `cadrumo-runtime config auth status`, then use
  `cadrumo-runtime config auth configure` themselves if needed. Explain the
  missing access and wait for the person's result.
  Secrets are entered by the person in Cadrumo, never through the conversation.

## Work that is the person's

Work that belongs to no single profile is not yours, and no tool offers it: the profile
list, profile archives, recovery enrolment, repair, resetting every profile, verifying
review packages the person holds, and the storage tree (`aeat config storage list`,
`aeat config storage view`, `aeat config storage check`, `aeat config storage init`,
`aeat config storage reclaim`, which deletes a category's contents). When your work
needs one, tell the person which command to run in Cadrumo and what it would change,
and continue once they have.

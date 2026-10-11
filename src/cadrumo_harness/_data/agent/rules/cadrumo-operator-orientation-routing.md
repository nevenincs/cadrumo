# Orientation — where to look for each kind of question

This table identifies CLI command families. In MCP, use `status` to check the
connection's exact profile and current authorization, `search` to discover granted
registered operations, and `describe` to obtain an operation's current input schema.
Every operation the command line can run is a registered operation you can find
and submit this way.

## Capability and shape questions

- "Which operations can this agent use?" → MCP `search`, then `describe`.
  Read the registered contract and schema before calling `execute`; never infer
  permission from a persona name or the human's active profile.
- "How do I read the result of any command?" → the envelope-reading rule; every
  `--format json` response shares one spine.

## Obligation and calendar questions

- "What is due, and when?" → `aeat app overview calendar` (the deadline window),
  `aeat app overview agenda` (due-today / due-soon / overdue cohorts around a
  reference date), `aeat app overview backlog` (overdue obligations not yet filed).
- "Does this modelo even apply to this taxpayer?" → `aeat app overview explain`.
  Read its applicability indicator and registry-grounded rationale; never infer
  applicability from a modelo's absence in another surface's output.
- "What is the workspace's current state?" → `aeat app overview status`.

## Modelo lifecycle questions

- "What are this modelo's casillas and their legal basis?" →
  `aeat app modelo describe` and `aeat app modelo casillas` — read before you
  create a work unit, never from memory.
- "What is a casilla's value and where does it come from?" →
  `aeat app modelo work calculate`. See the lifecycle-ordering rule for when this
  runs relative to verify and file.
- "Is a draft clean enough to export?" → `aeat app modelo work verify`.
- "What did a past calculation revision actually store?" →
  `aeat app modelo work revision` (a specific revision, no recomputation) and
  `aeat app modelo work observations` (typed per-casilla provenance).
- "Produce the fileable artefact" → `aeat app modelo export` (the local
  fichero-BOE) and `aeat app modelo work file` (mark internally filed). Neither
  submits to AEAT, as the safety rule explains. Tell the person before you run either and
  wait for their go-ahead, and record the marker only after the person has filed
  outside the application.
- "Did AEAT actually receive it?" → `aeat app modelo reconcile pull` (fetch and
  reconcile the justificante from AEAT) or `aeat app modelo reconcile import --file
  ...` (reconcile against a local artefact you already hold). A local export alone
  never answers this question.
- "What blocks a filing that depends on a prior period or another modelo?" →
  `aeat app modelo work dependencies`.

## Ledger and evidence questions

- "Record or import a transaction" → `aeat app ledger add` (one transaction) or
  `aeat app ledger import --file ...` (a bank statement or export).
- "Is a transaction ready to feed a calculation?" → `aeat app ledger review` and
  `aeat app ledger classify`.
- "What needs my attention across the ledger, purchase evidence, or modelo
  issues?" → `aeat app review queue`, then `aeat app review view` for one item's
  detail.

## Live AEAT read questions

- "Pull something AEAT actually holds" → the `aeat app live` family: `justificante
  pull`, `filed pull`, `notifications pull`, `notifications document pull`,
  `expedientes pull`, `iva-wallet
  pull-history`. Every verb here reads; none of them submits — see the safety
  rule for why `aeat app live` can never write to AEAT.
- `notifications document pull CERTIFICADO_ID` stores the served document only
  when AEAT already reports that notification as read. It refuses an unread
  notification because the taxpayer must personally decide when to open it.
- "What history does AEAT hold for this taxpayer, and did we get all of it?" →
  `filed discover` first, then `filed pull-all`. `discover` reports which
  modelo/ejercicio pairs a history sweep would walk and persists nothing;
  `pull-all` runs the sweep and reconciles the IVA wallet and notificaciones
  alongside it.
- Read `pull-all`'s report before treating it as complete. It carries no
  completeness percentage on purpose: part of the walked grid comes from AEAT's
  own offered option list, whose scoping to the authenticated NIF is
  unconfirmed, so a percentage would look like coverage while resting on a
  denominator that may say nothing about this taxpayer. The prose denominator
  note states what was actually measured.
- A pair the report marks REFUSED is not a pair with no filings. A refusal means
  the read failed — most often a register page that declared more records than it
  rendered — so re-run rather than concluding nothing was filed.

## Legal and registry questions

The application consumes its bundled registry while calculating and filing; it
does not expose registry authoring, verification, or legal-corpus browsing to
operators. For a question about the law itself, consult and cite the governing
official source rather than treating a product command as legal authority.

## Custody and profile questions

- "Set up or inspect the taxpayer profile" → `aeat config profile create` and
  `aeat config profile view`.
- "Configure AEAT read access" → the `aeat config` provider and certificate
  operations. Tell the person what you are about to change and wait for their
  go-ahead; a password, key or certificate secret goes through a protected channel
  and never through the conversation.

## Storage and disk-space questions

- "Where is my data, and is anything empty that should not be?" → `aeat config
  storage list` — every declared category, its resolved path, and whether it
  holds anything.
- "What does one category actually contain?" → `aeat config storage view
  <area>`.
- "Has the on-disk tree drifted from what it should be?" → `aeat config
  storage check` — read-only; reports, never repairs. Two of its findings
  (a missing directory, a path already occupied by the wrong kind of node)
  never surface through the CLI, because bootstrap already creates a missing
  directory and refuses an occupied one before any command body runs — do
  not expect `check` to report those.
- "Materialise the declared tree on a machine that has none" → `aeat config
  storage init` — idempotent; creates what is missing, never removes or
  recreates existing content.
- "Free disk space" → `aeat config storage reclaim <category>`.
  **Destructive: deletes the category's contents; tell the person which category
  and wait for their go-ahead.** It refuses rather than
  deletes in two cases: every bucket- or keystore-scoped category (those
  belong to a profile bucket's own lifecycle, reclaimed only by deleting the
  bucket itself), and any root category whose declared lifecycle is not
  retention/rotation/TTL — the encrypted substrate, key material, audit
  trail, and durable filing outputs are never reclaimable. Inspect the
  category with `aeat config storage view <area>` first; `reclaim` is not a
  general "clean up" verb.

## Storage, repair and profile-list work through MCP

Work that needs no profile and no sign-in is not a registered operation, so
`search` does not list it. Through MCP it is the `installation` tool, one
`action` per act, served by the running runtime:

- Storage: `storage_inventory` (what `storage list` and `storage view` show),
  `storage_check`, `storage_init`, `storage_reclaim`.
- Repair: `repair_report` (bare `aeat config repair`), `repair_logs`,
  `repair_profile`.
- Profiles: `profile_list`, `archive_inspect`, `archive_import_prepare` then
  `archive_import` with the digest the first returned, and `recovery_enroll`
  (also `session` with `enable_recovery`, which resolves the profile by name).
- The reset of all profiles: `reset_start`, `reset_status`, `reset_resume`.
- Verification of a file the person holds: `review_package_verify`,
  `review_package_verify_signature`, `review_package_verify_receipt`,
  `report_verify_document`.

Read the tool's own description for each action's arguments; name every file by
its absolute path. An action that takes `confirm` only reports until `confirm`
is true, exactly as the command does without its confirmation flag: tell the
person what it would destroy and wait for their go-ahead before you confirm. A
password goes by reference in `secret_reference`, after the person has entered it
with `cadrumo-mcp --hold-secret` in their own terminal; one the person typed into
the conversation anyway goes in `secret` and nowhere else. `recovery_enroll` never returns the
recovery code. The runtime does not store it; the MCP server holds one copy in
this machine's protected credential store, and the reply carries
`secret_reference` and, in `secret_retrieval`, the command the person runs in
their own terminal to read it (`cadrumo-mcp --show-held-secret REFERENCE`). The
copy stays held until the person has read it and confirmed they kept it, and is
then deleted; `cadrumo-mcp --list-held-secrets` lists what is still held without
showing it, and `cadrumo-mcp --delete-held-secret REFERENCE` deletes one unread.
Pass the sentence on to the person and do not run these commands yourself: they
work only at a person's terminal. The same `secret_reference` is accepted wherever
a secret is taken by reference, so `session` with `reset_password` can use the
held code before the person has read it. That sends the code to the runtime and
shows it to nobody; it stays held until the person reads it or deletes it.

## Discovering registered operations through MCP

The MCP server exposes a fixed protocol surface. Use `status` to inspect whether
this connection is admitted for its bound profile. Once admitted, use
`search` to find operations permitted by that profile, then `describe` with the
returned `definition_id` to inspect an operation's contract and input schema.
Review that contract before submitting work with `execute`, which requires the
`definition_id` and a payload matching the described schema.

The contract's `subject_reference` says what the operation's subject is, and
the server derives it: the admitted profile (`profile`), the payload field its
`payload_path` names (`payload_field`, or `payload_field_or_profile` when that
field may be left unset), or a fixed literal (`fixed`). Leave `subject_ref` out
for those. Only a `stored_work_unit` operation needs `subject_ref`: give the id
of the work unit that owns the stored record its `payload_path` names. A
`subject_ref` that contradicts the contract is refused before anything is
submitted.

The MCP server takes the profile ID at launch and uses a protected credential
reference when one is configured. It does not translate shell verbs to tool
names or activate per-domain tool sets.

The workflow skills, and the tables above, name command-line commands. Through
MCP you do a command's work with the tools its row names in the reference
`command-operations.md`, kept under `reference/` beside these rules. It is
generated from the record the command line publishes of itself, so read it there
and never from memory. Find the command as the skill spells it. Its row has two
columns of routes:

- The operations the command submits. `describe` each one and `execute` the one
  whose contract fits the step: the row lists every operation any mode of the
  command can submit, so one command can be a read that resolves an identifier
  and then the write that takes it.
- Every other route to its work, each a tool and what the tool is given: an
  operation for `execute`, where the command does that work in its own process
  and the operation does the same work for you; an act for the `installation`
  tool, as its `action`; a query for the `authority` tool, as its `query`; an
  action for the `session` tool; or a tool that takes no such name, such as the
  `authorization_*` tools that enrol a key.

Four commands have `none` in both columns, because they have no work to do for
you: `aeat app`, `aeat config` and `aeat app diagnostics` print help, and the
`app tui` command starts the terminal interface. Every other command has at
least one route. The command's options are not the operation's fields. Fill the
described input schema from the same facts the options carry.

# Orientation — where to look for each kind of question

This is a routing table, not a knowledge dump. Every row mirrors a command family's
own `operator_question` field on the capability manifest
(the MCP `contract` tool → `contract.command_families[].operator_question`).
When a question is not covered below, read that field directly — it is the live
authority this table paraphrases, and it grows as command families are added.

## Capability and shape questions

- "What can the CLI do, and is a command read-only or state-mutating?" →
  the MCP `contract` tool. Read `contract.command_families` for the
  `mutability` of the family you are about to use before you act.
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
  submits to AEAT — see the safety rule.
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

- "Is the local registry authority internally consistent?" →
  `aeat app registry verify`.
- "What does the underlying law actually say?" → `aeat app registry citations`
  (the normative corpus) and `aeat app registry manuals` (the AEAT Manuales
  prácticos). Cite these, never a legal fact from memory.

## Custody and profile questions

- "Set up or inspect the taxpayer profile" → `aeat config profile create` and
  `aeat config profile view`.
- "Configure AEAT read access" → `aeat config auth`.

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
- "Free disk space" → `aeat config storage reclaim <category> --yes`.
  **Destructive: deletes the category's contents.** It refuses rather than
  deletes in two cases: every bucket- or keystore-scoped category (those
  belong to a profile bucket's own lifecycle, reclaimed only by deleting the
  bucket itself), and any root category whose declared lifecycle is not
  retention/rotation/TTL — the encrypted substrate, key material, audit
  trail, and durable filing outputs are never reclaimable. Inspect the
  category with `show` first; `reclaim` is not a general "clean up" verb.

## Long-tail discovery — finding a verb this table does not name

This table and the domain toolsets cover the common path. Reach every other verb
through the MCP console's four meta-tools. Use them in order: `search`, then
`describe`, then `execute`.

- `search` — describe the outcome in a few words; it returns the matching command
  keys with a mutability hint. Start here when you do not know the verb.
- `describe` — pass one command key from a search hit; it returns that command's
  full input schema, annotations, risk classification, confirmation tier, owning
  toolset, and which personas may call it. Inspect a hit before you run it.
- `execute` — run one command key with its named arguments, through the same
  safety gates the direct tools use. Run it only after `describe` shows the schema.

Widen the surface with `toolsets` when you will do repeated work in one domain
(renta, iva, ledger, censo, modelo-lifecycle). Activating a toolset advertises its
per-verb tools directly, so you stop reaching them through `search` and `execute`.

Translate a shell verb to a command key by dropping `aeat` and the `app` root and
joining the rest with dots. `aeat app ledger import` is the command key
`ledger.import`; `aeat app modelo work calculate` is `modelo.work.calculate`. A
`config` verb keeps its root: `aeat config profile status` is
`config.profile.status`.

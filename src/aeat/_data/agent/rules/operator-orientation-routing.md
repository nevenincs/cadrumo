# Orientation — where to look for each kind of question

This is a routing table, not a knowledge dump. Every row mirrors a command family's
own `operator_question` field on the capability manifest
(`aeat app contract --format json` → `contract.command_families[].operator_question`).
When a question is not covered below, read that field directly — it is the live
authority this table paraphrases, and it grows as command families are added.

## Capability and shape questions

- "What can the CLI do, and is a command read-only or state-mutating?" →
  `aeat app contract --format json`. Read `contract.command_families` for the
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
  reconcile the justificante from AEAT) or `aeat app modelo reconcile file --file
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
  pull`, `filed pull`, `notifications pull`, `expedientes pull`, `iva-wallet
  pull-history`. Every verb here reads; none of them submits — see the safety
  rule for why `aeat app live` can never write to AEAT.

## Legal and registry questions

- "Is the local registry authority internally consistent?" →
  `aeat app registry verify`.
- "What does the underlying law actually say?" → `aeat app registry citations`
  (the normative corpus) and `aeat app registry manuals` (the AEAT Manuales
  prácticos). Cite these, never a legal fact from memory.

## Custody and profile questions

- "Set up or inspect the taxpayer profile" → `aeat config profile create` and
  `aeat config profile show`.
- "Configure AEAT read access" → `aeat config auth`.

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

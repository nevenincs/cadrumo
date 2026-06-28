---
tags:
  - '#research'
  - '#aeat-cli-redesign'
date: '2026-05-02'
modified: '2026-05-02'
related:
  - "[[2026-04-24-aeat-cli-wireframe-research]]"
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
  - "[[2026-04-21-google-auth-ux-adr]]"
---



# `aeat-cli-redesign` research: `cli-redesign-wireframe-and-external-cli-research`

This research starts a new CLI redesign loop after the May 2 root cleanup.
The purpose is to replace the current implementation-shaped AEAT CLI with a
user-shaped tax preparation interface. It captures the local grounded
wireframe, then derives language and hierarchy rules from mature complex CLI
tools before any implementation plan is written.

## Findings

### Current local grounding

The current retained AEAT root is narrower than the prior 34-command surface,
but it still does not read like a user tax product. It currently exposes
implementation nouns such as `attachments`, `casillas`, `categories`, `data`,
`normatives`, `filing`, `financial`, and `invoices` beside `auth` and
`deadlines`.

The user intent expressed on May 2 supersedes the April 24 draft root tree.
The older ADR proposed many root domains such as `configure`, `auth`,
`obligations`, `data`, `file`, `review`, `export`, `history`, `revise`, and
`advanced`. That was a useful language inventory, but the new direction is a
much smaller first-contact tree:

```text
aeat
|-- setup
`-- app
```

`setup` owns user-facing environment preparation: first run, local profile,
authentication, storage, and readiness. It absorbs the user-facing parts of
the old `bootstrap`, `doctor`, and `auth` surfaces without using those words
as the first-contact taxonomy.

`app` owns the actual tax preparation workspace. It should not expose provider
utilities, corpus nouns, Google nouns, browser nouns, LLM nouns, or issue
numbers at the top level.

The proposed `app` child domains are:

```text
aeat app
|-- ledger
`-- declaration
```

`ledger` owns evidence preparation: importing statements and invoices,
normalizing records, classifying transactions, linking invoices or receipts,
managing asset and inventory ledgers, and previewing tax-ready period inputs.

`declaration` owns filing preparation: obligations, draft import, draft
creation, calculation/review, validation, amendment, export readiness, and
eventually final exported artifacts.

This scaffold is intentionally smaller than the prior `data/file/review/export`
split. The older split is useful internally, but the user should not need to
choose among four separate filing-stage roots before they know whether they
are preparing a tax return or cleaning records.

### Current capability mapping

The grounded mapping to existing code is:

| Proposed surface | Existing surfaces it wraps | Notes |
| --- | --- | --- |
| `setup start` | `bootstrap`, selected `auth init`, readiness checks | Guided first-run path. Avoids "bootstrap" in user copy. |
| `setup check` | `doctor` | Plain readiness report; not a medical/debug metaphor. |
| `setup auth` | `auth configure`, `auth login`, `auth status`, `auth logout`, `auth whoami` | User-facing AEAT access story. |
| `setup profile` | profile config currently spread across settings, deadlines, filing, usage ratios | Needs a coherent local taxpayer profile contract before implementation. |
| `setup storage` | secure persistence and master-key readiness checks | Should be user-facing only when there is an action to take. |
| `app ledger import` | `financial ingest`, `financial txs build` | Prefer "import" over "ingest" and hide source-provider vocabulary until flags. |
| `app ledger transactions` | `financial txs list/show` | This is a resource subdomain; leaves can be `list`, `show`, `classify`, `edit`. |
| `app ledger classify` | `financial txs classify`, `classify-llm` | AI/provider variants should be advanced flags or hidden strategy details, not a noun in first-contact help. |
| `app ledger invoices` | `financial invoices list/show/link/unmatched/reconcile` | "Invoices" is a real user noun and belongs here. |
| `app ledger assets` | `data ledgers assets` | Current help uses tax-law and depreciation language too early. |
| `app ledger inventory` | `data ledgers inventory` | Keep as a specialized ledger subdomain. |
| `app declaration obligations` | `deadlines list/next/explain` | Deadline calculation is a declaration concern in the two-domain model. |
| `app declaration import` | `filing import` | Import AEAT PDFs or prior draft material into the declaration workspace. |
| `app declaration prepare` | `filing build` | Prefer "prepare" for user workflow; `build` is tool-maker language. |
| `app declaration review` | `filing validate`, future review queue pieces | Must show missing data and decisions in user terms. |
| `app declaration show` | `filing show`, `filing list` | Could be `list` and `show` under a `drafts` resource if needed. |
| `app declaration amend` | `filing complementaria` | Spanish legal term can appear in help, but English action remains first. |

### External CLI research sources

The external research used primary documentation from these mature CLIs:

- Google Cloud CLI command conventions and overview
- Kubernetes `kubectl` usage conventions
- GitHub CLI manual
- AWS CLI command structure guide
- Azure CLI reference and usage guidance

The strongest transferable pattern is from gcloud: commands form a tree with
groups in inner nodes and executable commands at leaf nodes. The command line
is consistently shaped as base command, group(s), command, positional
arguments, then flags. This supports a compact AEAT form such as:

```text
aeat app ledger import statement FILE --year 2025
aeat app declaration prepare 303 --period 2025Q1
```

The most important gcloud distinction for AEAT is positional argument versus
flag. A positional identifies the entity being operated on; flags configure
behavior. For AEAT, `303`, `2025Q1`, `statement.pdf`, `invoice-id`, and
`transaction-id` are often entities. Strategy choices such as output format,
AI use, dry run, profile override, and noninteractive mode are flags.

GitHub CLI shows another useful pattern: separate core commands from
additional commands. The AEAT equivalent is that `setup` and `app` are the
core product, while reference/provider/diagnostic surfaces move behind an
advanced or hidden compatibility surface.

kubectl contributes scripting discipline: machine-readable output must be
explicit, scripts should not depend on implicit context when stable operation
matters, and dry-run is a preview mechanism. AEAT should keep interactive
human output separate from `--json` output and should avoid making hidden
profile state the only way to reproduce a command.

AWS CLI reinforces a service/resource plus operation structure. The direct
transfer is not to make AEAT service-shaped, but to keep ordering stable:
base, domain/resource, operation, then options. It also validates special
verbs like `wait` only when they represent a distinct operator behavior.

Azure CLI demonstrates both the strength and weakness of very large command
sets. It uses many "Manage ..." command descriptions and exposes status/type
metadata, but its root is huge because it represents an entire cloud. AEAT is
not a cloud platform; it should not copy Azure's breadth. It should copy the
status disclosure idea for advanced/preview/deprecated surfaces.

### Wording rules derived from the research

Root nouns must be few and user-domain-shaped. For AEAT, the current candidate
root nouns are exactly `setup` and `app`.

Intermediate nouns should be stable work areas, not implementation packages.
`ledger` and `declaration` are acceptable because a user can understand them
as tax preparation domains. `financial`, `data`, `filing`, `casillas`,
`normatives`, `cloud`, and `llm` are not acceptable first-contact domains.

Leaf commands should be verbs. Preferred verbs:

- `start`: guided setup or guided workflow entry
- `check`: readiness or validation where the object is clear
- `import`: bring outside evidence into local state
- `list`: enumerate records
- `show`: inspect one record or draft
- `classify`: assign business/private and tax treatment to transactions
- `link`: connect records such as invoice and transaction
- `review`: inspect pending decisions and warnings
- `prepare`: create or refresh a declaration draft
- `validate`: run strict consistency checks
- `export`: produce an external filing artifact
- `amend`: start or manage a correction flow

Words to retire from user-facing first-contact copy:

- `bootstrap`
- `doctor`
- `helper`
- `engine`
- `catalogue` unless the object is truly a user catalogue
- `GCP`, `Drive`, `Docs`, `Cloud`, `OAuth client`, `browser`, `LLM`
- issue numbers such as `#73`
- raw internal nouns such as `casilla` before the declaration review level
- abbreviations such as `txs`, `NDJSON`, `MCP`, and provider-specific labels

### Proposed wireframe for review

This is the grounded first review wireframe, not an implementation plan:

```text
aeat
|-- setup
|   |-- start
|   |-- check
|   |-- profile
|   |-- auth
|   `-- storage
`-- app
    |-- ledger
    |   |-- import
    |   |-- transactions
    |   |   |-- list
    |   |   |-- show
    |   |   |-- classify
    |   |   `-- edit
    |   |-- invoices
    |   |   |-- list
    |   |   |-- show
    |   |   |-- link
    |   |   |-- unmatched
    |   |   `-- reconcile
    |   |-- assets
    |   |-- inventory
    |   `-- preview
    `-- declaration
        |-- obligations
        |   |-- next
        |   |-- list
        |   `-- explain
        |-- import
        |-- prepare
        |-- review
        |-- validate
        |-- list
        |-- show
        |-- export
        `-- amend
```

Alternative to discuss: collapse `transactions` and `invoices` verbs upward:

```text
aeat app ledger list transactions
aeat app ledger show transaction TX_ID
aeat app ledger classify transaction TX_ID
aeat app ledger list invoices
```

This reads closer to gcloud's group-command-entity shape but is longer. The
first wireframe keeps user resources as groups because it is easier to scan.

### Open questions for user revision

- Is `app` too generic as the product workspace noun, or should the root be
  `tax`, `work`, or `prepare`?
- Should `setup auth` expose `login/status/logout` as subcommands, or should
  those remain direct actions under `setup auth` with a guided default?
- Should `app declaration obligations` be shortened to `app declaration
  deadlines`, or is "obligations" the better tax concept?
- Should `app ledger preview` become `app ledger summary` or `app ledger
  tax-inputs`?
- Should `export` live under `declaration` in this two-domain model, or does
  it deserve a later top-level app subdomain after the declaration workflow
  matures?
- Should compatibility aliases be visible, hidden, or grouped under an
  `advanced` root that is deliberately absent from first-contact help?

### Working recommendation

Proceed to a revised ADR only after user review of the scaffold. The strongest
initial direction is:

```text
aeat setup ...
aeat app ledger ...
aeat app declaration ...
```

This is more coherent than the April 24 multi-root tree because it matches the
user's current intent and provides a smaller mental model. It is also grounded
enough to implement as Typer wrapper groups over current modules without
rewriting domain logic first.

### Research limitations

The local `vaultspec-rag search` path could not be used because the configured
sparse model required access to a gated Hugging Face repository. Existing vault
context was therefore gathered through `vaultspec-core vault list` plus direct
reads of the specific prior research and ADR files.

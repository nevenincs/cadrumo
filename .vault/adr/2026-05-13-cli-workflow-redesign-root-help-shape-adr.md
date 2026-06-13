---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-overview-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `Root help and discovery surface shape` | (**status:** `accepted`)

## Problem Statement

The HARD RULE locks the root surface to `aeat config` and `aeat app`,
and the apex §10A vocabulary section names mistype suggestions and
canonical period tokens. But the apex does not specify what `aeat`
(bare invocation), `aeat --help`, `aeat config --help`, or `aeat app
--help` actually render. Without a defined shape, every Typer-driven
implementation will produce a different help tree, breaking
discoverability for first-time users and returning operators.

## Considerations

- Typer/Click generates a default help message from registered
  commands. The default is alphabetical and verbose; it works against
  workflow-oriented discoverability.
- Operators typing `aeat` with no arguments expect either a top-level
  status summary or a curated entry-point hint, not a usage error.
- Help text is the operator's primary onboarding surface; it must
  reflect the workflow order, not the registration order.
- Spanish autónomo personas have asymmetric English / Spanish
  fluency; one-line descriptions must be plain and free of jargon.

## Constraints

- `aeat` with no arguments and no flags executes the equivalent of
  `aeat app overview agenda`. This is the canonical "where do I stand?"
  entry point.
- `aeat --help` and `aeat -h` render the curated root-help shape (see
  Implementation). They do NOT execute `overview agenda`.
- The curated help groups commands by workflow phase: Setup, Daily
  ledger work, Modelo lifecycle, Diagnostics. Within each group,
  commands are ordered by typical use sequence, not alphabetically.
- Every command listed in the root help includes a one-line
  description (max 80 chars) in plain language. Spanish-anchored
  vocabulary (`apoderado`, `borrador`, `justificante`) carries an
  English gloss in parentheses.
- The §10A mistype-suggestion list (`aeat init` → `aeat config init`,
  etc.) is rendered at the bottom of the root help as a "common
  mistypes" footer with the same one-line format.
- `aeat config --help` and `aeat app --help` render the same workflow-
  ordered shape for their own sub-trees.
- The HARD RULE is repeated as the first paragraph of `aeat --help`:
  "The CLI has exactly two roots: `config` and `app`. Type `aeat
  config --help` or `aeat app --help` to explore."

## Implementation

Root help shape (`aeat --help`):

```text
aeat — local-first Spanish autónomo tax-filing CLI

The CLI has exactly two roots: config and app.

Setup
  aeat config init                  Create your first profile and bucket
  aeat config profile use NAME      Switch the active profile (alias: set active)
  aeat config auth configure        Configure FNMT/Cl@ve/DNI-e authentication

Daily ledger work
  aeat app ledger import            Import bank statements and invoices
  aeat app ledger classify          Classify a transaction
  aeat app ledger allocate          Record business/personal allocation
  aeat app ledger attach            Attach a receipt or evidence
  aeat app ledger check             Report data-quality blockers

Modelo lifecycle (calculate → verify → file)
  aeat app modelo bindings list     Show modelo prerequisites
  aeat app modelo calculate         Produce or refresh a calculation revision
  aeat app modelo verify            Mark a revision verified complete
  aeat app modelo file              Mark a revision filed internally
  aeat app modelo export            Emit the BOE-format fichero

Live AEAT reads (read-only, never submits)
  aeat app live notifications       DEHú inbox snapshot
  aeat app live verify nif-iva NIF  VIES check
  aeat app live borrador 100 fetch  AEAT pre-fill snapshot for IRPF

Diagnostics
  aeat config repair                Composite health report (diagnose and fix)
  aeat config bucket history        Audit trail for the active bucket
  aeat app overview status          Cross-domain readiness

Common mistypes
  aeat init       → aeat config init
  aeat setup      → aeat config init
  aeat status     → aeat app overview status
  aeat sanitize   → aeat app ledger check
  aeat archive    → aeat config bucket
  aeat submit     → rejected (live submission is permanently disabled)

Run `aeat config --help` or `aeat app --help` to see all commands.
```

Sub-root help shape (`aeat config --help` and `aeat app --help`):

- Same workflow-phase grouping, restricted to that sub-tree's
  commands.
- The first paragraph names the sub-tree's purpose in one sentence.
- A footer line links back: "Run `aeat --help` for the full overview."

Bare-invocation behavior:

- `aeat` with no arguments executes `aeat app overview agenda` against
  the active profile.
- If no active profile is set, the bare invocation emits a friendly
  redirect message: "No active profile. Run `aeat config init` to get
  started." Exit code 0.

## Rationale

A workflow-ordered help shape is the single biggest discoverability
lever available to operators learning the CLI for the first time.
Alphabetical help trees are correct but useless: an operator
struggling to file 303 quarterly does not benefit from seeing
`amend` before `calculate`. The bare-invocation `overview agenda`
behavior gives returning operators a one-keystroke "where am I?"
that the prior design left unspecified. The mistype-suggestion
footer makes the apex §10A vocabulary section discoverable at the
moment of need.

## Consequences

- The Typer root app and the `app` / `config` sub-apps must override
  the default help renderer to produce the workflow-ordered shape.
- Every command's one-line description (the Typer `help=` argument)
  must conform to the 80-character, plain-language standard.
- Translations of help text (per the quadlingual-i18n ADR) must
  preserve the workflow grouping; group headers are also translated.
- Tests must cover: `aeat --help` renders the curated shape, not the
  default Typer list; `aeat` bare invocation executes `overview
  today` when a profile is active; bare invocation redirects to
  `config init` when no profile exists; every command listed in help
  has a non-empty one-line description; mistype suggestions render in
  the expected order.

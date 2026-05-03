# AEAT CLI test simulator

Temporary interactive simulator for the AEAT CLI v6 redesign.

Status: v6 review candidate, not approved for implementation.

Open `index.html` for the command simulator or `approval-session.html` for the
section-by-section approval session. The pages are dependency-free and keep
state in browser local storage.

## What V6 Tests

- Separation between setup prerequisites and app operation.
- Authentication as provider configuration plus AEAT login.
- Profile as schema-backed taxpayer data with discoverable editable keys.
- Singular app domains: `overview`, `ledger`, `invoice`, and `declaration`.
- Ledger import as one action: `ledger import PATH --provider PROVIDER`.
- Import diagnostics through `--verify`, including gap, duplicate, parser, and
  original-file checks.
- Read-only ledger inspection through `list` and `show`.
- Ledger edits through repeated `--set column=value`.
- Skip and unskip decisions through `ledger edit --skip true|false`.
- Mixed-use splits through share values that add to `1.0`.
- Invoice enrichment for base, IVA rate, IVA amount, IVA category, retention,
  payment linkage, references, comments, and document paths.
- Declaration calculation with visible summary output and human review gates.
- Local validation, preview, export, and verification with explicit outputs.
- Corrective declaration work through a recalculated draft.
- Interruption/resume as profile-scoped persisted app state.
- Global `--verbose` diagnostics on state-sensitive workflows.

## Removed From The Candidate Command Surface

Rejected or held-out grammar categories:

- account as a setup command family
- auth as an import/validation shortcut
- import as a nested domain with `verify`, `gaps`, `duplicates`, `exclude`, or
  `restore`
- ledger `exclude` and `restore`
- supporting files as standalone attach commands
- declaration support bundles as a package command
- separate amendment/corrective-filing subcommands
- separate CSV-code concepts for corrective declarations
- `declaration verify --export`
- one-off needs-review flags instead of `--filter status=pending`
- user-facing session/workspace save-load commands

The simulator may warn when old commands are typed so tape audits can measure
command-guess distance, but the command tree and tapes do not depend on those
old forms.

## Running Generated Audits

From this folder or the repository root:

```text
node tmp/cli-test-simulator/run-audits.js --runs 250 --seed kent-n26-v6 --out tmp/cli-test-simulator/generated-findings-v6.md --format md
```

The web simulator also has a Generative audit panel. Run a seeded audit,
inspect aggregate findings, then play the generated sample tape against the
interactive terminal.

## Core Command Model

```text
aeat
  setup
    init
    status
    auth
      providers
      configure --provider PROVIDER
      login
      status
      whoami
      logout
    profile
      use NAME
      show
      keys
      list-keys
      get KEY
      set KEY VALUE
      unset KEY
      validate
      list

  app
    overview
      status [--calendar] [--period PERIOD]
      next

    ledger
      import PATH --provider PROVIDER [--verify] [--source PATH]
      review [--filter KEY=VALUE] [--id RECORD_ID]
      edit --id RECORD_ID --set COLUMN=VALUE
      edit --id RECORD_ID --skip true|false
      edit --id RECORD_ID --split business=SHARE --split personal=SHARE
      edit --id RECORD_ID --split clear

    invoice
      import PATH --kind issued|received
      review [--filter KEY=VALUE] [--id INVOICE_ID]
      edit --id INVOICE_ID --set COLUMN=VALUE
      match
      verify

    declaration
      calculate
      review
      status --filter KEY=VALUE
      edit --set COLUMN=VALUE
      approve
      validate
      preview
      export --output PATH
      verify --id DRAFT_ID --file PATH
```

The simulator intentionally avoids current implementation terms such as
`financial`, `filing`, `bootstrap`, `doctor`, `txs`, `catalogue`, `NDJSON`,
provider internals, issue numbers, and developer commands.

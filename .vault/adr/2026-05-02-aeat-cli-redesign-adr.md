---
tags:
  - '#adr'
  - '#aeat-cli-redesign'
date: '2026-05-02'
modified: '2026-05-02'
related:
  - "[[2026-05-02-aeat-cli-redesign-research]]"
  - "[[2026-05-02-aeat-cli-redesign-reference]]"
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
  - "[[2026-04-18-live-submit-cli-excision-adr]]"
  - "[[2026-04-17-export-first-adr]]"
  - "[[2026-04-21-auth-cli-adr]]"
---



# `aeat-cli-redesign` adr: `user-cli-redesign-review-contract-v6` | (**status:** `in progress`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

The AEAT user CLI redesign remains in progress. The latest approval comments
require a v6 rework because the v4 surface still presented rejected import,
skip, verification, and corrective declaration concepts as viable command
grammar.

This ADR records the v6 review candidate. It does not accept a final command
tree, authorize implementation, approve aliases, supersede prior no-live-submit
safety decisions, or permit any live AEAT submission behavior.

## Considerations

The accepted root direction remains `aeat setup` plus `aeat app`. Setup owns
authentication, profile data, and local readiness. App owns operational tax
work: overview, ledger, invoice, and declaration.

The v6 design removes the rejected setup account family. Identity is exposed
through auth and profile status. Profile data must be schema-backed so users can
discover editable keys, set and unset values, validate completeness, and revise
profile facts without bespoke command families.

Authentication is not an import-validation surface. It is provider
configuration plus AEAT login state. The v6 candidate exposes auth provider
listing, configuration, login, status, whoami, and logout. Implemented provider
wording is limited to certificate and `clave_movil`; `clave_permanente` remains
research-only until backend support exists.

The app domain map is singular: `overview`, `ledger`, `invoice`, and
`declaration`. Calendar discovery belongs inside overview. Review files,
references, comments, invoice links, and payment links are record fields, not
standalone command nouns. User-facing sessions and workspaces remain rejected.

Ledger is the transaction review table that makes records eligible or
ineligible for tax calculations. The ledger schema is not manually approved by
this ADR. It must be driven by backend library behavior, migrations, and audit
output. The target contract includes stable row identity, source import
identity, source transaction identity, period, date, description, amount,
direction, status, category, `business.share`, skip state, reference, comments,
invoice link, document path, modelo association, review history, and split
metadata.

Ledger import is an action, not a command domain. The review candidate uses
`aeat app ledger import PATH --provider PROVIDER`. Import diagnostics, including
original-file checks, gap checks, duplicate checks, parser checks, and verbose
diagnostics, are exposed by `--verify`, `--source PATH`, and `--verbose`. The
candidate rejects import subcommands named `verify`, `gaps`, `duplicates`,
`exclude`, or `restore`.

Ledger skip state is an auditable edit, not a separate exclude/restore command
pair. The candidate uses `aeat app ledger edit --id ROW --skip true --reason
REASON` and `aeat app ledger edit --id ROW --skip false --reason REASON`.

Mixed-use transactions use split share values. The candidate command is
`aeat app ledger edit --id ROW --split business=SHARE --split personal=SHARE --reason REASON`, where shares must add to `1.0`. Backend implementation must preserve
source transaction identity, split metadata, and a clear path such as `aeat app
ledger edit --id ROW --split clear --reason REASON`.

Invoice is a separate review and enrichment domain. It must be separated from
ledger transaction evidence. The target invoice contract includes id, kind,
status, issue date, counterparty, base, IVA rate, IVA amount, IVA category,
retention rate and amount, payment link, document path, reference, comments,
lines, and review history. Current backend support must be audited before
retention and IVA category claims become implementation commitments.

Declaration is the filing work domain. It owns calculation, review, status,
edit, approval, validation, preview, export, verification, and recalculation
after records change. Bare `calculate` must print a compact summary table, blocker
counts, warnings, and the next action. If inputs are unresolved, it must show
repair hints instead of succeeding silently.

Export and verify are separate. Export writes a local artifact and therefore
requires `--output PATH`. Verify does not accept an export flag; it verifies an
exported file through `--file PATH` and may emit machine-readable output through
the root `--format json` option.

Corrective declaration work recalculates a new draft and compares it against the
previous approved/exported draft. The candidate rejects any extra
corrective-filing noun, any amendment subcommand, any amendment flag, and any
separate CSV-code identity in the user CLI. Official AEAT correction identity
requirements remain a backend/legal mapping to confirm per modelo before
release.

## Decision

Adopt the v6 recovered-comment review candidate as the current design surface
for continued review only.

- Keep `aeat setup` and `aeat app` as the root boundary.
- Keep setup auth as provider configuration plus login.
- Keep setup profile as a schema-backed editor.
- Use singular app domains: `overview`, `ledger`, `invoice`, `declaration`.
- Treat ledger and invoice files, references, comments, and links as editable
  record fields.
- Use `ledger import PATH --provider PROVIDER` and `--verify` for import
  verification and coverage checks.
- Use `ledger review` and `ledger edit` for row review.
- Use `ledger edit --skip true|false` instead of exclude/restore.
- Use split share values that add to `1.0`.
- Use singular `invoice` with import, review, edit, match, and verify workflows.
- Use declaration calculation, review, status, edit, approval, validation,
  preview, export, and verification gates.
- Recalculate a new declaration draft after late or corrected records.
- Keep all live submission behavior out of scope.

This ADR explicitly rejects:

- standalone account commands
- auth file import shortcuts
- import subcommands for verification, gap checks, duplicate checks, exclude, or
  restore
- ledger exclude and restore commands
- standalone supporting-file command nouns
- declaration package/support bundle commands
- corrective declaration nouns and amendment subcommands
- separate CSV-code identity flags
- `declaration verify --export`
- user-facing session/workspace commands
- bare help aliases as the canonical form

## Constraints

This ADR is in progress and grants no implementation authorization.

No live submission behavior is authorized. `export` means local files. `verify`
means local declaration verification before manual AEAT upload or supported
identifier inspection.

The active setup profile is the normal app identity context. Routine user
interaction must not depend on global profile or workspace override flags.

Canonical app domain nouns are singular.

Every command group must provide useful `--help`. State-sensitive commands must
have a clear dry-run policy where practical. Diagnostic commands must support
`--verbose` where useful.

## Implementation

No production implementation is authorized by this ADR.

A later implementation plan must first complete backend audits for:

- Auth provider capabilities and controlled login flows.
- Profile key registry, validation, and storage.
- Ledger row schema, skip state, split metadata, edit history, filters, and
  lifecycle.
- Import verification output for original-file, gap, duplicate, and parser
  diagnostics.
- Invoice metadata, line totals, IVA category mapping, retention, and payment
  linkage.
- Declaration calculate output, review/edit/approval, staleness checks,
  validation, export, and verification.
- Correction terminology, prior AEAT identity rules, and legal layering.

The current simulator is a review artifact only. It can replay messy user paths
and surface gaps, but it is not a production command contract.

## Rationale

Keeping this ADR in progress is mandatory because the latest approval comments
reject substantial parts of v4. Treating v4 as approved would lock in import as
a command domain, rejected exclude/restore verbs, amount-based split examples,
ambiguous calculate output, `verify --export`, and an extra amendment command
noun.

The v6 surface is driven by the user's real work: set up authentication and
profile data, import and verify transaction records, revise ledger decisions,
enrich invoice records, review declaration calculations, reject unsafe export
states, and recalculate a declaration when new data appears after export.

Preserving local-export and no-live-submit constraints protects prior safety
work while the command model is still under review.

## Consequences

The redesign cannot move to an accepted ADR or implementation plan until the
reopened and backend-audit items are resolved.

The next approval session must review the v6 surface. Tapes must cover invalid
imports, incomplete periods, duplicate and wrong-account imports, manual ledger
record review, mixed payments, split clearing, user revisions, skip and unskip
decisions, invoice base and IVA metadata, retention metadata, invoice matching,
multi-period backlog work, missed deadlines, stale calculations, export refusal,
validation reports, local export, export verification results, recalculated
declaration drafts after late records, and profile-scoped interruption recovery.

No execution record or implementation plan may treat this ADR as approval to
ship the redesigned CLI.

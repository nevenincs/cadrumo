---
tags:
  - '#research'
  - '#cli-design'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-10-eliminate-user-cli-shim-plan]]"
  - "[[2026-05-10-cli-structural-localization-audit]]"
  - "[[2026-04-12-workflow-engine-adr]]"
  - "[[2026-04-12-workflow-engine-audit]]"
---



# `cli-design` research: `Current CLI state and rewrite history`

This research maps the live CLI after the recent root-surface rework, traces the
main rewrite history that led to the current shape, and identifies backend or
CLI functionality that still exists but is no longer mounted on the operator
path. The goal is to prepare a proper ADR for CLI redesign and to support a
section-by-section wireframe review of the `app` domains.

## Findings

## 1. Rewrite history: what changed

The current CLI is the result of a deliberate contraction of the public root,
not just accidental deletion.

- Early feature history exposed many separate command families:
  `workflow`, `deadlines`, `filing`, `financial`, `auth`, `browser`, and
  related operational surfaces. The historical chain is visible in the `git log`
  for `src/aeat/entrypoints/cli/__init__.py`, including:
  - `068df2a4` — composite workflow engine
  - `178cbd45` — deadlines engine
  - `193a5189` — filing draft CLI
  - `723dbed3` — auth CLI
  - `fd541c83` — observability / replay
  - `487582ea` — unified review queue
- A later restructuring wave concentrated the operator surface:
  - `e2e14327` — “Restructure AEAT CLI and registry export tests”
  - `afde5503` / `e49ccce5` — gap-closure and final shape hardening
- The live root now mounts only `setup`, `config`, `archive`, and `app` in
  `src/aeat/entrypoints/cli/__init__.py`.

This means the present CLI should be read as a design choice under active
revision, not as a naturally grown final command tree.

## 2. Current mounted root surface

The live root CLI exposes four first-level surfaces:

- `setup`
- `config`
- `archive`
- `app`

`setup` is the operator prerequisites surface:
- profile creation and mutation
- auth provider configuration and login readiness
- overall setup readiness status

`config` is the local environment and diagnostics surface.

`archive` is a lifecycle / portability surface for local persisted state.

`app` is the operational tax-work surface and currently mounts:
- `overview`
- `ledger`
- `invoice`
- `declaration`
- `modelo`
- `registry`

The tests in `src/aeat/entrypoints/cli/test_workflow_surface.py` explicitly pin
the absence of top-level `auth`, `financial`, `filing`, and other historical
command families. This is not merely undocumented; it is enforced by tests.

## 3. Current `app` subdomains: what they do

These are the live user-facing subdomains under `app`, with a first-pass reason
for why they may deserve separate ownership.

### `overview`

What it does:
- renders workspace counts
- renders filing calendar views
- renders per-period draft summaries
- surfaces unreadable secure-object integrity warnings

Why it can stand alone:
- it is the operator’s status and orientation layer across multiple downstream
  systems

One pro:
- gives the user a global “where am I?” surface without forcing them into any
  one object type

One con:
- it is mostly a projection layer, so it risks becoming a thin dashboard over
  other domains rather than a domain with strong behaviors of its own

### `ledger`

What it does:
- imports bank / statement data through provider adapters
- verifies sources
- persists transaction catalogues
- exposes review and edit flows for transaction treatment and split metadata

Why it can stand alone:
- it owns a full ingestion-and-review lifecycle around financial transactions

One pro:
- the boundary is concrete: statement import, transaction normalization, review,
  and persistence are tightly related operator tasks

One con:
- some of its semantics overlap with older `financial` and `transactions`
  surfaces, so naming and ownership can drift if the taxonomy is not tightened

### `invoice`

What it does:
- imports invoice records
- exposes invoice review
- supports manual payment matching against ledger transactions

Why it can stand alone:
- invoice review and reconciliation are operationally distinct from bank-ledger
  classification even when they share artifacts

One pro:
- invoices have their own object model, errors, matching logic, and operator
  decision flow

One con:
- invoice and ledger together form one reconciliation story, so a split UI can
  feel fragmented unless the handoff is explicit

### `declaration`

What it does:
- calculates drafts
- resolves selector-based draft access
- supports review, edit, approve, validate, export, and verify flows
- persists declaration pointers into workflow state

Why it can stand alone:
- this is the closest thing to the current user-visible filing workflow

One pro:
- it is the highest-value operational surface because it converts reviewed data
  into filing-grade artifacts

One con:
- it currently absorbs some workflow responsibilities because the dedicated
  `workflow` surface is absent, so its boundary is at risk of becoming too broad

### `modelo`

What it does:
- user-facing registry introspection
- list / describe / casilla / binding / formula queries against validated
  registry authority snapshots

Why it can stand alone:
- it is a discovery and explanation surface for the filing models themselves,
  not for operator transactions or drafts

One pro:
- it gives users an inspectable truth source for what the system believes a
  modelo is

One con:
- it is expert-heavy and may be too technical for the main operator journey if
  surfaced too prominently

### `registry`

What it does:
- read-only registry verification
- workbook parity and verification commands
- AEAT-backed or source-backed registry trust checks

Why it can stand alone:
- it is a governance / truth-audit surface rather than an operator tax task

One pro:
- strong fit for advanced verification, parity, and source-of-truth auditing

One con:
- this feels closer to an expert or maintenance plane than to the main app task
  flow, so keeping it inside `app` may blur “user operations” vs “system
  verification”

## 4. Implemented but unmounted CLI surfaces

The repo still contains real CLI packages that are not mounted on the live root.
These are not all dead code; several still carry meaningful logic and tests.

### `financial`

What exists:
- `ingest`
- `txs`
- `invoices`
- `profile`

Current meaning:
- this is the older financial pipeline surface that the new `app ledger` and
  `app invoice` surfaces partially replace

Research judgment:
- this is the strongest example of “existing functionality stranded under old
  transport”

### `filing`

What exists:
- build / validate / show / list / import
- complementaria support
- draft rendering and next-step suggestions

Current meaning:
- this is a broader filing engine CLI than the user-facing `app declaration`
  surface

Research judgment:
- much of this is still real operator value and should be considered during ADR
  work, especially around whether `app declaration` is meant to replace it
  entirely or only simplify the common path

### `deadlines`

What exists:
- `list`
- `next`
- `explain`

Current meaning:
- the explicit deadline engine CLI still exists, while the mounted tree mainly
  exposes filing work after setup

Research judgment:
- this is a credible future `app` candidate because deadline reasoning is a real
  operator concern, not just backend machinery

### `browser`

What exists:
- `health`

Current meaning:
- an operational probe surface around Playwright / AEAT browser reachability

Research judgment:
- useful, but likely belongs in a support or diagnostics plane rather than the
  main `app` path

### `auth` top-level package

What exists:
- `src/aeat/entrypoints/cli/auth/`

Current meaning:
- historical direct auth command family, now intentionally subsumed under
  `setup auth`

Research judgment:
- this looks like a deliberate transport consolidation rather than a missing
  user feature

## 5. Backend/application functionality with incomplete CLI exposure

Several backend surfaces exist as real application capabilities but are only
partially visible or not cleanly expressed in the live CLI.

### `application.workflow`

What exists:
- workflow engine
- workflow state
- workflow run persistence
- declaration pointers

Current exposure:
- state and pointer writes are used by `app declaration`, `app invoice`, and
  `app ledger`
- engine execution and run-history surfaces are not exposed as user commands

Why this matters:
- this is the clearest “backend exists, user journey hidden” gap

### `application.review`

What exists:
- unified review adapters and queue logic
- edit parsing
- filter parsing
- review record models

Current exposure:
- parts are surfaced through `app ledger`, `app invoice`, and declaration review
- the older “one-command pipeline dashboard” intent is no longer visible as one
  mounted surface

### `application.setup`

What exists:
- setup wizard
- environment writer
- verifier
- prompter and wizard models

Current exposure:
- live root uses non-interactive `setup init` / `setup auth` / `setup profile`
- the richer wizard remains backend-first rather than openly surfaced

### `application.transactions`

What exists:
- import and diagnostics support

Current exposure:
- transaction work is mostly visible through `app ledger`, not a distinct
  transaction domain

### `application.archive`

What exists:
- import/export/archive registry

Current exposure:
- mounted at root as `archive`, which makes sense as a cross-domain lifecycle
  concern rather than an `app` concern

## 6. CLI design pressure points

The research points to five active design tensions:

- The root is intentionally narrower than the implementation inventory.
- `app` mixes true user-work domains (`ledger`, `invoice`, `declaration`) with
  more expert or governance surfaces (`modelo`, `registry`).
- The dedicated workflow engine exists, but the user-visible workflow grammar is
  mostly embedded inside `declaration`.
- There are at least three competing taxonomies still visible in the code:
  `workflow`, `financial`, and the new `app ledger` / `app invoice` split.
- `setup auth` is a successful example of consolidation: auth remains first-class
  functionality, but it no longer needs its own top-level root.

## 7. ADR implications

The upcoming ADR should answer at least these questions:

- Is `app` the long-term operator root, or a temporary aggregator?
- Which current `app` subdomains are true product domains versus expert tools?
- Is `workflow` supposed to return as a first-class user command, or should its
  user journey remain embedded in `declaration`?
- Should `financial` be formally retired in favor of `ledger` + `invoice`, or
  revived as a broader operator root for data-prep work?
- Should `modelo` and `registry` stay inside `app`, move under `config`, or live
  under a separate expert / audit plane?
- Which backend capabilities are intentionally hidden, and which are merely
  unconnected?

## 8. Recommended wireframe review order

For section-by-section approval, the cleanest order is:

- Root framing: `setup`, `config`, `archive`, `app`
- `app overview`
- `app ledger`
- `app invoice`
- `app declaration`
- `app workflow` or explicit decision to keep workflow embedded
- `app deadlines` or explicit decision to keep deadlines implicit
- advanced/expert plane: `modelo`, `registry`, browser-health style probes

This order starts with the operator’s journey, then moves into expert and
governance tooling last.

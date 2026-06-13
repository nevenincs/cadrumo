---
tags:
  - "#research"
  - "#cli-workflow-redesign"
date: 2026-05-12
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# CLI workflow redesign app modelo shape research
Date: 2026-05-12

## Purpose

Define the complete `aeat app modelo` command surface for the
`cli-workflow-redesign` feature and identify the object boundaries that keep
modelo work units, calculation revisions, internal filing records, historical
imports, reconciliation, amendments, bindings, and source-data inventory
separate.

## Live CLI findings

The console entry point is `aeat = "aeat.entrypoints.cli:app"` in
`pyproject.toml:75`.

Live `aeat --help` exposes `version`, `init`, `setup`, `config`, `archive`,
`topic`, `help`, and `app`. This conflicts with the redesigned root contract:
exactly `aeat config` and `aeat app`.

CLI registration confirms the extra roots in
`src/aeat/entrypoints/cli/__init__.py`, with app subcommands mounted around
line 234 and root additions around line 247.

Live `aeat app --help` exposes `overview`, `ledger`, `invoice`,
`declaration`, `modelo`, and `registry`. The app registration is at
`src/aeat/entrypoints/cli/__init__.py:234`.

Live `aeat app modelo --help` exposes only `list`, `describe`, `casillas`,
`bindings`, and `formulas`. The `_modelo.py` module is pure registry query
transport starting around line 42.

`app modelo` commands use `_emit`; `_emit` switches on `ctx.obj["format"]`
in `_common.py:44`.

`aeat filing` is not mounted, but `entrypoints/cli/filing/__init__.py` still
contains `filing build/validate/show/list/import/complementaria build` around
line 351.

## Backend capabilities disconnected from `app modelo`

Lifecycle behavior exists under `app declaration`: `calculate`, `review`,
`status`, `edit`, `approve`, `validate`, `preview`, `export`, and `verify` in
`_declaration.py` around line 125.

Draft construction and validation are in `application.filing.build_draft` and
`validate_draft`. Build uses registry snapshots, casilla inputs, binding
inputs, and `calculate_registry_snapshot` in `application/filing/__init__.py`
around line 96.

Binding input preservation exists for scalar, list, and mapping values in
`application/filing/__init__.py` around line 262.

Export and verify for local AEAT-compatible files exist and keep export
separate from live submission in `application/filing/_export.py`.
`export_draft` requires an approved draft around line 211.

The filing history repository exists in
`application/filing/_history_repository.py` around line 27, but there is no
`app modelo history` verb.

Reconciliation exists as `reconcile(draft, justificante)` in
`application/filing/reconciliation/_reconcile.py` around line 66, but there is
no CLI verb.

Amendment behavior exists only through the unmounted
`filing complementaria build` surface. `build_complementaria` persists
`FilingAmendment` and currently supports only `AmendmentKind.COMPLEMENTARIA`
in `application/filing/_complementaria.py` around line 40.

The workflow engine supports profile -> deadline -> inbox -> draft ->
preflight in `application/workflow/_engine.py` around line 233, but it has no
CLI wiring to `app modelo file`.

The submission engine is read/preflight only and intentionally exposes no
transport method in `domain/submission/_engine.py`.

## Drift and contradictions

`app modelo` currently means registry introspection. Accepted and evolving
ADRs require modelo work units, calculation revisions, verification, internal
filing, filing records, history, import/export, amendments, and
reconciliation.

The code still mounts `setup`, `archive`, `topic`, and `help`, while the bucket
ADR says redesigned UX only exposes `aeat config` and `aeat app`; legacy roots
must be removed.

The code still mounts `aeat app invoice`, while invoice decoupling forbids bare
generic `invoice` UX and requires explicit source kinds.

Current declaration commands mutate `FilingDraftRepository` and
`workflow_state_repository`, but there is no `bucket_id` or bucket event
backend in source.

`app declaration` uses `workflow_state_repository()` through `_state()`, which
matches redesign direction. The unmounted `filing build` command calls
`load_default_filing_profile`, which imports retiring `load_profile_envelope`
in `application/filing/runtime.py` around line 177.

Domain statuses retain `SUBMITTED` for historical and imported records. CLI
copy should prefer "internal filed", "exported", and "imported historical
filing record"; it should avoid "submit".

## Canonical command grammar

Use `amend`, not `complement`. `amend` covers complementaria and future
sustitutiva; the backend currently implements only complementaria, so
`--kind complementaria` is the first supported kind. No `complement` alias.

Use `bindings`, not `inputs`. Registry has first-class binding objects and
current UX already points to `app modelo bindings`; `inputs` is ambiguous with
raw casilla inputs and JSON input files.

Do not place mutating inventory under `app modelo`. Inventory is source-data
management and should live under `app ledger inventory` or a future source-data
ADR. `app modelo bindings` and `app modelo status` may consume
inventory-derived readiness but do not own inventory mutation.

## Suggested canonical tree

- `aeat app modelo list [--modelo] [--year] [--period] [--state draft|verified_complete|filed|superseded]`
- `aeat app modelo create --modelo M --year YYYY --period P [--name TEXT]`
- `aeat app modelo status WORK_UNIT_ID | --modelo M --year YYYY --period P [--revision REV]`
- `aeat app modelo rename WORK_UNIT_ID --name TEXT`
- `aeat app modelo bindings list --modelo M --year YYYY --period P [--missing]`
- `aeat app modelo bindings preview --modelo M --year YYYY --period P [--binding KEY=VALUE]`
- `aeat app modelo calculate WORK_UNIT_ID | --modelo M --year YYYY --period P [--binding KEY=VALUE]`
- `aeat app modelo verify WORK_UNIT_ID [--revision REV]`
- `aeat app modelo file WORK_UNIT_ID [--revision REV] --by ACTOR [--reason TEXT]`
- `aeat app modelo filing-record list|show ...`
- `aeat app modelo export WORK_UNIT_ID --output PATH [--revision REV]`
- `aeat app modelo import --from-justificante PATH | --from-declaracion PATH`
- `aeat app modelo reconcile WORK_UNIT_ID --justificante PATH`
- `aeat app modelo amend WORK_UNIT_ID --kind complementaria --from-filing-record ID --set CASILLA=VALUE [--reason TEXT]`
- `aeat app modelo history --modelo M [--year YYYY] [--period P]`

## Rejected surfaces

Reject `aeat app declaration`. Fold lifecycle commands into `app modelo`.

Reject `aeat app invoice` and bare `invoice` CLI copy. Replace with explicit
source kinds.

Reject `aeat filing *` as an operator root. Salvage backend behavior into
`app modelo`.

Reject `submit`, `presentation`, or `preflight` as standalone modelo verbs.
`preflight` is internal to `verify` and `file` because it implies submission
readiness.

Reject `app modelo help`. Use command help and registry/topic documentation
elsewhere. There is no support-only modelo surface.

Reject `name` alias. Use `rename`.

Reject `compare`. The apex maps comparison needs to `app modelo reconcile`.

## Cross-reference dependencies

Bucket identity and active selection belong to the bucket ADR.

Bucket events and history belong to the bucket-event-history ADR.

Revision immutability belongs to the modelo-calculate-revisions ADR.

`verified_complete` belongs to the verified-complete and modelo-verify ADRs.

The internal filing record object belongs to the modelo-file and
modelo-filing-record ADRs.

Source-kind taxonomy belongs to the invoice-domain-decoupling and
ledger-transaction-management ADRs.

Inventory placement belongs to the inventory-placement ADR. This decision may
reject `app modelo inventory` as a mutating owner but must not decide final
inventory placement.

Live read-only AEAT signals belong to app-live-shape and
app-registry-boundary.

Workflow engine exposure belongs to workflow-engine-harvest.

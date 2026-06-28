---
tags:
  - '#audit'
  - '#cli-persona-testimonials'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - '[[2026-05-20-test-fidelity-sweep-audit]]'
---



# `cli-persona-testimonials` audit: `cli-operator-persona-testimonial-audit`

## Scope


## Findings


## Recommendations



## Context

## Scope

Five sonnet operator-persona agents drove the live `aeat` CLI end-to-end
against isolated storage roots and filed testimonial audits: first-day
newcomer, quarterly-IVA autónomo, multi-profile gestor, annual-Renta
filer, recovery/repair operator. Four returned in full; the Renta
persona ran long under concurrent contention and is not included here.

Findings are deduplicated and severity-ranked. Two positives confirmed:
the no-active-profile landing page is friendly and actionable, and
per-profile SQLite bucket isolation held completely across every
cross-profile probe (no client data leaked).

## CRITICAL

### profile-lifecycle — `logout` then `switch` locks the operator out

`aeat config profile logout` followed by `aeat config profile switch
<name>` — the exact command the tool instructs — fails with a
`NoActiveBucketSessionError` SQLAlchemy traceback ending in "Internal.
The command failed due to an unexpected internal error." `switch` needs
an active bucket session to decrypt, but `logout` removed it: a circular
dead-end with no in-CLI recovery. Remediation: `profile switch` must
operate without a pre-existing session — it is the unlock path.

### workflow — `verify` hard-blocks on `NO_PENDING_OBLIGATION` for fresh profiles

`aeat app modelo work verify <id>` aborts with `final_stage='ABORTED'
reason='NO_PENDING_OBLIGATION'` for any clean-room profile. The implied
create → calculate → verify → file path cannot be completed without an
externally registered filing schedule. Remediation: seed an obligation
on profile creation, let `verify` operate on the calculation revision
directly, or give the error an actionable registration path.

## HIGH

### registry/engine — `decl.ejercicio` / `decl.periodo` resolve to 0 on Modelo 303

Both casillas are `input_kind = "informational"`, `required = true`,
tagged `semantic_role = "filing_year"` / `"filing_period"`. The engine
(`_formula_runtime.py`, `_snapshot.py`) has no handling for those
semantic roles, so a `work calculate` leaves them `0` even though the
work unit carries `filing_year=2025, period=1T`. A 303 filed with
ejercicio/periodo 0 is structurally invalid. Remediation: the engine or
`calculate_modelo_revision` must populate informational casillas from
work-unit metadata via the semantic-role tags. VERIFIED against the 303
registry TOML.

### cli — profile UUID shown where the human name belongs

The welcome screen, `config profile status`, `app overview status`,
`app ledger status`, and the `config repair` header all print the
internal bucket UUID instead of the operator-chosen profile name.
Three personas independently flagged it. Remediation: render
`display_name`; reserve UUIDs for JSON/verbose output.

### cli — `uv sync` / "Venv stale" developer instruction surfaced to operators

`aeat config repair` always emits `warn runtime.dependency_sync / Venv
stale / Siguiente: uv sync`. "venv" and "uv sync" are meaningless to an
autónomo and read as a broken install. A permanent un-actionable warn
trains operators to ignore the repair semaphore. Remediation: suppress
in released builds or replace with an operator-facing action.

### i18n — naked English strings in the Spanish CLI

`tr()` is bypassed at: NIF/NIE/CIF validation (`core/identity/_documents.py`
— "NIF check letter mismatch: expected ..."), ledger-import file-not-found
(`application/ledger/_actions.py` — "The ledger file cannot be imported:
source file does not exist: ..."), period validation (`core/config.py`,
`registry/_queries.py` — "period must be YYYY, YYYYQn, ..."). Operators
hit sudden English in an otherwise-Spanish surface. Remediation: route
through the error-registry `message_key` / `tr()` localisation path.

### cli — internal tr-key leaked as a field label in NIF error

The NIF validation refusal shows `... no válido para
wizard.setup.profile.tax-id.prompt: 12345678A` — a raw translation key
used as the field name. Remediation: resolve the key, or use a
human-facing field label.

### cli — revision identifier undiscoverable; `work create` requires it

`aeat app modelo work create --revision` is required but `--help` gives
no example and no pointer; the value (`2009-y-siguientes`) is only
findable via a separate `modelo describe` / `bindings list` detour. Two
personas hit it. Remediation: name an example in help, surface revision
ids in `modelo list`, or auto-select the sole revision when unambiguous.

### cli — `profile import` rejects a tombstoned profile name; list hides deleted state

After `profile delete <name> --yes`, `profile import` of that name is
refused "ya existe"; `profile list` still shows the deleted profile with
no deleted marker. The export → delete → import recovery path is blocked
on the same machine. Remediation: allow import to replace a tombstoned
profile (with confirmation), and mark deleted profiles in the list.

### cli — `classify` does not echo stored IVA figures

`aeat app ledger classify` with `--taxable-base/--iva-rate/--iva-amount`
confirms only the review status; the operator cannot see whether the IVA
figures were stored. Remediation: echo the stored typed figures.

### cli — `config repair` `secure_state.load fail` shows raw `aeat_database_url` jargon

On a no-profile cold start `repair` reports `fail secure_state.load` with
`StorageError: aeat_database_url is empty` and suggests a destructive
`reset-state --yes` with no data-impact explanation. Remediation: explain
in plain Spanish that this is normal pre-profile, and gate the
destructive suggestion behind a `--dry-run` first.

## MEDIUM

### cli — `work create` silently accepts an invalid revision id

`--revision "bad-revision"` creates a work unit, exit 0, no validation.
Remediation: reject unknown revision ids at create time with the valid
list.

### cli — period format described three inconsistent ways

`modelo describe` shows `1T..4T`, `work create --help` says `Q1, 4T, 0A,
01`, the validation error says `YYYY, YYYYQn, YYYY-Qn, YYYY-MM` (in
English). Remediation: one canonical, localised description.

### cli — `ledger list` and `ledger review` produce identical output

The two verbs imply a workflow distinction the output does not deliver.
Remediation: make `review` a pending-focused workflow view or merge.

### cli — `--format json` is a pre-subcommand global flag, invisible from subcommand help

`aeat app ledger list --format json` fails; only `aeat --format json app
ledger list` works. Two personas mis-placed it. Remediation: document the
global flag in `aeat --help` and reference it from subcommand help.

### cli — `work revisions` takes `--work-unit-id` while sibling verbs take a positional id

`status/history/calculate/verify <id>` are positional; `revisions` alone
needs the flag. Remediation: accept the positional id for consistency.

### cli — `profile logout` gives no warning about in-process session loss

Remediation: emit a line explaining that `switch` (or a new terminal) is
needed to resume.

### cli — `config reset --help` does not say what each `--scope` destroys

`[profile|auth|data|all]` listed without describing the data each erases.
Remediation: one localised line per scope.

### cli — `work list` does not auto-scope to the active profile bucket

Unfiltered `work list` lists across all buckets, surfacing the
`bucket="default"` orphans from the `2026-05-20-test-fidelity-sweep-audit`
sibling bucket-isolation bug. Remediation: default the filter to the
active bucket. Linked to the modelo-work-create bucket bug (task #513).

### cli — `overview status` draft count disagrees with `work list`

`overview status` reports "no drafts" while `work list` shows units —
a downstream effect of work units landing in bucket "default".

## LOW

### cli — `registry inspect` accepts no `--modelo`

Cannot query the registry per modelo from the diagnostics surface.

### cli — "bucket" jargon unexplained in `app --help` and `work create --help`

Cloud-storage term with no operator-facing gloss.

### cli — post-create `next` hint is jargon-only

`next: aeat app modelo work create` with no plain-language context or
example command.

### cli — `profile import --help` does not explain the name comes from the JSON

## Remediation discipline

This document is inventory. Each finding becomes a structural fix paired
with a CLI surface test, or a tracked task. Fixes route operator-facing
text through `tr()`; no naked strings. The `logout`→`switch` lockout and
the `verify` obligation wall are the priority criticals.

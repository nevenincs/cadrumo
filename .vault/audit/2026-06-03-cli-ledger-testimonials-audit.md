---
tags:
  - '#audit'
  - '#cli-ledger-testimonials'
date: '2026-06-03'
modified: '2026-06-03'
related: []
---



# `cli-ledger-testimonials` audit: `CLI ledger-operator persona testimonials — graded findings + hardening`

## Scope

Six taxpayer-operator personas — core (happy-path), cross-year (continuity),
messy (lifecycle/corrections), foreign (multicurrency), skeptic (safety/legal),
and newcomer (zero-knowledge discoverability) — operated the real `aeat` CLI
black-box (`uv run aeat ...` + `--help` only, isolated scratch storage roots,
`AEAT_LIVE_TESTS_ENABLED=0`) against the hand-authored ledger-corpus fixture
(Marta Ríos Velasco, autónoma in estimación directa simplificada / IVA general,
514 transactions, four multicurrency bank accounts, cross-year 2025 → 2026 H1).
The goal was to perform end-to-end cross-period filing from ledger + profile
data (import → classify → calculate → verify → file/export) and grade the
operator experience.

Per the swarm-audit verify-before-action discipline, every reported BLOCKER was
re-reproduced by the coordinator against HEAD before being actioned; three
reported BLOCKERs proved to be transient peer-WIP and were screened out rather
than chased (see Transient section). Severity grades are the personas' own
(BLOCKER / MAJOR / MINOR / COSMETIC), reconciled across personas.

## Findings

### Verdict

A real operator **cannot complete the CLI's own signposted path**
(`ledger import` → `classify` → `modelo work file`) — it is severed by
confirmed BLOCKERs. However, the cross-period filing *goal is achievable* via
the manual `--binding`/`--casilla` → `calculate` → `verify` → `export` path:
the newcomer persona reached fichero-BOE output for Modelo 130 1T and 2T 2025.
The safety bones are sound (FX normalization correct; `calculate` fail-safe
blocks unclassified income rather than emitting a silent zero; `verify` surfaces
missing casillas with legal_refs; `file` and `runs` state plainly they never
contact AEAT).

### BLOCKER — confirmed at HEAD

- **B1 — single-transaction read-model rejects persisted FX fields.** The
  importer persists `value_in_eur` and `fx_rate` on every row, but the CLI-side
  `TransactionPayload` (a strict `extra="forbid"` output schema behind
  `ledger view`, `classify --id`, `update`, `archive`, `stash`) omitted them, so
  every single-transaction read raised `ValidationError(extra_forbidden)` — even
  on EUR rows where the values are null. The whole correction/classification
  surface was dead, which cascaded to block `preflight` → `calculate`. Reproduced
  by the coordinator and four personas. **RESOLVED** (the payload now declares
  both as typed optional fields, `extra="forbid"` kept; roundtrip test with a
  proven anti-tautology; gate PASSED).
- **B2 — "Refused" commands persist partial corrupting writes.** Personas saw a
  failed `update` leave a row flipped to MIXED/ARCHIVED with a renamed id, and
  lifecycle counts appear from commands that reported failure. **RESOLVED /
  moot:** the symptom was B1's post-mutation read-model crash; an exhaustive
  review of all 13 mutation save-sites confirmed every one routes through a
  single batched atomic save helper (validate-then-build-then-save ordering), so
  a refused command cannot reach a write — structurally impossible.
- **B3 — Modelo 303 calculate dead-ends on IVA-wallet seed circularity.** Past
  classification, `calculate` demands a persisted reconciliation *decision* from
  a different repository than the one `iva-wallet seed` writes to; `seed` reports
  success but produces no decision and `iva-wallet balance` shows `lot_count 0`,
  and the refusal points back at `seed` — a circular dead-end. **IN PROGRESS:**
  fix adjudicated calculate-side (auto-derive the non-blocked local-authority
  decision when none exists and no live wallet is configured, surfacing the carry
  as the casilla 110 "Cuotas a compensar de periodos anteriores" observation with
  legal_refs — never a silent zero), plus the `lot_count` carry-forward gap.

### REGRESSION — confirmed real at HEAD (sequential), absorbed in-scope

- **~55 ledger/modelo CLI tests fail with "No active bucket session is open."**
  The active bucket session is a per-process/per-context var opened per command
  bootstrap; the real CLI re-opens it each process, but the older in-process
  CliRunner fixtures (`_create_profile_and_import`-style) invoke `profile create`
  then `ledger import` in one process, where the bare create invoke opens and
  closes its own session so the import finds none. The newer fixtures hold the
  session open via the `profile_create_storage_span` contextmanager and pass.
  Root cause = **stale fixtures, product is sound** (three-way subprocess proof).
  **IN PROGRESS:** migrate the stale fixtures to the span pattern (no product
  change).

### MAJOR

- **No bulk path supplies IVA facts.** `classify --from-csv` sets only
  classification/category, never `taxable_base`/`iva_rate`/`iva_amount`, which
  `preflight` then mandates per BUSINESS row — so even with B1 fixed there is no
  scalable way to ready a 514-row ledger for a real 303.
- **`config repair` is a no-op recovery dead-end.** Every read-model refusal
  suggested "Run `aeat config repair`"; repair reports all-OK and changes
  nothing. (Largely mitigated now B1's crash is gone, but the pattern of pointing
  at a no-op recovery remains.)
- **`ledger list` has zero filters** (no period/year/direction/classification/
  account/limit) — operators dumped ~16k JSON lines and grepped.
- **devengo-vs-caja silently bucketed by payment date.** The ledger keys on
  payment (caja) date with no devengo field or straddle warning; a 2025-12-raised
  / 2026-01-paid invoice lands in 2026 — an IRPF correctness risk for estimación
  directa. (Hardening in the journey-suite + a basis test.)
- **`modelo work file` NO_PENDING_OBLIGATION is undiscoverable.** A
  verified-complete revision cannot be filed and nothing signposts how; `readiness`
  reports ready while `file` refuses (apparent contradiction). Investigation: filing
  obligations are calendar-derived (not operator-creatable) and `export` is the real
  local finish line — so the fix is to make the refusal instructive and reconcile the
  readiness/file labels. **IN PROGRESS.**
- **The working path is invisible.** Nothing tells the operator they can
  hand-enter bindings when import/classify is unavailable, nor that `export`
  (not `file`) is the local finish line.

### MINOR / COSMETIC

Inconsistent id arguments (`calculate` takes the work-unit id; `verify`/`file`/
`export` take the calculation-revision id, both 64-char, no hint); `modelo
describe` and `ledger preflight` absent from top-level `--help` though referenced
by subcommand help; period-token inconsistency (`1T` for `work create` vs
`2025Q1`/`2026-03` elsewhere); `export` runs full-registry validation so an
unrelated in-flight modelo can block exporting another; profile `output_language`
ignored `AEAT_OUTPUT_LANGUAGE=en`; stray `%` in a not-found error; `bindings list
--missing` returns the unfiltered count; `profile create --help` is an ~80-flag
wall with no minimal-profile hint.

### TRANSIENT peer-WIP — verified RESOLVED at HEAD, not actioned

- **`ledger import` traceback** (`ModuleNotFoundError: aeat.adapters.core` in the
  ECB FX provider + a `_parse_iso8601_date` NameError) reported by the newcomer
  during a long run mid-relocation. At HEAD the provider uses absolute imports and
  imports of all four corpus files succeed — a peer fixed it mid-flight.
- **Registry global-validation abort** on a malformed modelo reddening the whole
  authority, and a `pyproject.toml` duplicate key breaking `uv run`: both the
  known loader-cache / peer-WIP races that clear on re-run; verified clean at HEAD.

### Positives (regression-guard)

FX/multicurrency normalization (GBP/USD → EUR with stored rate, no
`UNSUPPORTED_CURRENCY`); `calculate` auto-aggregates the ledger and fail-safe
blocks unclassified income (no silent zero); `verify` surfaces missing casillas
with legal_refs; `export` works on a verified-complete revision; `verify`/`file`
require a real calculation-revision id (no filing an empty draft); destructive
ledger ops gate on `--yes`; category validation is instructive; the late-period
recargo (Art. 27 LGT) warning; error-message "Did you mean …" remediation.

## Recommendations

- **Hardening already dispatched (one fix per finding, each behind the
  code-review gate):** B1 round-trip (landed, gate PASSED); B3 calculate-side
  lazy-reconcile with the non-silent casilla-110 guardrail (in progress); the
  bucket-session fixture migration (in progress); the journey-suite lifecycle
  post-state assertions + a devengo-vs-caja basis test (in progress); the
  `file` NO_PENDING_OBLIGATION discoverability + readiness reconciliation (in
  progress).
- **Next wave (held to avoid hot-file collision while the above land):** add a
  bulk path that supplies IVA facts (`taxable_base`/`iva_rate`/`iva_amount`),
  not just classification/category; add filters to `ledger list`; make
  `config repair` either fix or honestly disclaim the read-model class of
  failure rather than no-op; surface the working manual-binding → `export`
  finish line; the MINOR/COSMETIC batch (id-argument hint, `--help`
  completeness, period-token consistency, locale honouring).
- **Close the still-open items with a post-fix persona re-run** once B3 and the
  bulk-facts path land: whether a *calculated* return with positive income but
  zero cuota passes `verify` silently (the skeptic could not reach it); whether
  intracom/export/import/reverse-charge route to the correct Modelo 303
  casillas and the recargo-equivalencia anomaly is surfaced (the foreign persona
  could not reach calculate); whether prior-year `previous_filing` bindings
  actually carry across a real filed prior period (the cross-year persona could
  not file one).
- **Keep verify-before-action mandatory.** Three of the reported BLOCKERs were
  transient peer-WIP; re-reproducing each against HEAD before assigning a fix
  prevented chasing ghosts and is the single highest-leverage discipline in this
  fast-landing shared worktree.

## Codification candidates


Two candidates meet the bar (cross-session, constraint-shaped, project-bound).
Per the codify discipline they are recorded here for evaluation at campaign
close, not authored mid-campaign:

- **Source:** finding B1 (CLI `TransactionPayload` with `extra="forbid"` omitted
  persisted `value_in_eur`/`fx_rate`, breaking every single-record read).
  **Rule slug:** `cli-output-payload-mirrors-persisted-record`.
  **Rule:** a strict (`extra="forbid"`) CLI output payload that mirrors a
  persisted record MUST declare every field that record can carry, and a
  single-record-read round-trip test MUST exercise it with non-default values —
  the CLI-presentation sibling of the persistence-boundary roundtrip discipline,
  which it is not currently covered by.

- **Source:** finding #52 (older in-process CliRunner fixtures fail "No active
  bucket session is open" because a bare `profile create` invoke opens and closes
  its own session).
  **Rule slug:** `cli-runner-tests-hold-bucket-session-span`.
  **Rule:** an in-process CliRunner test that spans more than one profile-bound
  command MUST hold the bucket session open across invokes via the
  `profile_create_storage_span` contextmanager (the real CLI re-opens the session
  per process; a multi-invoke in-process test does not).

The verify-before-action lesson (three transient peer-WIP BLOCKERs screened out
against HEAD) is already covered by the existing recheck-HEAD coordination rule;
no new rule needed there.

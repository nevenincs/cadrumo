---
tags:
  - '#research'
  - '#m036-lifecycle-verbs'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
---

# `m036-lifecycle-verbs` research: `M036 declarative-recording verb design (S2349)`

Subagent ground-truth pass for #629 W85.P414.S2349 — register
Modelo 036 lifecycle verbs (alta / modificacion / baja) under
`aeat app modelo`. The 2026-06-03 R-row refresh audit confirmed
these verbs are absent.

## Critical decoupling from the ADR amendment

The 2026-05-16 ADR amendment is explicit: **036 is a live-synced
census-data store, not a filing-lifecycle modelo. The CLI surface
lives under `aeat config profile censo`.** That decision shipped:
the four-verb censo subgroup is live.

So what does S2349 actually mean? Two readings:

1. **Declarative-record verbs**: record the operator's declaration
   that they filed an alta/modificacion/baja with AEAT (an
   audit-trail event, not a filing action). AEAT is the
   authority; the operator files at sede; the local app records
   that the declaration happened so downstream profile state and
   stale-cascade logic can react.

2. **Lifecycle work-units**: treat alta/modificacion/baja as
   `work_unit` periods that the engine processes. This
   contradicts the ADR amendment's "the local app never files a
   036" lock.

**Reading 1 is mandated by the ADR.** The audit's "CLI verbs
absent" finding is accurate but the verbs must be *declarative
recording verbs*, not filing verbs.

## Current state

### Registry

Standardised in directory-mode by #637 (plan
`2026-05-27-schema-hardening-m036-standardization-plan.md`, all 4
Steps done). Manifest declares `tax_domain = "censo"`,
`cadence = "ad_hoc"`. One revision
`2025-02-03-y-siguientes` whose `period_selector.periods =
["alta", "modificacion", "baja"]` — these are the AEAT-side event
kinds, not period tokens in the calendar sense. The
schema-hardening work shipped structure standardisation only (no
behavioural changes). It did NOT ship CLI verbs.

### Domain foundation

`src/aeat/domain/calculations/registry/_censo_modelos.py` already
defines `CensoModeloEventKind {ALTA, MODIFICACION, BAJA}`,
`CENSO_MODELO_EVENT_KINDS = ("alta", "modificacion", "baja")`,
`CensoModeloFoundationContract`, and the active/historical routing
for 036/037. Backend-owned contract referenced in the ADR's
"backend-boundary stays intact" lock.

### Application service

`aeat.application.live._censo.CensoSyncService` already exists for
the live-read mirror surface (G313 Mis Datos Censales). That
service backs `aeat config profile censo {refresh, show, compare,
apply}`. **No `alta/modificacion/baja` declaration-action service
exists** — only the read/mirror surface.

### CLI

`_modelo.py` mounts `work_app`, `bindings_app`,
`filing_record_app`, `verification_report_app`, `audit_app`,
`iva_wallet_app`. **No M036-specific verb tree exists.**
`_resolve_year_period` already short-circuits censo event tokens
("alta", "modificacion", "baja") to the registry, so `work create
--modelo 036 --period alta` would technically resolve — but no
enforcement of the ADR's mandate that 036 is NOT a filing-lifecycle
modelo (the local app never files it; the operator files at sede).

## Recommended mounting

`aeat app modelo m036 {alta, modificacion, baja}` — a dedicated
`m036` subgroup under `aeat app modelo` (not under `work_app`,
which carries `create/calculate/verify/file/amend` filing-lifecycle
semantics that the ADR forbids for 036). Mount via a new
`m036_app = typer.Typer(name="m036", ...)` registered with
`app.add_typer(m036_app, name="m036")` at the end of `_modelo.py`.

The `aeat app m036 ...` top-level shape is NOT recommended —
`aeat-architecture-boundaries` caps the CLI root at `config` +
`app` and discourages a third family; `m036` belongs under the
`modelo` subgroup.

## Backend service signatures

New module `src/aeat/application/modelo/_m036_lifecycle.py`:

- `class M036DeclarationCommand(BaseModel)`: profile_id, event_kind
  (CensoModeloEventKind), declared_on (date — when operator filed
  at sede), sede_justificante (optional AEAT acuse de recibo),
  note.
- `class M036DeclarationResult(BaseModel)`: declaration_id
  (SHA-256 content-addressed), event_kind, declared_on,
  recorded_at, bucket_event_id.
- `class M036DeclarationService`:
  - `record_alta(cmd) -> M036DeclarationResult`
  - `record_modificacion(cmd) -> M036DeclarationResult`
  - `record_baja(cmd) -> M036DeclarationResult`
  - `list_declarations(profile_id) -> tuple[...]`

Persistence: a new `LIVE_M036_DECLARATION_NAMESPACE` at PII
sensitivity (parallel shape to `LIVE_CENSO_SNAPSHOT_NAMESPACE`).

## New BucketEventType members

Add to `src/aeat/domain/buckets/_event.py`:

- `CENSO_DECLARATION_ALTA = "modelo.036.declaration.alta"`
- `CENSO_DECLARATION_MODIFICACION = "modelo.036.declaration.modificacion"`
- `CENSO_DECLARATION_BAJA = "modelo.036.declaration.baja"`

Keeping the `modelo.036.declaration.*` prefix distinguishes them
from the existing `profile.censo.refreshed/applied` mirror events.

## Service-contract test plan (5-7)

Under `src/aeat/application/modelo/test_m036_lifecycle.py`:

1. `test_record_alta_persists_declaration` — round-trip through
   SecureObjectRepository, strict pydantic equality.
2. `test_record_alta_emits_censo_declaration_alta_event` — event
   appears in history catalogue.
3. `test_record_modificacion_requires_prior_alta` — refuse if no
   ACTIVE alta declaration exists.
4. `test_record_baja_requires_prior_alta` — same.
5. `test_record_baja_after_baja_refused` — closed-state refusal.
6. `test_declaration_id_is_content_addressed` — SHA-256 derivation
   stable.
7. `test_list_declarations_orders_by_declared_on` — chronological
   surface.

## CLI test plan (3-4)

Under `src/aeat/entrypoints/cli/test_m036_lifecycle_verbs.py`:

1. `test_m036_alta_records_and_emits_event` — CliRunner end-to-end.
2. `test_m036_modificacion_refuses_without_prior_alta` — typed
   refusal text.
3. `test_m036_baja_emits_censo_declaration_baja_event` — payload +
   text format.
4. `test_m036_no_active_profile_refused_cleanly` — cold-start
   guard.

## Peer-WIP risk

`_modelo.py` and `domain/buckets/_event.py` were peer-clean at
research time. Safe to land additions at the bottom of `_modelo.py`
following the existing lazy-load subapp pattern; add a fresh
`m036_app` Typer with its own command bodies — do NOT modify
`work_app` or `_guard_stub_modelo`.

`_config/__init__.py` carries unrelated peer WIP at research time;
the M036 mount does NOT touch that file.

## Authoring atomicity

The full landing is multi-commit per the relocation-atomicity
discipline:

- Commit 1: BucketEventType additions + value-equality test
  (preconditions).
- Commit 2: M036DeclarationCommand / Result + service module +
  7 service-contract tests.
- Commit 3: CLI verb mount + 4 CLI tests.

Each commit ships its tests; no commit lands without operational
behaviour.

## Source

Subagent ground-truth discovery 2026-06-03 against #629
W85.P414.S2349. Cited file:line evidence:
- `.vault/adr/2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr.md`
  + 2026-05-16 amendment
- `src/aeat/_data/registry/aeat/modelos/036/manifest.toml`
- `src/aeat/_data/registry/aeat/modelos/036/revisions/2025-02-03-y-siguientes/revision.toml`
- `src/aeat/domain/calculations/registry/_censo_modelos.py`
- `src/aeat/application/live/_censo.py`
- `src/aeat/entrypoints/cli/_config/_profile_censo.py` (existing
  read/mirror CLI — pattern to follow)
- `src/aeat/entrypoints/cli/_modelo.py` (mount target)
- `src/aeat/domain/buckets/_event.py` (add 3 BucketEventType
  members)

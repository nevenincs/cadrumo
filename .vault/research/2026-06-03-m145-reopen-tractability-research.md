---
tags:
  - '#research'
  - '#m145-reopen-tractability'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
  - "[[2026-06-03-m036-lifecycle-verbs-research]]"
---

# `m145-reopen-tractability` research: `M145 reopen plan tractability + 3-commit landing sequence`

Subagent ground-truth pass for #638 modelo-145-reopen (23 open
Steps). M145 is a local payer-communication (operator gives the
record to the payer; never filed at AEAT), NOT a filing modelo.
Strong cross-reference with the M036 declarative-recording
pattern landed in commits 013754745 + 3a23e7eb1.

## Open Steps tractability (23)

### P03 — registry TOML (5, sequential within phase)

- `P03.S11` registry TOML scaffold — ready; pattern is M111
  manifest+revisions/ pared down (no
  filing_schedules/deadline_windows/application_links subdirs).
- `P03.S12` lifecycle modelling as payer-communication — ready
  (schema vocabulary already accepts `"communication"` and
  `"payer_delivery"` surfaces per `_schema.py:1143-44`;
  P02.S07-S10 already shipped vocabulary).
- `P03.S13` export layout from `aeat-dr-145-v20` — ready, source
  already catalogued.
- `P03.S14` exclusion negative-assertion — multi-turn (must
  enumerate every excluded surface).
- `P03.S15` verification test — ready.

### P04 — backend service (7, sequential)

All ready; greenfield `_m145_communication.py` module. No
blockers.

### P05 — thin CLI (5, sequential)

All ready once P04 lands. S27 (help-text vocabulary scan) is a
negative test, low effort.

### P06 — verification (6, sequential)

All ready post-P05. S32 (036/037 unaffected) is a cross-touch
regression check, low risk because no shared surface. S33 is the
suite gate.

## Registry kind decision

Author as a **modelo** (i.e., `src/aeat/_data/registry/aeat/modelos/145/`),
not a new top-level document kind. ADR §Implementation explicitly
mandates `registry/aeat/modelos/145.toml`. The schema already
extended its `application_links.surface` Literal with
`"communication"` and `"payer_delivery"` in P02; no new top-level
discriminator is required. The "non-filing" nature is enforced by
**absence** of filing_schedules/deadline_windows/live_cross_references
subdirs, not by a new file type.

Set `tax_domain = "irpf"` (Modelo 145 is IRPF retención support
data), `cadence = "ad_hoc"` (operator initiates whenever they
need to communicate to a new payer or update existing data).

## Pydantic command/result shapes

```
class M145CommunicationCommand(BaseModel):
    profile_id: ProfileId
    payer_nif: str  # NIF of the payer (employer/retainer)
    situacion_familiar: SituacionFamiliarKind
    descendientes: tuple[DescendienteEntry, ...]
    ascendientes: tuple[AscendienteEntry, ...]
    discapacidad: DiscapacidadKind | None
    movilidad_geografica: bool
    pension_compensatoria: Decimal | None
    pagos_prestamo_vivienda: bool
    note: str = ""

class M145CommunicationResult(BaseModel):
    communication_id: str  # SHA-256 content-addressed
    payer_nif: str
    created_at: datetime
    state: M145CommunicationState
    bucket_event_id: str

class M145ExportResult(BaseModel):
    communication_id: str
    layout_revision: str  # "dr-145-v20"
    bytes_path: Path
    sha256: str
```

Service `M145CommunicationService` with `create`, `validate`,
`export`, `mark_delivered_to_payer`, `mark_locally_completed`,
`list_communications(profile_id)`. New PII-sensitivity namespace
`LIVE_M145_COMMUNICATION_NAMESPACE`. New BucketEventType members
`M145_COMMUNICATION_{CREATED, VALIDATED, EXPORTED,
DELIVERED_TO_PAYER, LOCALLY_COMPLETED}` keyed
`"modelo.145.communication.*"`.

## CLI verb tree

**Recommended:** `aeat app modelo m145 {create, validate, export,
mark-delivered, mark-completed, list}` — dedicated
`m145_app = typer.Typer(...)` mounted at the bottom of
`_modelo.py`, mirroring the M036 pattern
(2026-06-03-m036-lifecycle-verbs-research lines 86-97).

**Do NOT** mount under `work_app` — that subgroup carries
`create/calculate/verify/file/amend` filing semantics the ADR
explicitly forbids (no `file` verb anywhere). **Do NOT** add an
`aeat app payer-communication` root — `aeat-architecture-boundaries`
caps CLI roots at `config`+`app`. The `modelo m145` location
reuses the modelo subgroup without inheriting work_app semantics.

## Cross-references with M036 declarative-recording pattern

Strong parallels: greenfield service module under
`application/modelo/`, content-addressed result ID, new namespace
at PII sensitivity, dedicated typer mount at bottom of `_modelo.py`,
BucketEventType additions with domain-prefixed values, sequential
service-then-CLI commit ordering.

**Key difference:** M036 verbs are *declarative recording* of
AEAT-side events (operator filed at sede; app records the
assertion). M145 verbs are *actual local-side actions* — the app
produces the export artefact the payer receives. So M145 needs a
real `export` verb producing fichero bytes (anchored to
`dr-145-v20` record design), whereas M036 has no export — only
declaration recording.

## Peer-WIP risk

- `src/aeat/entrypoints/cli/_modelo.py` — last commit `7558800b1`
  (M036 verb mount, same pattern). Currently peer-clean per
  `git status` summary. LOW risk if landing additions follow the
  bottom-of-file lazy-mount pattern, untouching `work_app` /
  `_guard_stub_modelo`.
- `src/aeat/application/modelo/test_export.py` — has 232-line
  uncommitted peer WIP. DO NOT modify this file; new M145 tests
  go in `test_m145_communication.py`.
- `src/aeat/_data/registry/aeat/modelos/145/` — absent. NO risk.
- `_schema.py:1143-44` already carries `communication` /
  `payer_delivery` literals from P02 — NO schema edits needed
  in this campaign.

## 3-commit atomic landing sequence

1. **P03 registry + tests (S11-S15)**: create
   `modelos/145/manifest.toml` + `revisions/2011-y-siguientes/
   {revision.toml, casillas/, export/, extraction_profiles/}` +
   `test_modelo_145_registry.py`. Land all P03 Steps as one
   commit; discrete authority surface; loader gate runs at
   collection.
2. **P04 backend service + tests (S16-S22, S28)**: add
   `_m145_communication.py` with command/result/service + new
   BucketEventType members + new namespace +
   `test_m145_communication.py` (real SecureObjectRepository
   round-trip per `aeat-roundtrip-discipline`). One commit.
3. **P05 CLI mount + P06 verification (S23-S27, S29-S33)**: add
   `m145_app` typer subgroup mount in `_modelo.py` +
   `test_m145_lifecycle_verbs.py` + negative-surface tests +
   suite-slice run. One commit.

Each commit ships its own real-behaviour tests; no commit lands
inert structure. Run `uv run --no-sync pytest --collect-only -q`
immediately before each commit.

## Source

Subagent ground-truth discovery 2026-06-03 against #638
modelo-145-reopen plan. Cited file:line evidence:

- `src/aeat/_data/registry/aeat/modelos/145/` (absent)
- `src/aeat/application/modelo/_schema.py:1143-44`
  (communication / payer_delivery literals)
- `src/aeat/entrypoints/cli/_modelo.py` (peer-clean mount target)
- `src/aeat/application/modelo/test_export.py` (232-line peer WIP
  — DO NOT TOUCH)
- `2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan.md`
  (the 23-step plan)
- `2026-05-12-cli-workflow-redesign-modelo-145-foundation-adr.md`
  (companion ADR)
- `2026-06-03-m036-lifecycle-verbs-research.md` (cross-reference
  pattern)

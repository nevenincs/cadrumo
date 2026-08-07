---
tags:
  - '#adr'
  - '#aeat-liabilities-sanciones'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:df292b7c71ed118d9982f0a14a8040fcb438436e8906db515a76a6d9e690489b'
related:
  - '[[2026-08-07-aeat-liabilities-sanciones-research]]'
---

# `aeat-liabilities-sanciones` adr: `Deudas y sanciones: read-only liability register, never a calculation input` | (**status:** `accepted`)

## Problem Statement

A taxpayer's AEAT-owed liabilities — sanciones, recargo de apremio, intereses
de demora, liquidaciones from a comprobación, and aplazamiento/fraccionamiento
in force — have no typed representation anywhere in this application. The only
existing surface, `PostFilingEventKind`, tags pulled notification rows by
concepto substring and carries no amount, no deadline, and no procedural
state. An operator who wants to know what AEAT currently believes is owed has
nowhere to look inside the app. This record decides how to close that gap: what
gets built, what stays deliberately out of scope, and how the read surface is
kept safe given its direct adjacency to AEAT's payment flow.

## Considerations

- Interés de demora and recargo de apremio are *consequences* of the
  taxpayer's own liability, never inputs to any modelo casilla — no
  calculation-grounding, aggregation, binding, or resolver machinery is
  triggered by a read-and-display record of these objects, per
  `2026-08-07-aeat-liabilities-sanciones-research` ("Decisive answer: an
  AEAT-imposed sanción, recargo de apremio or AEAT-determined interés de
  demora never reaches a modelo casilla — this is purely read-and-display").
- The registry already carries a casilla-level "Intereses de demora" concept
  that must never be confused with this gap. M100 casilla `0576`
  (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/c0576.toml`,
  `legal_refs` citing `ley-58-2003:art-26`) is the taxpayer
  **self-computing** an interés de demora while voluntarily regularising a
  previously-claimed tax benefit within the SAME declaration under LGT art.
  26.5 — a value the formula engine derives from the taxpayer's own prior
  figures, never a value AEAT hands back to the app. An AEAT-assessed interés
  de demora (art. 26.2.a/d), surfaced through "Consultar deudas", is a
  categorically different data flow: an administrative act happening to a
  filing that already exists, not an input to a future one. No `casilla`
  anywhere in the registry accepts "amount AEAT says I owe" as an input, and
  `BindingSourceKind` has no member referencing any post-filing enforcement
  concept (research, "Decisive answer..."). This is the worked counter-example
  a future contributor must not miss: casilla `0576` looks, at a glance, like
  exactly the box an AEAT-reported interés de demora should feed. It is not.
- AEAT's "Consultar deudas" surface is a genuine read-only consulta, structurally
  and procedurally distinct from payment: viewing the debts list and choosing
  to pay are different trámites with different apoderamiento codes, mirroring
  the separation the app already trusts between `Consultar declaraciones
  presentadas` and the payment-adjacent branches of `Mis Expedientes`
  (research, "AEAT exposes a genuine read-only Consultar deudas surface").
  Payment, aplazamiento requests and any other mutating AEAT action stay
  categorically out of reach of this application, per the sensitive-financial-
  data rule's never-file mandate.
- No AEAT specimen of the debts-consulta page exists yet — no URL, no ZK/AJAX
  form structure, no known DOM identifiers. The research explicitly could not
  investigate this without a live authenticated probe, which is not authorized
  by this record (research, "Not investigated").
- Five of seven relevant LGT provisions are absent from the bundled corpus:
  art. 28 (recargo de apremio), arts. 65/82 (aplazamiento/fraccionamiento),
  arts. 163/167-173 (procedimiento de apremio) and arts. 178-212 (régimen
  sancionador). Only art. 26 (interés de demora) and art. 27 (recargo
  extemporáneo, already built and grounded elsewhere) are bundled today.
  `aeat-calculation-grounding` forbids shipping any figure whose establishing
  provision is not defined in the legal catalogue with a `corpus_ref`
  resolving to real, live-cross-checked BOE text, and forbids an agent
  stamping a legal entry as reviewed.
- The sibling to mirror structurally is `ExpedientesService` /
  `PersistedExpedientesSnapshot` (`src/cadrumo/application/live/_expedientes.py`):
  a `mode: Literal["read"]` structural marker, a `StatelessSnapshotService`
  over `SecureSnapshotRepository`, a bucket-scoped namespace constant, and an
  `assert_read_landing` guard pinned to an allowed path-prefix tuple
  (`src/cadrumo/adapters/outbound/aeat/sede/_walker.py:109-134`). The censal
  reader's `_assert_read_landing` (`src/cadrumo/adapters/outbound/aeat/sede/
  _censal_datos.py:791`) is the sharper worked example: it refuses at runtime
  the moment AEAT lands the session on *Cambio de Domicilio Fiscal*, an M036
  filing tool, or any other modification launcher one control away from the
  consulta page — the exact adjacency this feature's debts-consulta page has to
  "pagar todas mis deudas" / "pagar algunas deudas" / aplazamiento requests.
- `PostFilingEventKind` classifies a *notification event stream*; a debts-
  consulta row is a *standing liability with an amount and a procedural
  state*. These are different entities with different identity, source
  surface and lifecycle — an `ACUERDO_SANCION`-classified notification
  announces a sanción, a debts-consulta row is the sanción's resulting deuda,
  if and once liquidated (research, "Concrete typed-record shape, owning
  packages, and CLI surface — actionable for the ADR"). Conflating them is
  exactly the cross-concept collision `aeat-architecture-boundaries` forbids
  for the reserved term "binding", generalised: two concepts, one type.
- Every profile-bound write path — including a read verb that persists a
  captured snapshot to bucket storage, such as the existing `app live
  expedientes pull` and `app live iva-wallet pull` entries — is hand-enrolled
  in `PROFILE_BOUND_WRITE_VERB_PATHS`
  (`src/cadrumo/application/storage_write_policy.py:122-265`). An unenrolled
  new leaf silently bypasses the profile-bound write guard (`aeat-cli-contract`).
- An informational register that silently omits a liability leaves the
  taxpayer unaware of a debt accruing recargo de apremio — the same failure
  class as a silent under-declaration, just pointed at an omission rather than
  a miscalculation (`no-silent-under-declaration`).
- The locale catalogues currently carry uncommitted peer WIP on `en.yml` and a
  partially staged `hu.yml`; any new locale key for this feature is blocked
  until that WIP lands, per the worktree-safety rule's prohibition on touching
  a file a peer is mid-write on.

## Considered options

1. **Minimal read-and-display inventory (chosen).** New `deudas` adapter under
   `src/cadrumo/adapters/outbound/aeat/sede/`, mirroring the declarations-
   register / expedientes read-guard pattern, plus a new `DeudasService`
   snapshot family mirroring `ExpedientesService` exactly. Persists typed
   `Deuda` rows (clave de liquidación, objeto tributario, importe, período,
   situación, classified LGT category) read-only, surfaced through a new CLI
   read verb. No divergence logic, no calculation coupling, no write path.
   Smallest, most self-contained; ships operator value without touching any
   calculation-grounding machinery. **Kept**: the research's evidence supports
   it directly, and it is the only option whose full scope is buildable
   without a live specimen or new legal grounding for every field.
2. **Full reconciliation with divergence decisions**, cloning the IVA-wallet /
   `apply_cotejo` shape: snapshot the AEAT debts list, compare against the
   app's own filed-declaration resultados, and persist a divergence decision
   when AEAT's recorded deuda diverges from what the app expects. **Rejected
   for this record, named as a future extension**: it needs a comparison
   authority analogous to `reconcile_iva_compensation_wallet`, a decision
   repository, and a strictly advisory-only gate per
   `aeat-calculation-aggregation` — substantially more surface than a first
   cut can responsibly ground, and it presupposes option 1's read surface
   plus a real specimen to validate the comparison against, neither of which
   exists yet.
3. **Extend `PostFilingEventKind` in place**, adding amount/deadline fields to
   the existing enum's carrying row type. **Rejected**: the enum classifies an
   event stream, not a standing liability register; a debts-consulta row has
   no natural event timestamp, and conflating the two entities is the exact
   shape `aeat-architecture-boundaries` forbids. Not viable on the evidence
   gathered (research, "Options").

## Constraints

- **Specimen-blocked:** the exact URL, ZK/AJAX form structure and trámite
  gating of "Consultar deudas" is unknown. The read-landing guard's allowed
  path-prefix tuple, and any DOM-parsing adapter function, cannot be written
  against a real page until an operator authorises a live authenticated probe
  and captures a specimen (still not authorized by this record). Everything
  downstream of the adapter's actual HTTP parse function is buildable and
  testable now against a synthetic fixture; the parse function's field mapping
  is not.
- **Grounding-blocked:** any classification or interpretation this register
  adds under a legal category (a sanción percentage band under arts. 191-197,
  a recargo de apremio percentage under art. 28, an aplazamiento interest rate
  under arts. 65/82) needs its establishing provision defined in the legal
  catalogue with a `corpus_ref` resolving to the live-cross-checked BOE text,
  authored and reviewed by a named human owner per
  `aeat-calculation-grounding`. The register can display AEAT's own reported
  `importe` and `situación` string without new grounding work — those are
  AEAT's own figures, not values this app asserts under a legal provision —
  but any label or derived interpretation the app adds on top needs it.
- **Peer-WIP-blocked:** new locale keys for this feature cannot be authored
  until the in-flight `en.yml`/`hu.yml` peer WIP lands; per
  `aeat-locales-cli`, `scaffold` then `scaffold --check` must run clean before
  any `set` for this feature's keys.
- **Never-file, always:** no code path introduced by this record may submit,
  pay, acknowledge, or otherwise mutate AEAT state. The read-landing guard is
  the runtime wall; it must exist before any adapter function that fetches
  live HTML is merged, not after.

## Implementation

The register is layered so the buildable-now work is fully separable from the
specimen- and grounding-blocked work; the plan document splits these into
distinct, independently verifiable rows.

**Naming.** The Spanish stems `deuda`, `sancion`, `apremio`, `aplazamiento`
follow `aeat-naming` directly — these are AEAT-surface concepts with 1:1
Spanish mappings, exactly the category the rule reserves Spanish for. The
`notificaciones` family's English CLI naming is the pre-rule exception the
rule already carves out ("Already-public pre-rule identifiers keep their
names"); this record does not retroactively rename it, and does not treat it
as license to name a new family in English.

**Domain type (unblocked today).** A `Deuda` pydantic model in a new adapter
schema module, mirroring `Expediente`'s placement
(`src/cadrumo/adapters/outbound/aeat/sede/_schema.py`), carries:
`clave_liquidacion` (validated identifier), a closed `ObjetoTributario`
StrEnum declared in `core/` (interés de demora / recargo de apremio / sanción /
liquidación / other, per `aeat-architecture-boundaries`'s closed-value-set
mandate — never reused or widened from `PostFilingEventKind`), `importe`
(non-negative `Decimal`, mirroring the ledger contract's amount-is-magnitude
convention), a typed `direccion` axis (owed vs. refundable) carried as its own
enum field rather than as sign, `periodo`, a closed `Situacion` StrEnum, and
`mode: Literal["read"]` as the structural no-write marker. This model, its
StrEnums, and their unit tests need no specimen and no new legal grounding —
AEAT's reported `importe`/`situacion` strings are displayed as reported.

**Snapshot service (unblocked today).** `DeudasService` /
`PersistedDeudasSnapshot` / `DeudasCapture`, structured identically to
`ExpedientesService` (`src/cadrumo/application/live/_expedientes.py`): a
`StatelessSnapshotService` over `SecureSnapshotRepository`, a new
`LIVE_DEUDAS_SNAPSHOT_NAMESPACE` bucket-scoped namespace constant, and
content-addressed snapshot ids via the same `_derive_snapshot_id` pattern.
Buildable and roundtrip-testable against a synthetic `DeudasCapture` fixture
with no specimen dependency.

**Read-landing guard (partially blocked).** The guard function itself —
modelled on `_censal_datos.py:791`'s `_assert_read_landing`, refusing at
runtime the moment the session lands on a payment or aplazamiento-request
path — can be written and unit-tested against synthetic landing URLs today.
Its `allowed_path_prefixes` tuple cannot be populated with the real
debts-consulta path until a specimen is captured; ship the guard with an
empty/refusing prefix set (fails closed by construction) and populate the
real prefix in the specimen-dependent row.

**Adapter parse function (specimen-blocked).** The DOM-to-`Deuda` mapping,
the navigation path, and the trámite/apoderamiento gating cannot be written
without a real page. This row is explicitly deferred until an operator
authorises a live authenticated capture; it is not scheduled by this record.

**CLI surface (unblocked for the service layer, blocked for `pull`).** `aeat
app live deudas list`, `view` and `latest` read persisted snapshots and need
no specimen — the exact verb shape `expedientes` already uses (`app live
expedientes latest|list|view`, `test_root_fallback_write_guard.py:611-613`).
`aeat app live deudas pull` — the AEAT fetch,
named `pull` never `capture`/`refresh`/`fetch`/`sync` per `aeat-cli-contract`
— is wired last, once the adapter exists, and its own row adds `"app live
deudas pull"` to `PROFILE_BOUND_WRITE_VERB_PATHS`
(`src/cadrumo/application/storage_write_policy.py:122`) in the same commit,
with a comment stating it persists a captured snapshot to bucket storage
(mirroring the existing `"app live expedientes pull"` entry's rationale). The
same commit adds `deudas pull` to the operator-orientation agent-harness
document alongside `expedientes pull` and `notifications pull`
(`src/cadrumo/_data/agent/rules/cadrumo-operator-orientation-routing.md:59-64`),
per `aeat-cli-contract`'s mandate that the harness cites only the live verb
surface.

**Grounding rows (human-owner-blocked).** Each `ObjetoTributario` category
that carries a legally-established percentage or rate the app interprets
(rather than merely displays as reported) gets its own legal-catalogue entry
citing its establishing LGT article, authored and reviewed by a named human
under `aeat-calculation-grounding`. These rows are listed but not executed by
this record; they block only the *interpretation* layer, never the base
display-as-reported layer.

**Locale rows (peer-WIP-blocked).** CLI help text and any operator-facing
labels for the new verbs get real `es`/`en`/`ca`/`hu` values via `dev.locales
set`, scheduled after the in-flight `en.yml`/`hu.yml` WIP lands and
`scaffold --check` is clean.

Divergence reconciliation against filed declarations (considered option 2) is
explicitly out of scope for this record and requires its own ADR once option
1 ships and a specimen exists to validate the comparison against.

## Rationale

Option 1 wins on a knockout criterion the other two fail: it is the only
option whose full scope is buildable and testable today without either a live
AEAT specimen or new legal grounding for every displayed field, because it
displays AEAT's own reported figures rather than asserting or deriving new
ones. Option 2 is strictly more capable but strictly more expensive, and its
comparison authority cannot be validated without a real specimen and without
option 1's read surface already existing — sequencing it after, as a
separately decided extension, is the only order the evidence supports. Option
3 fails on identity grounds the research already settled: an event-stream
enum and a standing-liability register are different entities, and forcing
one type to serve both is the exact "binding" collision
`aeat-architecture-boundaries` names as a worked failure mode. The safety
argument reinforces option 1 independently of cost: the smaller the surface,
the smaller the payment-adjacency blast radius, and a read-and-display record
with no write path and a fail-closed landing guard is the shape that keeps
"read AEAT's deudas" categorically separate from "act on AEAT's deudas".

## Consequences

**Gains.** An operator gets, for the first time, a place inside the app to see
what AEAT currently reports as owed — the domain type, snapshot service,
guard, and list/show CLI verbs ship without waiting on a specimen or new legal
review. The structural separation from `PostFilingEventKind` keeps both
entities honest: neither one silently grows fields that belong to the other.
The read-landing guard, built fail-closed from birth, means a future
specimen-dependent row can only *narrow* the refused surface, never widen it
by omission.

**Difficulties.** The feature ships visibly incomplete until a specimen
exists: `pull` cannot be wired, so the register stays empty until an operator
authorises live capture — an honest but unsatisfying interim state that must
not be papered over with a synthetic-looking `pull` that fabricates rows.
Grounding the interpretive layer (percentage bands, rates) needs sustained
human legal-review capacity this record does not itself provide.

**Pitfalls this decision heads off.** Widening `PostFilingEventKind` instead
would have looked like the cheaper path and quietly merged two entities'
lifecycles. Skipping the read-landing guard until the adapter existed would
have left a window where a first specimen-driven navigation could land on a
payment page with no runtime refusal in place. Treating AEAT's reported
`importe` as license to skip all grounding would have let a future contributor
add an interpretive label without the review this record requires — the
distinction between "display what AEAT reported" and "assert what a
provision means" is the line every future row on this register must respect.

**Pathway opened.** Once a specimen exists and this record's read surface is
live, a divergence-reconciliation ADR (rejected option 2) becomes buildable
against real data — its comparison authority has something to compare
against, and its advisory-only gate has a genuine display surface to attach
to.

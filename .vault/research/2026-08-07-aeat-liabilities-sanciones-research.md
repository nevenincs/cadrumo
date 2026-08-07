---
tags:
  - '#research'
  - '#aeat-liabilities-sanciones'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:4fd479d972c309cb5ee0196a0921b39355c999e9fe3d95206504ea2df07302ca'
related: []
---

# `aeat-liabilities-sanciones` research: `Sanciones, recargos and deudas pendientes: gap and options`

The application has no typed representation of a taxpayer's AEAT-owed liabilities
— a sanción, a recargo de apremio, a liquidación from a comprobación, a suffered
intereses de demora, or an aplazamiento/fraccionamiento in force. The only
existing surface, `PostFilingEventKind` (`src/cadrumo/core/_post_filing_event.py`),
is a closed classification enum that tags pulled notification/expediente rows by
concepto substring; it carries no amount, no deadline, and no procedural state,
and it shipped with no governing ADR. Every read surface the app already drives
(notificaciones, expedientes, declaraciones register) is proven read-only-safe;
none of them targets AEAT's actual debt-consultation surface. This document
grounds the gap: what AEAT exposes, the governing LGT taxonomy, whether any of
it feeds a calculation, what a typed record would need, and the option space —
so the ADR can decide without re-deriving any of this. Implementation is
authorized for this area once the ADR lands; this document stays research-only
(no ADR, no code, no legal-catalogue entry, no registry TOML) and is written so
the ADR can be authored directly from it: the recommended typed-record shape,
owning package, sibling family and Sede surface are stated concretely below,
not left as an open question.

## Findings

### AEAT exposes a genuine read-only "Consultar deudas" surface, separable from payment

AEAT's public sede documentation describes a dedicated "Consultar deudas"
procedure under `sede.agenciatributaria.gob.es`, reachable with Cl@ve,
certificado, DNI electrónico or eIDAS, on the taxpayer's own behalf or via
apoderamiento `GENERALDATPE` (general) or `RA19006` (specific to debt
consultation). The consultation list displays, per debt: **clave de
liquidación, objeto tributario, importe pendiente, período, and situación**
(current procedural state) — clicking a row surfaces detail for that single
obligation. Critically, **the view is a distinct stage from payment**: only
after viewing does the operator choose "pagar todas mis deudas" / "pagar
algunas deudas" / "pago parcial", each a separate procedure requiring a
different, payment-specific apoderamiento code (`GENERALLEY58`, `RA19007`
through `RA19010`) and ending in an NRC. This mirrors the shape the app already
trusts elsewhere: `Consultar declaraciones presentadas`
(`src/cadrumo/adapters/outbound/aeat/sede/_declarations.py:1`) is read-only and
distinct from `Mis Expedientes`
(`src/cadrumo/adapters/outbound/aeat/sede/_walker.py`), which is itself a
*procedures* tree the app already walks read-only — its category tree includes
a "sanciones, recursos, certificados" branch that every production caller
currently avoids by always passing an explicit `modelo=` filter
(`src/cadrumo/adapters/outbound/aeat/sede/_schema.py:89-116`, `Expediente.modelo`
is `None` for exactly this branch). A debts consulta adapter is a new sibling
surface, not an extension of the expedientes walker: the debts list is keyed by
clave de liquidación / objeto tributario, not by expediente id, and AEAT serves
it from a different trámite than either existing surface. No internal AEAT
`wlpl`-style path or ZK form structure for it is known to this app — that is
unverifiable without a live authenticated probe (see "Not investigated" below).

A neighbouring page (`.../deudas-apremios-embargos-subastas/recat.html`) names
apremios, embargos, domiciliaciones, compensaciones, certificados de deuda
pendiente and subastas as adjacent AEAT recaudación services, but is purely a
navigation/appointment index — it does not itself expose a read surface beyond
what "Consultar deudas" and the existing notificaciones/expedientes surfaces
already reach. A `providencia de apremio` or `diligencia de embargo` currently
surfaces to this app only as a classified notification row
(`PostFilingEventKind.PROVIDENCIA_APREMIO` / `.DILIGENCIA_EMBARGO`), never as a
line item with an amount from the debts consulta.

### The legal taxonomy spans five distinct LGT objects, only two of which the bundled corpus grounds today

| Concept | Governing provision | Bundled corpus? | Grounding status |
|---|---|---|---|
| Interés de demora (self-computed, casilla-facing — see the decisive Q3 finding above) | LGT (Ley 58/2003) art. 26 | Yes — `src/cadrumo/_data/corpus/normatives/html/ley-58-2003-art-26.html.extracted.md` | Already grounded and shipped (M100 c0576 and siblings) |
| Recargo por declaración extemporánea | LGT art. 27 | Yes — `.../ley-58-2003-art-27.html.extracted.md` | Already built and grounded. Do not duplicate |
| Recargo del período ejecutivo / recargo de apremio (ejecutivo, reducido, ordinario) | LGT art. 28 | **No** | **New grounding row required** — no `corpus_ref` exists; a human legal-catalogue reviewer must author and adjudicate it, never an agent (per `aeat-calculation-grounding`'s human-reviewed, filing-grade mandate) |
| Sanción tributaria (infracciones y sanciones, Título IV) | LGT arts. 178–212 (principios, tipificación, arts. 191–197 pecuniarias proporcionales) | **No** | **New grounding row required**, human-owned |
| Aplazamiento / fraccionamiento del pago | LGT art. 65, art. 82 (garantías) | **No** | **New grounding row required**, human-owned |
| Procedimiento de apremio / providencia / embargo | LGT arts. 163, 167–173 | **No** | **New grounding row required**, human-owned |
| Medios de revisión (recurso de reposición, etc., relevant once a sanción or liquidación is contested) | LGT art. 213 | Yes — `.../ley-58-2003-art-213.html.extracted.md` | Bundled but not a value-establishing provision (procedural-review only); no grounding claim needed for this scope |

Because the Q3 finding establishes this record is read-and-display only, none
of these provisions gate a casilla `legal_refs` value the way a calculation
input would — but the typed record's own `legal_refs`/`source_refs` fields
(carried per `aeat-calculation-grounding`'s "grounding travels to the operator"
mandate, so the operator sees which article underlies a displayed sanción or
recargo) still need the missing four rows authored before those categories can
display a legal citation. Interés de demora and recargo extemporáneo can cite
their existing corpus entries immediately; sanción, recargo de apremio,
aplazamiento and procedimiento de apremio cannot until a human reviewer adds
them. General-knowledge grounding for those article ranges (Título IV =
178–212, art. 28 = recargos del período ejecutivo, art. 65/82 = aplazamiento)
came from public web search (`iustel.com`, `boe.es` RD 2063/2004 index page)
and is consistent with the LGT's own structure, but **was not cross-checked
against the live BOE consolidated text** — per `aeat-calculation-grounding`,
even a bundled excerpt is not infallible on numbers, and an unbundled one is
unverified prose, not a citable source.

### Keep the three "recargo" concepts strictly apart

This gap concerns only the third row below; the first two are unrelated,
already-built mechanisms and must never be touched or referenced by the new
work:

1. **Recargo de equivalencia** — an IVA regime (LIVA art. 161), not a penalty.
   Built, and already summed into every M303/M390 total cuota per
   `aeat-calculation-grounding`'s total-aggregation mandate.
2. **Recargo por presentación extemporánea** — a late-filing surcharge (LGT
   art. 27.2), built and grounded, banded by delay length.
3. **Recargo de apremio** — a collection-enforcement surcharge (LGT art. 28),
   charged by AEAT once a debt enters período ejecutivo. Entirely unbuilt; the
   subject of this document.

### Decisive answer: an AEAT-imposed sanción, recargo de apremio or AEAT-determined interés de demora never reaches a modelo casilla — this is purely read-and-display

The registry already carries a casilla-level "Intereses de demora" concept, and
it is important to name it precisely so it is never confused with this gap. M100
casilla `0576` (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/c0576.toml`,
`semantic_role = "irpf_intereses_demora_perdida_transitoria_estatal"`) and its
sibling regularización casillas (`_REGULARIZACION_PREVIOUS_INTEREST_CASILLAS`,
grounded and tested in
`src/cadrumo/domain/calculations/registry/tests/test_modelo_100_registry_role_legal_refs.py:198-213`)
carry `legal_refs = [..., "ley-58-2003:art-26"]`. That casilla is the taxpayer
**self-computing** an interés de demora as part of voluntarily regularizing a
previously-claimed tax benefit within the SAME declaration (`section =
["resultados", "calculo_impuesto_res", "gravamenes_res"]`) — a value the
formula engine derives from the taxpayer's own prior figures under LGT art.
26.5, never a value AEAT hands back to the app. This is a categorically
different data flow from the gap this document covers: AEAT-imposed liabilities
— a sanción, a recargo de apremio, a liquidación from a comprobación, or an
interés de demora AEAT itself assesses via its own procedimiento (LGT art.
26.2.a/d) and surfaces through "Consultar deudas" — are administrative acts
happening to a filing that already exists; they are never an input the
taxpayer types into, or the formula engine derives for, a future filing. No
casilla anywhere in the registry accepts "amount AEAT says I owe in recargo de
apremio" or "amount of my sanción" as an input, and none should ever be added:
a modelo casilla exists to compute or declare the taxpayer's own tax position
for a period, and an AEAT-imposed liability is not part of that position — it
is downstream of it. Grep confirms no `BindingSourceKind` or `source` binding
family references any post-filing enforcement concept today.

This resolves the calculation-grounding question decisively: the new typed
record is **purely read-and-display**, and the `aeat-calculation-grounding` /
`aeat-calculation-aggregation` rules' strict channel/oracle machinery is not
triggered *as long as the implementation enforces that boundary structurally* —
never letting a persisted sanción/recargo/deuda value flow into any
`BindingAggregation`, relation, or casilla resolution, and never adding a
binding `source` kind for it. If a later feature wants to *reconcile* a filed
declaration's resultado against AEAT's recorded deuda (comparing what the app
computed against what AEAT's debts list shows for the same period), that
comparison is a **display-time divergence flag** only, mirroring the IVA
wallet's snapshot-vs-declared comparison, and must stay non-blocking — feeding
it into a casilla would violate `no-silent-under-declaration` and
`aeat-calculation-grounding` with no existing sanctioned mechanism. This
materially shrinks the scope the ADR needs to cover: no oracle, no grounded
casilla, no aggregation channel — only a typed record, a read-only adapter, and
a snapshot service.

### Concrete typed-record shape, owning packages, and CLI surface — actionable for the ADR

The sibling family to mirror end-to-end is the expedientes stack, and a new
`Deuda`/`deudas` family should be placed at exactly the same four layers, with
the same file per layer:

- **Outbound adapter schema** — new
  `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`, mirroring
  `Expediente` (`src/cadrumo/adapters/outbound/aeat/sede/_schema.py:89-140`).
  A `Deuda(BaseModel)` with `model_config = STRICT_FROZEN_CONFIG`: a validated
  `clave_liquidacion: str` identifier field (pattern TBD from a real specimen —
  see "Not investigated"), `objeto_tributario: str`, `importe_pendiente:
  Decimal = Field(ge=Decimal("0"))` (non-negative, the same precedent the same
  module's own wallet `pending_amount` field sets at
  `src/cadrumo/adapters/outbound/aeat/sede/_schema.py:340`, sourced through
  `coerce_decimal_strict`), `periodo: Period | None`, `situacion: DeudaSituacion` (new closed
  enum — see below), and `mode: Literal["read"]`. The walker function
  (`walk_deudas_consulta` or similar, named after `walk_expedientes_tree` /
  `walk_declarations_register`) drives the read-landing guard
  (`assert_read_landing(..., allowed_path_prefixes=_DEUDAS_READ_PATH_PREFIXES)`
  per `src/cadrumo/adapters/outbound/aeat/sede/_walker.py:109-134`), pinned to
  the debts-consulta path once known — never to any path prefix under the
  payment flow (the three "pagar ..." sub-flows AEAT's own help page
  describes must never be reachable from this adapter).
- **New closed enum in `core/`** — `DeudaSituacion` (or similar), a
  `StrEnum` per the architecture-boundaries rule ("closed value sets live in
  `core/`"). Its member set cannot be finalised without a live specimen (AEAT's
  help text names "situación" as a field but not its enumerated values); this
  document does not invent members. A `DeudaConcepto`/category field
  classifying the LGT object (sanción / recargo de apremio / liquidación /
  interés de demora / aplazamiento) is a **separate** closed axis from
  `PostFilingEventKind`, never a widening of it — `PostFilingEventKind`
  classifies a *notification event*, a debts-consulta row is a *standing
  liability with an amount and a procedural state*; conflating them would
  make one type serve two entities with different identity, source surface
  and lifecycle (exactly what `aeat-architecture-boundaries` forbids). An
  `ACUERDO_SANCION`-classified notification *announces* a sanción; a
  debts-consulta row is the sanción's resulting deuda, once liquidated — two
  facts about one procedure, not one fact twice.
- **Application snapshot service** — new
  `src/cadrumo/application/live/_deudas.py`, mirroring
  `ExpedientesService` / `PersistedExpedientesSnapshot` / `ExpedientesCapture`
  (`src/cadrumo/application/live/_expedientes.py:46-140`) exactly: a
  `DeudasCapture(BaseModel)` slim wrapper, `PersistedDeudasSnapshot`,
  content-addressed snapshot ids (`_derive_snapshot_id` hashing the canonical
  capture JSON, same pattern), a new bucket-scoped namespace constant
  (`LIVE_DEUDAS_SNAPSHOT_NAMESPACE`, alongside
  `LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE`), and `DeudasService` extending
  `StatelessSnapshotService[PersistedDeudasSnapshot, DeudasCapture]`.
  Structurally read-only by construction, same as `ExpedientesService`'s own
  docstring guarantee: no method calls AEAT to mutate state.
- **CLI entrypoint** — new `src/cadrumo/entrypoints/cli/_app_live_deudas_cli.py`
  and payload models in `_app_live_payloads.py`, exposing
  `aeat app live deudas pull|list|view|latest`, the exact verb shape
  `expedientes` already uses (`aeat app live expedientes pull`, confirmed live
  in `src/cadrumo/application/storage_write_policy.py:194` and
  `src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py:611-613`).
  Per `aeat-cli-contract`, landing this verb requires the same hand-swept
  surfaces expedientes already appears on: the `storage_write_policy.py`
  allowlist, any `default_suggestion` in the error registry pointing at the
  new list verb, and the agent-harness document
  (`src/cadrumo/_data/agent/rules/cadrumo-operator-orientation-routing.md:62`)
  that already enumerates `expedientes pull` alongside `notifications pull`
  and would need `deudas pull` added in the same commit as the verb.

### Options

1. **Minimal read-and-display inventory.** New adapter (debts-consulta walker,
   mirroring the declarations-register / expedientes read-guard pattern) plus a
   new `DeudasService` snapshot family mirroring `ExpedientesService` exactly.
   Persist typed `Deuda` rows (clave de liquidación, objeto tributario,
   importe, período, situación, classified LGT category) read-only, surfaced
   through a new CLI read verb and the overview. No divergence logic, no
   calculation coupling, no write path. Smallest, most self-contained; ships
   value (an operator finally sees what AEAT thinks is owed) without touching
   any calculation-grounding machinery.
2. **Full reconciliation with divergence decisions**, cloning the IVA-wallet /
   `apply_cotejo` shape: snapshot the AEAT debts list, compare against the
   app's own filed-declaration resultados, and persist a divergence decision
   when AEAT's recorded deuda diverges from what the app expects (e.g. AEAT
   shows a debt for a period the app believes was paid, or a recargo the app's
   own extemporaneous-filing logic did not predict). This is materially more
   work: it needs a comparison authority analogous to
   `reconcile_iva_compensation_wallet`, a decision repository, and a blocking
   or advisory gate — and per the calculation-aggregation rule, must stay
   strictly non-blocking/advisory-only, never feeding a casilla.
3. **Extend `PostFilingEventKind` in place.** Add amount/deadline fields to the
   existing enum's carrying row type. Rejected on the evidence above:
   `PostFilingEventKind` classifies an event stream (notifications/expedientes
   rows), not a standing liability register; a debts-consulta row has no
   natural event timestamp, and conflating the two would make one type serve
   two entities with different identity, source surface, and lifecycle — the
   exact shape the architecture-boundaries and naming rules exist to prevent.

The evidence favors option 1 as the ADR's starting point, with option 2 named
as an explicit, separately-decided extension once option 1's read surface
exists and a real debts-consulta specimen is available to validate the
reconciliation comparison against. Option 3 is not viable on the evidence
gathered.

### Not investigated — requires a live authenticated probe this document does not attempt

- The exact URL, ZK/AJAX form structure, and trámite/apoderamiento gating of
  AEAT's "Consultar deudas" surface as actually served (path prefix for the
  read-landing guard, whether it is one page or a category-tree like Mis
  Expedientes, what identifiers appear in the DOM). Public help pages describe
  the *procedure*, not the page's markup.
- Whether a sanción, once firm, always appears in "Consultar deudas" with a
  clave de liquidación, or whether some sanciones states are visible only
  through the expedientes "sanciones" branch and never reach the debts list.
- Whether aplazamiento/fraccionamiento requests already granted appear as a
  distinct situación value in the debts list or require a separate consulta.
- Live cross-check of LGT arts. 28, 65, 82, 163, 167–173, 178–212 against the
  BOE consolidated text, per `aeat-calculation-grounding`'s bundled-corpus-is-
  not-infallible mandate — this document only located the article numbers via
  public web search, it did not verify their text.

No credentials were used, no authenticated AEAT session was opened, and no
Playwright automation against a real AEAT surface was attempted for this
document, per the sensitive-financial-data and never-file mandates.

## Sources

- `src/cadrumo/core/_post_filing_event.py:1-184` — `PostFilingEventKind`, the only existing classification of post-filing events; no amount/deadline/state.
- `src/cadrumo/adapters/outbound/aeat/sede/_schema.py:89-140` — `Expediente`, the sibling read-only record shape to mirror (`mode: Literal["read"]`, strict-frozen config).
- `src/cadrumo/adapters/outbound/aeat/sede/_schema.py:338-340` — `pending_amount: Decimal = Field(ge=Decimal("0"))`, the non-negative-decimal-field precedent for a new `importe_pendiente` field.
- `src/cadrumo/core/aggregation.py` — `BindingSourceKind`, the closed taxonomy of registry `source` tokens; confirmed by full enumeration that no member references any post-filing enforcement concept (sanción, recargo de apremio, deuda), grounding the "never feeds a casilla" claim structurally, not just narratively.
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/c0576.toml` — M100 casilla `0576`, the existing self-computed "Intereses de demora (pérdida transitoria estatal)" casilla, grounded to `ley-58-2003:art-26`; cited to distinguish the already-built self-computed-interest mechanism from this document's gap.
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_100_registry_role_legal_refs.py:198-213` — test asserting `_REGULARIZACION_PREVIOUS_INTEREST_CASILLAS` cite `ley-58-2003:art-26`, confirming the casilla-level interés de demora is regularización-anterior self-computation, not an AEAT-supplied value.
- `src/cadrumo/application/storage_write_policy.py:194` — `"app live expedientes pull"` in the write-policy allowlist; a new `deudas pull` verb needs the same entry.
- `src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py:611-613` — asserts `expedientes latest|list|view` verb identifiers; the shape a new `deudas` verb family must match.
- `src/cadrumo/_data/agent/rules/cadrumo-operator-orientation-routing.md:59-64` — the agent-harness document enumerating live-read verbs (`expedientes pull`, `notifications pull`, etc.); a new `deudas pull` verb must be added here in the same commit per `aeat-cli-contract`.
- `src/cadrumo/adapters/outbound/aeat/sede/_walker.py:109-134` — `_RESUMEN_READ_PATH_PREFIXES` / `assert_read_landing`, the read-landing guard pattern a new debts adapter must replicate.
- `src/cadrumo/adapters/outbound/aeat/sede/_declarations.py:1-26` — module docstring distinguishing the procedures tree (Mis Expedientes, includes a "sanciones, recursos, certificados" category never targeted by any caller) from the canonical filings register.
- `src/cadrumo/adapters/outbound/aeat/sede/__init__.py:1-66` — the sede subpackage's public API and navigation-flow docstring; no debts-consulta surface exported.
- `src/cadrumo/application/live/_expedientes.py:46-140` — `ExpedientesService` / `PersistedExpedientesSnapshot` / `ExpedientesCapture`, the snapshot-service family to mirror for a new `DeudasService`.
- `src/cadrumo/_data/corpus/normatives/html/ley-58-2003-art-26.html.extracted.md` — bundled corpus text, interés de demora (LGT art. 26).
- `src/cadrumo/_data/corpus/normatives/html/ley-58-2003-art-27.html.extracted.md` — bundled corpus text, recargo extemporáneo (LGT art. 27), already built elsewhere; not duplicated here.
- `src/cadrumo/_data/corpus/normatives/html/ley-58-2003-art-213.html.extracted.md` — bundled corpus text, medios de revisión (LGT art. 213).
- Directory listing of `src/cadrumo/_data/corpus/normatives/html/` confirms no `ley-58-2003-art-28`, `art-65`, `art-82`, `art-163`, `art-167` through `art-173`, or any art. 178–212 file is bundled.
- https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/pago-impuestos-deudas-tasas-ayuda-tecnica/consultar-deudas.html — AEAT public help page, "Consultar deudas": access requirements, displayed fields, separation from payment, apoderamiento codes.
- https://sede.agenciatributaria.gob.es/Sede/deudas-apremios-embargos-subastas/recat.html — AEAT public help index page for apremios/embargos/subastas; navigation-only, no substantive procedural detail.
- General-knowledge claim, unverified against live BOE text: LGT Título IV (arts. 178–212) governs infracciones y sanciones, art. 28 governs recargos del período ejecutivo, art. 65 governs aplazamiento/fraccionamiento — sourced from public web search (iustel.com, boe.es RD 2063/2004 index), not from a corpus fetch or article-by-article read.

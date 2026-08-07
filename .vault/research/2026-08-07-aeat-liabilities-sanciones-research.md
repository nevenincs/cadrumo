---
tags:
  - '#research'
  - '#aeat-liabilities-sanciones'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e91881e1d572edbf3fbd13931388b7f2a12037662e978ba77d5127b25319cdf4'
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
so the ADR can decide without re-deriving any of this.

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

| Concept | Governing provision | Bundled corpus? |
|---|---|---|
| Interés de demora | LGT (Ley 58/2003) art. 26 | Yes — `src/cadrumo/_data/corpus/normatives/html/ley-58-2003-art-26.html.extracted.md` |
| Recargo por declaración extemporánea | LGT art. 27 | Yes — already built and grounded; `.../ley-58-2003-art-27.html.extracted.md`. Do not duplicate; do not conflate with recargo de equivalencia (an IVA regime, LIVA art. 161, unrelated) |
| Recargo del período ejecutivo / recargo de apremio (ejecutivo, reducido, ordinario) | LGT art. 28 | **No** — not present under `.../corpus/normatives/html/` |
| Sanción tributaria (infracciones y sanciones, Título IV) | LGT arts. 178–212 (principios, tipificación, arts. 191–197 pecuniarias proporcionales) | **No** |
| Aplazamiento / fraccionamiento del pago | LGT art. 65, art. 82 (garantías) | **No** |
| Procedimiento de apremio / providencia / embargo | LGT arts. 163, 167–173 | **No** |
| Medios de revisión (recurso de reposición, etc., relevant once a sanción or liquidación is contested) | LGT art. 213 | Yes — `.../ley-58-2003-art-213.html.extracted.md`, but this is a procedural-review provision, not a value-establishing one |

General-knowledge grounding for the article ranges above (Título IV = 178–212,
art. 28 = recargos del período ejecutivo, art. 65/82 = aplazamiento) came from
public web search (`iustel.com`, `boe.es` RD 2063/2004 index page) and is
consistent with the LGT's own structure, but **was not cross-checked against
the live BOE consolidated text** the way `aeat-calculation-grounding` requires
before any of these could be cited as a `legal_refs` value. Per that rule, a
value or period any of these objects carries (the sanción percentage bands in
arts. 191–197, the recargo de apremio percentages in art. 28, an
aplazamiento's interest rate) would need its own `corpus_ref` resolving to the
**last** version of the consolidated BOE text before it could ship — none of
that grounding work exists yet, and this document does not attempt it.

### None of this is purely informational once amounts are involved — but nothing here should feed a modelo casilla

Interés de demora and recargo de apremio are *consequences of the taxpayer's
own late payment or the enforcement process*, not inputs to any modelo's tax
base or cuota — no AEAT modelo casilla asks "how much do you owe in recargos
de apremio". The one place a penalty-adjacent value could arguably touch a
calculation is a sanción's own base (a percentage of the cuota dejada de
ingresar, LGT arts. 191–197) — but that base is *derived from* the taxpayer's
own liquidación, never *fed into* one; there is no forward calculation
dependency. This means the `aeat-calculation-grounding` and
`aeat-calculation-aggregation` rules' strict channel/oracle machinery is **not
triggered** by a read-and-display record of these objects, so long as the
implementation never lets a persisted sanción/recargo/deuda value flow into any
`BindingAggregation`, relation, or casilla resolution. If a future feature
wanted to *reconcile* a filed declaration's resultado against AEAT's recorded
deuda (a legitimate divergence-detection use, mirroring the IVA wallet chain's
snapshot-vs-declared comparison), that comparison is a **display-time
divergence flag**, not a calculation input, and should stay that way — feeding
it into a casilla would be a `no-silent-under-declaration` and
`aeat-calculation-grounding` violation with no existing sanctioned mechanism.
This materially shrinks the scope: the work is read-and-display plus, at most,
non-blocking divergence advisories — never a calculation surface.

### A typed record would live beside the notifications/expedientes family and needs its own snapshot service

The sibling family to mirror is `ExpedientesService` /
`PersistedExpedientesSnapshot` / `ExpedientesCapture`
(`src/cadrumo/application/live/_expedientes.py:46-140`): a `mode: Literal["read"]`
structural marker on every boundary record, a `StatelessSnapshotService` over
`SecureSnapshotRepository`, content-addressed snapshot ids
(`_derive_snapshot_id` hashing the canonical capture JSON), and a bucket-scoped
namespace constant (`LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE`) analogous to what a
new `LIVE_DEUDAS_SNAPSHOT_NAMESPACE` would need. The adapter side mirrors
`Expediente` (`src/cadrumo/adapters/outbound/aeat/sede/_schema.py:89`): a
`STRICT_FROZEN_CONFIG` pydantic model with a validated AEAT-shaped identifier
field (here, clave de liquidación rather than expediente id), `mode:
Literal["read"]`, and a read-landing guard
(`assert_read_landing(..., allowed_path_prefixes=...)` per
`src/cadrumo/adapters/outbound/aeat/sede/_walker.py:109-134`) pinned to the
debts-consulta path once it is known — never to any path prefix under the
payment flow. A `sanciones`/`recargo`/`aplazamiento` typed field on the record
should carry its own closed `StrEnum` for objeto tributario / situación
(closed value sets live in `core/` per the architecture-boundaries rule) rather
than reusing or widening `PostFilingEventKind`, because that enum classifies a
*notification event*, not a *standing liability with an amount and a
procedural state* — the two are different entities (an
`ACUERDO_SANCION`-classified notification announces a sanción; a debts-consulta
row is the sanción's resulting deuda, if and once liquidated).

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

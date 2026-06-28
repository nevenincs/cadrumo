---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-sergio-cli-testimonial-audit]]"
  - "[[2026-05-27-pedro-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-24 Ramón Solá promotor inmobiliario IVA autoconsumo M303 M347`

## Scope

Twenty-fourth testimonial round, Ramón Solá Bruguera — Tarragona,
54, owner of "Solá Promociones SL" (real-estate developer). 2024:
12 first-occupancy housing sales €4.2M (IVA tipo reducido 10%), 4
self-held apartments for rental (cost €1.4M — autoconsumo Art. 9.1.c
LISIVA hot path), land €800k. INCN €4.2M (above ERD threshold,
tipo IS 25%). Exercises promotor inmobiliario surface: IVA reduced
type 10%, autoconsumo, inversión sujeto pasivo, M390 anual breakdown,
M347 operaciones con terceros.

## Findings

### CRITICAL — IVA autoconsumo Art. 9.1.c LISIVA absent

M303 bindings list shows 6 entries: general/reducido/super-reducido
repercutido + soportado-interiores + autorepercutido-intracom +
compensación-pendiente. **NO binding for autoconsumo promotor.**

When promotor builds apartments for sale and decides to use them
for own rental, must self-bill 21% IVA on construction cost (Art.
9.1.c LISIVA). For Ramón's 4 self-held apartments (cost €1.4M):
silent obligation never surfaced. AEAT inspection later finds it
+ recargo + intereses.

Every active promotor affected (~50k SLs in real-estate development
activity in Spain).

### CRITICAL — M347 multi-row contraparte mechanism absent (FOURTH confirmation of #200 pattern)

`aeat app modelo bindings list --modelo 347` returns 0 bindings.
M347 calculate produces empty borrador with just 2 casillas
(decl.ejercicio + decl.tipo-declaracion). No mechanism to declare
contrapartes (NIF + nombre + importe-Q1 + importe-Q2 + ...).

Profile has `third_party_transactions_above_347_threshold = True`
(detection works) — but no input channel for the row data. Same
structural pattern as:
- M184 (Núria F1+F2, #200).
- M232 (Sergio C4, #184).
- M349 (Pedro #2, #200).

**Now FOUR independent modelos confirm the cross-cutting multi-row
mechanism gap (#200).** Adding M347 to its scope.

For a promotor with 25-30 obligados-declarables proveedores
(architects, builders, suppliers > €3,005.06), the empty borrador
makes M347 unfileable. Annual obligation; ~200k filers/year.

### CRITICAL — M100 registry validation error blocks M303 calculate

Cross-model bug: `calculate --modelo 303` raises:
```
modelos/100: invalid revision '2024': 1 validation error for
ModeloRevision — bindings.6.source_citations.0.required_text —
Field required
```

The M100 (IRPF) revision 2024 has a binding (#6) with empty
`required_text` on its source_citation. This validation occurs in
the registry-loading path of M303 calculate (probably full-tree
load). Blocks ALL M303 calculate operations even for non-M100 cases.

Same family as Yara H7 (#190), Sergio H3, Khalid #167 — legal-
catalogue corpus validation overzealous at production CLI surfaces.
Should be deferred to a dedicated audit verb.

### HIGH — Inversión sujeto pasivo Art. 84.2 LISIVA absent

For second-transmission sales between empresarios (or renunciation
of exemption), the IVA is ingreso del comprador, not the vendor.
M303 has no binding for ISP base declarations. Promotor secondary
transmissions (resale of own stock to other developers, B2B
property sales) silently miss the ISP declaration.

### HIGH — M303 calculate path blocked without ledger entries

`ledger_iva_aggregation` bindings refuse direct override —
`caller binding values cannot override bucket-derived source
bindings`. To calculate M303 manually for verification, must first
import ledger. Re-confirms Khalid round-11 + Sergio round-13
pattern. Document the workflow clearly OR allow manual override
for verification scenarios.

### HIGH — M200 hidden bindings discoverable only via error

`--relation` for M202 (pagos fraccionados IS) is required but
NOT shown in `bindings list --modelo 200`. Discovered through
failed `calculate` attempt. UX gap — discovery surface incomplete.

### MEDIUM — M390 autoconsumo casilla missing

M390 has IVA tipo breakdown structure (cuotas 4%/10%/21%) — good.
But no casilla for "Operaciones asimiladas a entregas de bienes
(autoconsumo)". Consequence of CRITICAL #1.

### MEDIUM — M390 cuotas anuales zero without ledger

Same ledger-blocker as M303 — without imported invoices, M390
casillas iva.anual.repercutido.* stay 0.

### POSITIVE — Several elements work correctly

- M303 binding for reducido (10%) exists structurally.
- M200 tipo 25% correctly applied for INCN €4.2M (re-confirms
  Sergio/Aitor — tipo path works for INCN > €1M; broken only for
  INCN < €1M ERD case #210).
- M390 desglose tipos structurally present.
- M347 obligation detection (via profile flag) activates.
- NIF/CIF validation rejects wrong control letter.

## Recommendations

Priority order:

1. **Multi-row mechanism #200 (CROSS-CUTTING)** — now extends to
   FOUR modelos. Add M347 to the task description. Promotor M347
   unfileable joins the unfileable M184/M232/M349 list.

2. **IVA autoconsumo Art. 9.1.c (CRITICAL, new)** — author binding
   `modelo-303-autoconsumo-promotor-base` + `cuota`, M390 casilla
   "Operaciones asimiladas a entregas". Wire to construct +
   `aeat-dr-303-dictionary` source_refs. Affects every active
   promotor.

3. **M100 registry validation blocking M303 (CRITICAL)** — same
   task as Yara H7 (#190) plus targeted fix on the specific empty
   `required_text`. Add to #190 description.

4. **Inversión sujeto pasivo Art. 84.2 (HIGH)** — author M303
   binding `modelo-303-isp-base` for promotor scenarios.

5. **M200 hidden bindings discovery (HIGH)** — include `--relation`
   axis in `bindings list` output.

6. **M390 autoconsumo casilla (MEDIUM)** — consequence of #2.

7. **M303 calculate-without-ledger documentation (HIGH)** —
   either allow manual override OR document the ledger workflow
   prominently.

8. **Onboarding question for promotor** — `config profile create`
   should ask "¿Realiza primeras transmisiones de vivienda sujetas
   al tipo 10%?" to activate autoconsumo + ISP workflows.

Promotor surface is structurally weak: tipo 25% + tipo 10% +
M390 breakdown all work mechanically, but the two CRITICAL
omissions (autoconsumo + M347 row mechanism) make the CLI
unsafe for actual promotor declarations.

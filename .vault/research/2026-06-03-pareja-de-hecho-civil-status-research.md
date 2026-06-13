---
tags:
  - '#research'
  - '#pareja-de-hecho-civil-status'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `pareja-de-hecho-civil-status` research: `Pareja de hecho CCAA-aware schema design`

Subagent research pass for #627 W09.P41.S346 (R9-ANDREA-HIGH).
Confirmed the codebase carries TWO enums in tension:
`RentaMaritalStatus` (literal AEAT `tipo_EstadoCivil` 4-value enum
at `src/aeat/domain/contribuyente/_renta_codes.py:28-34`) and
`SituacionFamiliar` (LIRPF Art. 82 unidad-familiar domain enum at
`:110-158`) which already includes `PAREJA_HECHO_REGISTRADA` and
`PAREJA_HECHO_NO_REGISTRADA` members. The Step description's framing
("add use_type enum") is a misread — the discriminator concept
already exists in `SituacionFamiliar`; the gap is the SCHEMA-side
carrier plus the cross-validation and per-CCAA routing.

## Findings

### AEAT ECIVIL fidelity is non-negotiable

AEAT's `tipo_EstadoCivil` field is a 4-value closed code published
in the disenos-registro properties files for every Renta year
2020-2025. Extending `RentaMaritalStatus` with a fifth value
`PAREJA_DE_HECHO_REGISTRADA` would emit a string the AEAT BOE/PADRE
parser rejects. The literal enum is the wire contract and must
mirror the published vocabulary exactly. This rules out the
"extend the existing enum" design path on regulatory grounds, not
ergonomic ones.

### SituacionFamiliar is half-wired

The domain enum at `_renta_codes.py:110-158` already includes
`PAREJA_HECHO_REGISTRADA` and `PAREJA_HECHO_NO_REGISTRADA` members
plus helpers `conjunta_eligible()`, `requires_spouse_or_partner()`,
`monoparental_required()`. `_verifier.py:140` consumes
`sf.conjunta_eligible()`. The wiring gap is the SCHEMA: no profile
fact produces a `SituacionFamiliar` value; the
`renta_taxpayer.marital_status` field is typed `string`, not even
enum-constrained to the AEAT 4-value set. S346 must close this
derivation gap, not author a new enum.

### CCAA-specific effects need structured data

Pareja-de-hecho deductions are spread across multiple CCAAs:
Andalucía (DECA15, REGA21, CONYA21), Canarias (PHDISCAN10),
Cantabria (D01CCANT2, D02CCANT2, CONVCANT5, DECCANT19),
Extremadura (CONVE4, IMP2E10, CONYE21), and several more. Many
deductions REQUIRE proof of inscription in the specific autonomic
registry. A single enum bit cannot carry `(ccaa, registration_date,
partner_nif, registry_name)` provenance, but those four fields are
exactly what the legal_refs require to evaluate the deduction.

### Recommended design: separate registration record

A new `[[sections]] key = "pareja_de_hecho"` profile section
(sensitivity = identity, effective_dated = true), with fields:

- `registered` (boolean) — is the couple inscribed in an
  autonomic/municipal registry
- `ccaa` (enum, same closed set as `tax_residence.ccaa`) — which
  registry
- `registration_date` (date) — `valid_from` of the registered
  status
- `partner_tax_id` (string) — partner NIF (parallels
  `renta_spouse.tax_id`)
- `registry_name` (string, optional) — free-form registry name for
  export provenance

The existing `renta_taxpayer.marital_status` stays the 4-value AEAT
enum (re-typed `enum` with `enum_values = ["1","2","3","4"]` —
currently it is loose `string`, which is itself a gap).

### Cross-validation rules

1. `pareja_de_hecho.registered = true` AND `marital_status = "2"
   (CASADO)` is forbidden (a married person cannot simultaneously
   be registered as pareja de hecho with another partner —
   Art. 234-2.b CCCat, Art. 1.2 of most autonomic laws).
2. `pareja_de_hecho.registered = true` requires `partner_tax_id`
   non-empty AND `ccaa` non-empty AND `registration_date`
   non-empty (ADVISORY; some deductions tolerate the partner NIF
   being absent for partner-already-deceased cases).
3. Derived `situacion_familiar` (binding-resolver computed):
   - `("2", _)` → `CASADO`
   - `("1"|"3"|"4", true)` → `PAREJA_HECHO_REGISTRADA`
   - `("1", false)` → `SOLTERO`
   - `("4", false)` → `SEPARADO_DIVORCIADO`
   - VIUDO without registration → `SOLTERO` for conjunta eligibility
     (Art. 82 LIRPF treats widow as single for unidad-familiar)
4. If `pareja_de_hecho.registered = true` but `ccaa` is outside
   the deduction-bearing set, the verify gate emits ADVISORY
   noting that no CCAA deduction surface is reachable for that
   registry jurisdiction (per `no-silent-under-declaration` rule).

### Affected M100 calculation chains

- Unidad-familiar / TIPOTRIBUTACION (Art. 82 LIRPF):
  `RentaDeclaracionType.JOINT` gating; the derived
  `situacion_familiar` answers conjunta eligibility.
- Per-CCAA deducciones autonómicas (Andalucía, Canarias,
  Cantabria, Extremadura, Madrid, Cataluña, Comunidad Valenciana,
  etc.) — each CCAA has its own DEDUCCION_PAREJA_DE_HECHO_* axis
  the calculation chain must read.
- Mínimo por descendientes / monoparental supplement (Art. 81 bis
  LIRPF): `monoparental_required()` already excludes
  `PAREJA_HECHO_REGISTRADA` — derivation must feed this.

### M200 + M714 cross-references

M200 (IS) is the IS contribuyente surface — pareja de hecho is a
natural-person concept, no direct impact. M714 (Patrimonio) joint
filing eligibility mirrors M100 unidad-familiar so the same
derivation feeds it. M650 (ISD) succession ordering treats
registered pareja de hecho as cónyuge in several CCAAs — out of
scope for this Step but worth a follow-up audit.

### Required legal_refs (CCAA-level pareja-de-hecho establishment)

- `ley-madrid-11-2001`: Ley 11/2001 Madrid (BOE-A-2002-3776)
- `llei-cataluna-25-2010`: Llei 25/2010 del llibre segon CCCat
- `ley-andalucia-5-2002`: Ley 5/2002 Andalucía (BOE-A-2003-1633)
- `ley-pais-vasco-2-2003`: Ley 2/2003 País Vasco (foral, advisory
  for IRPF common)
- `ley-comunidad-valenciana-5-2012`: Ley 5/2012 CV
  (BOE-A-2012-13883)
- Plus equivalents for Canarias, Aragón, Asturias, Baleares,
  Extremadura, Galicia, Cantabria, Castilla-León,
  Castilla-La-Mancha, La Rioja, Murcia

Per-CCAA Renta deduction ley text already partially present under
`aeat/modelos/100/.../deducciones/` — the pareja-de-hecho gate
clauses need `legal_refs` pointing to both the
registry-establishing law AND the IRPF deduction article.

## Source

Subagent ground-truth discovery 2026-06-03 against #627 W09.P41.S346
(R9-ANDREA-HIGH). Cited file:line evidence:

- `src/aeat/domain/contribuyente/_renta_codes.py:28-34, :110-158`
- `src/aeat/_data/registry/aeat/user_profile/schema.toml:127-150, :776-782`
- `src/aeat/application/wizard/_verifier.py:140`
- corpus disenos-registro properties for M100 2025

---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-18-schema-hardening-adr]]"
---

# `schema-hardening` audit: enrollment campaign queue for M100 and M200

## Status (2026-05-19)

24 of 26 modelos at 100% role coverage on the casilla layer.
Two modelos remain unenrolled at scale:

| modelo | unroled | total | % roled |
|--------|--------:|------:|--------:|
| M100   | 10,639  | 11,302 | 5.9% |
| M200   | 1,002   | 1,004  | 0.2% |

These two campaigns are not in-scope for the casual rollout
pattern that delivered the other 24 modelos. Each requires a
dedicated classification pass because the casilla taxonomy is
not derivable from id + label alone — they have hundreds of
domain-specific concepts (CCAA deductions in IRPF, LIS
liquidacion stages in IS).

## Campaign A: M100 IRPF (10,639 casillas)

The 663 already-roled casillas cover:

- All identity (NIF/NIE/CIF) atoms across 6 revisions
- Country / postal / municipality / IBAN atoms
- Filing-year and key financial roles (base_imponible_irpf,
  resultado_ingresar_o_devolver_irpf, etc.)
- M100 NIF role-classification agent output applied (see prior
  audit) — every Spanish-NIF casilla in M100 now carries its
  role across all 6 revisions

The remaining 10,639 unroled casillas are organised by
declaration section. The form structure is:

- toma_datos_ampliada — input-side declaration sections
  (rendimientos del trabajo, actividades economicas, capital
  mobiliario / inmobiliario, regimenes especiales, reducciones
  base imponible)
- resultados — computed and CCAA-specific deduction sections,
  including ~19 CCAA-autonomic deduction trees, each with
  multiple sub-sections per autonomous community

The CCAA deduction sub-trees dominate the casilla count. Each
CCAA has its own legally-distinct deduction set; many share
structural patterns (NIF de arrendador / propietario / etc.
already roled, plus amount / cap / requirement-flag triplets).

### Recommended approach

1. **Classification audit (split per section family).** Dispatch
   a swarm of sonnet agents, one per section family:
   - W-1: toma_datos_ampliada > rendimientos
   - W-2: toma_datos_ampliada > regimenes_especiales
   - W-3: toma_datos_ampliada > red_base_imponible
   - W-4: resultados > calculo_impuesto_res (cuota + minimos)
   - W-5: resultados > deduccion_autonomica_res > [CCAA cluster]
     (further sub-split by CCAA: andalucia / aragon / canarias /
     etc. — 19 sub-agents)
   - W-6: resultados > anexo_a_res / anexo_b_res / anexo_c_res
   - W-7: resultados > datos_adicionales_res

   Each agent reads its scope, emits a per-id-to-role mapping
   honouring the canonical taxonomy reference doc (and
   proposing new role names where corpus reuse exists). Output:
   `.vault/audit/2026-05-XX-schema-hardening-m100-<section>.md`
   per agent.

2. **Bulk role application.** Per-section script applies the
   audit's role assignments to all 6 revisions of M100 in one
   commit per section family.

3. **Hard-flip pattern audit.** After each section family
   lands, sweep for label patterns where corpus coverage is now
   100% and add them to `_REQUIRED_ROLE_LABEL_PATTERNS`.

### Effort estimate

- 7-15 dispatch sessions for classification audits
- 7-15 corresponding bulk-apply commits
- One closing taxonomy refresh + one closing acceptance audit

## Campaign B: M200 IS (1,002 casillas)

Single-revision (2024-y-siguientes) M200 file. The 2 already-
roled casillas are `00027` (base_imponible_negativa_is) and
`00599` (resultado_ingresar_o_devolver_is). Everything else
unroled.

M200 organises around LIS stages:

- Page 01: identification + tipos / cnae
- Page 011: Liquidacion (cuota integra, deducciones, cuota
  liquida, retenciones, pagos fraccionados, cuota a ingresar)
- Pages 011b-018: Detalle correcciones contables al resultado
  (article-by-article LIS corrections, dotaciones, valoraciones)
- Pages 019-022: Bases imponibles negativas y compensaciones
- Pages 023-034: Reservas (capitalizacion, nivelacion, etc.)
- Pages 035-042: Tributacion conjunta / regimes / consolidacion
- Pages 043+: Anexos (deducciones I+D+i, cooperativas, etc.)

### Recommended approach

1. **Classification audit (split per page family).** Same
   pattern as M100: one sonnet agent per page family. Likely
   8-12 audits total.

2. **Bulk role application.** Per-page script applies the
   audit's role assignments.

3. **Roles to coordinate with existing taxonomy.** Many M200
   concepts overlap with M202 (LIS pago fraccionado). The
   role naming should align (e.g., M202 `is_pf_mod_40_3_*`
   roles correspond to M200 base-imponible / cuota sections).
   The audit pass must explicitly check the existing role
   taxonomy before proposing new names.

### Effort estimate

- 8-12 dispatch sessions for classification audits
- 8-12 corresponding bulk-apply commits
- One closing taxonomy refresh

## Coordination notes

- Both campaigns can run in parallel — they touch different
  modelo directories so cross-commit conflict risk is zero.
- The role taxonomy reference doc must be refreshed after each
  major landing so future modeller decisions can reuse names.
- The cross-revision drift validator is fatal at registry load,
  so any per-section bulk-apply that produces inconsistent
  shapes across the 6 M100 revisions will fail. Per-id role
  assignments in audit docs must explicitly carry through
  every revision the id appears in.
- The hard-flip required-role pattern set grows as each
  section's corpus coverage hits 100%. The validator gate
  catches new modeller drift the moment a section's coverage
  is provably complete.

## Acceptance

This doc serves as the durable cross-session queue for the
two remaining enrollment campaigns. Subsequent sessions can
pick up M100 or M200 work without re-deriving the scope.
The TaskList (in-session) carries the same campaigns as
ID 13 and 14; this vault doc is the persistent record.

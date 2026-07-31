---
tags:
  - '#research'
  - '#autonomic-deduccion-auto-trigger'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:2a25dece55cd2f3690d9d4bbec62568be7462ae1db0863ac3fc48991ece918cf'
related:
  - '[[2026-06-04-m100-marriage-date-axis-adr]]'
  - '[[2026-06-19-m100-dependent-modelo-applicability-adr]]'
  - '[[2026-05-08-renta-cuota-integra-autonomic-scale-adr]]'
---

# `autonomic-deduccion-auto-trigger` research: `autonomic deduccion auto-trigger framework`

Grounds issue #550 (P1, systemic): no Modelo-100 autonomic-deducción box is auto-computed — every comunidad's `deduccion_autonomica_res` box is a manual-input casilla. The Madrid nacimiento/adopción deducción and the `adoption_date` axis both exist but nothing connects them. This research maps the existing compute machinery, the regulatory shape of the Madrid nacimiento/adopción deducción (the worked first case), and the shared primitives a faithful auto-trigger needs, so the ADR can decide the framework. Confidence: high on the code surfaces (read at HEAD) and the current Madrid figure (bundled 2025 manual); medium on the completeness of the unidad-familiar spouse-income data the app currently holds.

## Findings

### F1 — Current state: madrid_res deducción boxes are pure manual input

In revision `2025`, `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/1041-1039.toml` declares casilla `1039` "Por nacimiento o adopción de hijos" (`section = ["resultados", "deduccion_autonomica_res", "madrid_res"]`, `semantic_role = "irpf_deduccion_madrid_nacimiento_adopcion"`), and `1042-1040.toml` declares `1040` "Por adopción internacional de niños". Neither carries a `binding` or a `formula` `target_casilla_id` — they are operator-typed inputs. `legal_refs = ["ley-35-2006:art-77", "orden-hac-277-2026:art-3"]` (art-77 framework grounding, per the `casilla-grounding-corrects-actividades-default-by-section` rule for autonomic deductions).

The autonomic-deducción formulas that DO exist in `2025/formulas/` (`0002-renta-2025-deduccion-cultural-autonomica-50-porciento` targeting casilla `0551`, plus ceuta/melilla and alquiler) are the art-68-shared 50 % state/autonomic split deductions, NOT the comunidad-specific deducciones. The comunidad-specific set (`madrid_res`, `andalucia_res`, ...) is entirely manual. #550's assertion holds: zero comunidad-specific autonomic-deducción boxes are auto-computed.

### F2 — The canonical compute mechanism already exists: profile-derived-fact injection plus registry formula/binding

`src/aeat/application/modelo/_profile_binding.py` is the load-bearing precedent. It walks every `source = "profile"` registry binding the revision declares and projects the matching profile fact into one of three engine channels (`date_binding_values`, `enum_binding_values`, Decimal `binding_values`). Crucially, it injects **derived** facts that no raw profile fact holds, as synthetic keys the same channel resolver then picks up:

- `_inject_derived_marriage_facts(fact_index, filing_year)` computes `marriage_full_year` / `marriage_month_start` / `marriage_month_end` from `renta_taxpayer.marriage_date` plus the snapshot's `filing_year` (the matrimonio-sobrevenido date-axis).
- `_inject_derived_family_facts(fact_index, filing_year)` reconstructs per-descendant birth dates from `renta_family.descendiente.{n}.birth_date` facts and writes `renta_family.descendientes_menores_3_2024` (a count) — the Art. 58.3 menores-3 supplement.
- `_inject_derived_state_attribution_facts` projects an enum (`jurisdiction_scope`) onto a synthetic Decimal ratio key consumed by a bound casilla.

This is exactly the shape an autonomic-deducción auto-trigger needs: the per-descendant date-window / convivencia logic that no casilla can express is a Python derived-fact injector; the injected count/amount then feeds a registry binding or formula through the existing Decimal channel. The mechanism is enrolled in the live calculate mesh (satisfies `no-dormant-source-resolvers`); a new injector rides the same path with no new source kind.

### F3 — The family/descendant model already carries every signal the Madrid deducción needs

`src/aeat/domain/contribuyente/family.py` `DescendantInfo` carries `birth_date`, `adoption_date` (validated ≥ birth_date and ≤ today), `convive_con_contribuyente`, `custodia_compartida`, `nif`. `_entry_date()` already returns `adoption_date if present else birth_date` — the exact "fecha de nacimiento o adopción" the deducción window keys on. `RentaFamilyProfile` exposes derived helpers per filing year (`descendientes_menores_3_year_end`, `descendientes_eligible_minimum`, `deduccion_maternidad_0611`, `incremento_guarderia_0613`) — the natural home for a `madrid_nacimiento_adopcion_count(filing_year)` companion.

Persistence is already wired: `src/aeat/domain/contribuyente/_descendant_facts.py` stores `renta_family.descendiente.{n}.adoption_date` (ISO-8601) and `.convivencia` facts and reconstructs them. The CLI capture flag `--descendiente NACIMIENTO=...,ADOPCION=...,CONVIVENCIA=...` (`parse_descendiente_flag`) exists. No new profile-capture axis is required for the Madrid adopción slice — the audit-noted "adoption date absent" gap (`2026-05-27-ines-cli-testimonial-audit`) was closed by the DescendantInfo/adoption_date work; what is missing is only the trigger that consumes it.

### F4 — CCAA residence is already a typed dispatch key

`2025/bindings/0008-renta-2025-profile-tax-residence-ccaa.toml` is a `source = "profile"` binding with `typed_enum = "CCAA"` projecting `TaxResidenceProfile.ccaa`. This is the gate that scopes a comunidad-specific deducción to residents of that comunidad — consumed as an enum dispatch key (the `enum_binding_values` channel), the same way `lookup_bracket_by_ccaa` dispatches the autonomic scale (`2026-05-08-renta-cuota-integra-autonomic-scale-adr`). The framework needs no new residence signal.

### F5 — Regulatory shape of the Madrid nacimiento/adopción deducción (current, bundled 2025 manual)

Source: `src/aeat/_data/corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf.extracted.json`, Comunidad de Madrid, "Por nacimiento o adopción de hijos", Normativa Arts. 4 y 18.1 del Texto Refundido DL 1/2010 de 21 octubre:

- **Cuantía: 721,70 € por cada hijo nacido o adoptado** (regulación vigente desde 1-1-2023). **For births/adoptions before 1-1-2023 the amount is 600 €** — #550's audit €600 is the pre-2023 figure and is STALE for a 2023+ event.
- **Partos/adopciones múltiples:** the first period's amount is increased by 721,70 € per child.
- **Ámbito temporal:** applies in the period of birth/adoption AND in each of the two following periods (a 3-year window keyed on the entry year).
- **Requisito:** only parents who cohabit with the child (`convivencia`).
- **Prorrateo:** when the child cohabits with both parents and they file individually, the amount is split equally between the two declarations (÷2).
- **Doble límite de renta** on the sum of casillas **[0435]** (base imponible general) **+ [0460]** (base imponible del ahorro):
  - Contribuyente: ≤ 30.930 € (individual) / ≤ 37.322,20 € (conjunta).
  - Unidad familiar (aggregate of all members' bases): ≤ 61.860 €.
  - The unidad-familiar aggregation rules (Art. 82.1.1ª conyugal vs 82.1.2ª monoparental/no conyugal) are spelled out in the manual: for a conyugal unit, aggregate both spouses' plus the minor children's bases; in tributación conjunta the joint declaration's base is used.

Both casillas exist and are computed in the 2025 revision (`0502-0435.toml`, `0527-0460.toml`), so a registry formula can reference `0435` + `0460` directly for the contribuyente double-limit gate. The unidad-familiar aggregate (spouse + children bases) is NOT on this filer's own declaration — it is the one term the registry formula cannot reach and that a Python derived fact (or an operator-supplied value) must supply.

The international box (`1040`, Madrid Art. 5) carries the separate **+50 % uplift** rule ("cuando el niño adoptado conviva con ambos padres adoptivos el importe se incrementará en un 50 %") — a framework axis, but a distinct deducción deferred out of the first slice.

### F6 — The registry formula op vocabulary already supports the double-limit gate and CCAA-scoped amount

The 2025 M100 formulas already use `if_then_else`, `greater_than`, `greater_equal`, `equal`, `min`, `max`, `multiply`, `percent`, `lookup_bracket_by_ccaa`, `lookup_parameter_by_entity_type`, and `age_at_year_end` (a date-aware op — the marriage/menores-3 date channel). A formula targeting casilla `1039` can therefore express: `if (0435 + 0460 ≤ contribuyente_limit) and (unidad_familiar_base ≤ 61860) then eligible_count × per_child_amount / prorrateo else 0`, with the per-child amount and the limits modelled as CCAA-scoped registry `parameters` (the `parameters/` directory already holds CCAA-scoped autonomic-scale values such as `0010-renta-2025-escala-autonomica-andalucia-base-general`). No new op is required.

### F7 — Grounding and honesty constraints that bind the first slice

- `casilla-grounding-corrects-actividades-default-by-section` and `2026-06-14-legal-grounding-centralization-audit` (V21): autonomic deducciones ground to the LIRPF framework `ley-35-2006:art-77` (cuota líquida autonómica), keyed by the renumbering-immune section tag `madrid_res`, with the specific comunidad law as a secondary ref.
- `registry-calculation-legal-grounding`: 721,70 is a regulatory value; its binding provision (Arts. 4 y 18.1 DL 1/2010, and the disposición that set 721,70 from 2023) MUST be cited on the value's `legal_refs` and defined in the legal catalogue with a `corpus_ref` resolving to real text, not the framework art-77 alone.
- `legal-grounding-verifies-bundled-authoritative-corpus`: 721,70 is confirmed against the bundled 2025 manual, but the bundled manual is not infallible for an AMOUNT — cross-check against live BOE/AEAT before operator re-stamp; the legal entry ships `reviewed_by` as agent-prepared pending operator confirmation.
- `aeat-safety-legal-gates`: ground current figures (721,70, not 600); never invent.
- `no-silent-under-declaration`: the gate exists to stop a positive-input/zero-output silent grant. For a **deducción** (which reduces tax) the symmetric hazard is an over-claim the taxpayer is not entitled to; the auto-trigger must surface eligibility explicitly (a Notice), never silently apply an unverified deducción.
- `one-aggregation-path-pull-equals-calculate` and `registry-revision-content-inline-or-fragmented`: the 2025 revision is fragmented; the casilla must produce the same value on the calculate and Sheets-pull paths (the derived-fact injector runs on both).

### F8 — Prior art for the mechanism decision

`2026-06-04-m100-marriage-date-axis` is the closest date-axis precedent, but its ADR is a curation-only alignment record; the real implementation is the `_inject_derived_marriage_facts` path in F2. `2026-06-19-m100-dependent-modelo-applicability-adr` establishes that M100 applicability signals are registry/profile-grounded with a fail-closed default and are registry-authoritative, not schedule-derived — the same discipline applies to a deducción-eligibility gate (fail-closed: absent adoption/convivencia data → deducción not auto-applied). `2026-05-08-renta-cuota-integra-autonomic-scale-adr` establishes the CCAA-scoped parameter + `lookup_bracket_by_ccaa` dispatch the amount/limit parameters reuse.

### F9 — What is NOT yet verified (bounded honesty)

- Whether the app persists a spouse's base imponible (the other unidad-familiar member's 0435/0460) anywhere retrievable for the unidad-familiar 61.860 aggregate. If not, the unidad-familiar limit term is operator-supplied, or the auto-trigger is advisory-only when it cannot be evaluated. Not resolved in this pass.
- The exact disposición that fixed 721,70 from 2023 (the manual cites Arts. 4 y 18.1 DL 1/2010 and a disposición final quinta) — the legal-catalogue entry must name the modifying provision precisely per `registry-calculation-legal-grounding`; the precise BOE id is a plan-phase lookup, not settled here.
- Whether any other comunidad's nacimiento/adopción deducción shares the exact double-limit shape (the framework generalises, but the per-CCAA parameter set is a later enrollment, not verified here).

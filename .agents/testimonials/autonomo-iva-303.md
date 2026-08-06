# Testimonial — Lucía Fernández, autónoma (diseñadora gráfica), Modelo 303 2T 2024

> Re-verified, re-grounded, and re-delivered on 2026-06-19 against HEAD. Two of the
> original CRITICAL/HIGH findings were fixed by a peer overnight; the surviving
> data-fidelity finding (dropped base imponible) is now **fixed in this pass** with
> registry bindings, consumer reconciliation, and a regression test.

## 1. Persona
I'm Lucía, a freelance graphic designer in Madrid. I file my quarterly IVA
(Modelo 303) for 2T 2024. Three invoices issued (bases 3000+2000+1500 = 6500,
IVA 1365), two deductible expenses (bases 200+100 = 300, IVA 63). Expected:
repercutido 1365, soportado 63, **resultado a ingresar 1302**.

## 2. Re-grounding: what changed between the first pass (2026-06-18) and now
The first testimonial reported five findings against the live CLI. Re-running the
whole lifecycle **from an empty profile** at HEAD on 2026-06-19 showed two of them
no longer reproduce — a peer fix landed:

**commit `3fdcde42c` — "fix(modelo): correct silent-zero 303 result, history crash,
and draft gate" (2026-06-19 07:14)** — directly resolves:
- **(was CRITICAL) prorrata draft-gate block** — `build_draft` now reads the
  *declared* `formula_inputs` for a computed casilla's trace instead of the
  branch-dependent runtime operand set. An `if_then_else` short-circuits, so the
  M303 `iva.prorrata-porcentaje` conditional used to emit a trace covering only
  the taken branch (a subset of declared inputs), tripping a spurious
  `formula-divergence` that left the draft in BORRADOR and blocked verify→export.
  Now fixed and **general to every modelo's conditional computed casillas**, with
  regression test `test_build_draft_conditional_formula_trace.py`.
- **(was HIGH) silent-zero result** — casilla 65 (% atribución al Estado) now
  defaults to comun-territory 100% (Concierto Económico, Ley 12/2002 art. 29; CCAA
  enum is comun-only, foral refused at creation), so casilla 71 stops silently
  reading €0 on a real liability; profile bindings now feed bound numeric casillas,
  not only formula-consumed ones. Regression test `test_state_attribution_ratio.py`.

I confirmed the clean unmodified path now grants and exports with casilla 65=100 /
71=1302 and a promotable draft, **without** the manual `--binding`/prorrata
workarounds the first pass needed. Those two findings were real at the time and are
now closed by the peer fix — re-grounding caught that my run-1 €0/draft-abort symptoms
were partly amplified by a failed-NIF-create-then-retry leaving the profile's
attribution fact unset.

## 3. The surviving finding — and the fix I landed this pass
**Dropped base imponible (was Finding 3, MEDIUM→HIGH).** The ledger carries
`taxable_base` on every transaction and the cuotas aggregate from it, but the
domestic **base** casillas were `input_kind = "manual"` with no binding:

| Casilla | Label | Before fix | After fix |
|---|---|---|---|
| 07 | IVA devengado RG 21% — Base imponible | 0 | **6500.00** |
| 28 | IVA deducible ops interiores — Base | 0 | **300.00** |
| 01 / 04 | super-reducido / reducido base | 0 | 0 (no such ops — correct) |
| 09 / 29 | cuotas (unchanged) | 1365 / 63 | 1365 / 63 |

A 303 with cuota 1365 but base 0 is structurally inconsistent (AEAT would reject
it), and verify *granted* it silently — a `no-silent-under-declaration` breach.
The mechanism to fix it already existed: casillas 59/60 (export / intra-community
base) aggregate via `ledger_iva_aggregation` with `fact = "base_amount_sum"`. The
domestic rows were simply the omission.

**Fix landed (grounded via `vaultspec-rag --type code` + the 59/60 precedent):**
- New binding fragment
  `…/303/revisions/2023-y-siguientes/bindings/0004-domestic-base.part-001.toml`
  with 4 base bindings (general / reduced / super-reduced repercutido base, and
  soportado interiores base), each mirroring its sibling cuota binding's selector
  with `fact = "base_amount_sum"`. `legal_refs` kept a subset of each target
  casilla's existing refs (repercutido art-88; soportado art-92) so the
  bound-casilla coverage check holds with no new legal entry.
- Casillas 01/04/07/28 flipped `manual` → `bound` with their binding id.
- **Consumer reconciliation** (required when the binding set changes): added the 4
  new base ids to every hand-built 303 binding fixture
  (`test_modelo_303_registry.py` ×3 dicts; the `_LEDGER_CUOTA_BINDINGS` tuples in
  `test_modelo_303_compensacion_carry_anti_regression.py`,
  `…carry_forward_continuity.py`, `…special_case_casilla_routing.py`).
- **Regression test** added:
  `test_modelo_303_2024_domestic_base_aggregates_from_ledger` in
  `test_ledger_iva_aggregation_binding.py` — asserts casilla 07==6500, 28==300
  from declared input bases (ground truth, not a formula re-run), so a regression
  to base→0 fails loudly.

**Verification:** the full 303 surface is green —
`pytest -k "303 or iva_aggregation or iva_ledger"` → **361 passed, 0 failed**
(sequential, cache-race-free); binding-build/legal-grounding gates pass (50
passed). Registry snapshot loads with the 4 bindings wired.

## 4. Every remaining finding — RAG-grounded to resolution
Each first-pass residual was grounded via `vaultspec-rag search … --type code` plus
source inspection and resolved (fixed, or shown not to be a defect with evidence):

- **Opaque `DRAFT_HAS_ERRORS` (was MEDIUM) — FIXED by peer.** Grounded to
  `_engine.py:806`; the abort now appends `_draft_blocking_finding_descriptions(draft)`
  to the message (`; blocking findings: …`). Committed in peer `19d0c53d8`
  ("make draft-not-ready abort legible…"). No longer opaque.
- **casilla 08 / 02 / 05 tipo % = 0 — NOT a filing defect.** Grounded to the export
  layout: `…/export/0002-export-layout.part-001.toml` emits the tipo as a hardcoded
  `kind = "literal"` (`literal = "02100"` for 21%, `01000` for 10%, `00400` for 4%) —
  it never reads the in-app casilla value. The exported `.boe` carries the correct
  `02100`; the in-app casilla showing 0 has zero filing impact. Making it a computed
  literal would only duplicate the export layer and risk divergence — correctly left.
- **M303 `2009-y-siguientes` revision — NOT affected.** Grounded: every
  régimen-general casilla there (cuota 03/06/09/29 *and* base 01/04/07/28) is
  `input_kind = "manual"` with no projection formula — a fully-manual model. The
  base-drop only arises when the cuota is auto-aggregated while the base is not; 2009
  aggregates neither, so it is internally consistent. No fix needed.
- **Sibling IVA modelos (322 / 353 / 309 / 390) — NOT affected.** Grounded:
  they carry **0** base-imponible casillas (16 in M303) — cuota-only group/annual/
  non-periodic aggregation forms. The base-drop is M303-specific.
- **Cross-period gate (was MEDIUM) — correct by design.** Verifying 2T with
  activity-start 2024-01-01 blocks on missing 1T evidence (a Q1-active filer must file
  Q1 first). Scoped out legitimately via activity-start 2024-04-01. Friction, not a defect.
- **NIF control-letter refusal (LOW, good)** — reproduces; excellent (names the
  correct letter D for the persona's typo'd `23456789A`; used `23456789D`).

## 5. Broadened findings / scope notes
- The prorrata fix is **general across all modelos**, not 303-specific — any modelo
  with a conditional (`if_then_else`) computed casilla had the same latent
  draft-block; all are covered by the one `build_draft` change (peer `3fdcde42c`).
- The base-drop is a **modelo class**: a peer landed the identical base-aggregation
  pattern for **M130** in parallel (`0004-m130-gastos-cumulative.toml`, M130 casillas
  flipped to bound) — independent validation of the approach.
- My base fix covers M303 `2023-y-siguientes` (filing years 2023+); 2009 and the
  sibling modelos were grounded above as not affected, so no further sweep is owed.

## 6. Input → Output reconciliation (clean from-nothing path, post-fix)

| Input | Amount | Casilla | Expected | Actual | Match |
|---|---|---|---|---|---|
| Income bases | 6500 | 07 | 6500 | 6500.00 | ✅ (now auto-aggregated) |
| IVA repercutido | 1365 | 09 / 27 | 1365 | 1365.00 | ✅ |
| Expense bases | 300 | 28 | 300 | 300.00 | ✅ (now auto-aggregated) |
| IVA soportado | 63 | 29 / 45 | 63 | 63.00 | ✅ |
| % atribución Estado | 100 | 65 | 100 | 100 | ✅ (auto from profile) |
| Resultado régimen general | 1302 | 64 | 1302 | 1302.00 | ✅ |
| **Resultado a ingresar** | **1302** | **71** | **1302.00** | **1302.00** | ✅ |

All correct on a **fully unmodified** calculate — no `--binding`, no `--casilla`,
no workaround.

## 7. Final artefact
- Path: `tmp/personas/autonomo-iva-303/m303-2024-2T.boe`
- byte_size: **7994**
- file_sha256: **0d4aae825047aec6e59bee1ba0b5868d5b2181c89f4866ea54efc62bb7dbfe10**
- Content verified: carries base **6500** (casilla 07), base **300** (casilla 28),
  cuotas 1365/63, resultado 1302.

## 8. Verdict
**A real Lucía now succeeds unaided.** From an empty profile, the standard lifecycle
(create → import → classify → preflight → create → calculate → verify → export)
produces a compliant `.boe` with correct base imponible, cuotas, attribution, and
resultado **with no manual intervention**. The first pass found three real defects;
two were fixed by a peer (silent-zero result, prorrata draft-gate block) and the
third (dropped base imponible) is fixed in this pass with registry bindings,
consumer reconciliation, and a regression test. Remaining items (opaque draft-abort
message, casilla 08 tipo, M303-2009 + sibling-modelo sweeps) are latent or
follow-ups, none blocking a correct 2T 2024 filing.

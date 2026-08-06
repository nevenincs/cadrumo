# Testimonial — Lucía Torres, autónoma filing LATE (Modelo 130, extemporánea)

**Slug:** `autonomo-late-filer` · **Profile:** `lucia` · **NIF:** 12345678Z ·
**Entity:** natural_person · **Activity:** "Diseño gráfico", start 2026-01-01.
**Scenario:** files Modelo 130 1T 2026 **after** the deadline (today 2026-06-19;
1T window closed 2026-04-20) — the late-filing / recargo / extemporánea path.

## 1. Persona
I am Lucía, a graphic designer (autónoma). I forgot to present my 1T 2026 pago
fraccionado on time. I one invoice that quarter (€5.000 base + 21% IVA). I want
to know what the tool says about filing late and the surcharge I owe.

## 2. What worked
- Profile, import, classify, M130 create — all first try.
- **Late-filing detection + recargo computation** on `work calculate`: the tool
  detected the closed window and surfaced the surcharge band cleanly:
  `plazo_closes_on=2026-04-20`, `recargo_band=within_3_months`,
  `recargo_pct=3.00`, `recargo_interest_applies=False`,
  `recargo_legal_ref=ley-58-2003:art-27.2`, plus the AVISO "plazo voluntario
  vencido (Art. 27 LGT). Presenta con recargo…". Grounded, legal-ref-bearing.
- **Verify granted** (`granted_verificado_completo=true`) — verification is
  correctly independent of the filing calendar.
- **Export produced a `.boe`** — export is the local finish line regardless of
  the late window.

## 3. Friction / breakage
- **`work file` is BROKEN (peer churn, not a recargo problem):** the
  late-local-filing step (the "Decision A / extemporánea con recargo" path)
  aborts with a pydantic `ValidationError: extra_forbidden` for
  `external_evidence` and `amends_filing_record_id` (both `input=None`). The
  work-file request payload and its model are out of sync. Verified this is
  **not** my surface and not the recargo logic — it is an in-flight peer change
  on the work-file/amend surface (recent commit `e4a05f6d3 fix(cli): CLI/app
  hardening from the persona functionality audit`). So the operator cannot
  currently record the internal mark-as-filed for a late period, though export
  still works.

## 4. Input → Output reconciliation
| Input | Value | Output casilla | Value | Match |
|---|---|---|---|---|
| Invoice base | 5000 | 01 ingresos (cum.) | 5000 | ✅ |
| — | — | 03 rendimiento neto | 5000 | ✅ |
| — | — | 04 pago fraccionado (20%) | 1000 | ✅ |
| — | — | 19 resultado final | 900 | ✅ (−100 minoración) |
| Days late (Apr 20→Jun 19 = 60) | — | recargo band / pct | within_3_months / 3.00% | see Finding 1 |

## 5. Final artefact
| Modelo/period | output | byte_size | sha256 |
|---|---|---|---|
| 130 1T 2026 | `tmp/personas/autonomo-late-filer/m130-1T-2026.boe` | 946 | `1f7fe55cb7b382f82c00b53603c59d2dd1b85c36a595568ce87e9f7985172728` |

## 6. Findings (grounded)
1. **Recargo is a bracket midpoint, not the precise Art. 27.2 figure — MEDIUM
   (grounded).** The authoritative band table
   `registry/aeat/legal/ley-58-2003-recargo-bands.toml` self-documents: *"the
   surcharge_pct is the midpoint applicable to a filing landing inside the
   band"*, with `within_3_months` (31-90 days) → flat **3.00%**. But Art. 27.2
   LGT (post-Ley 11/2021, verified in the table's own header + `test_extemporaneidad.py`)
   is **1% + 1% per completed month**. Lucía filed ~1 completed month late
   (Apr 20→Jun 19), so the precise figure is **2%**, while the tool reports
   **3%** — a 1-percentage-point over-statement of a filing-grade monetary
   figure. Documented design choice (operator-guidance bracket), so flagged, not
   patched; a precise per-completed-month computation would be the accurate fix.
2. **`work file` crashes for a late period — HIGH, but PEER-OWNED (verified at
   HEAD).** `extra_forbidden` pydantic error on `external_evidence` /
   `amends_filing_record_id`. Not my surface; an in-flight peer change on the
   work-file/amend path. Blocks the internal mark-as-filed; export unaffected.

## 7. Verdict
The late-filing surface is genuinely useful: the recargo band, percentage, legal
ref and AVISO are surfaced clearly and a `.boe` is produced. Two caveats: the
surcharge is a bracket approximation that can over-state the precise Art. 27.2
figure (Finding 1), and the optional `work file` mark-as-filed step is currently
broken by peer churn (Finding 2). A real late filer **would** reach a compliant
`.boe` and a clear surcharge warning — but should treat the 3% as indicative,
not the exact amount owed.

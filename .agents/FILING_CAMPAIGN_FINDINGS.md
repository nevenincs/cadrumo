# Filing-persona campaign — consolidated findings (coordinator synthesis)

Date: 2026-06-18 · Branch: `chore/eliminate-shims` · Coordinator: filee-personas session
Method: each persona started from an empty profile, created a profile with a custom
password (isolated `AEAT_SECRET_STORE_DIR` + `AEAT_SECRET_PASSPHRASE`, file backend),
imported financial data, classified, and drove the modelo lifecycle to a `.boe` export
against the **live** CLI. Coordinator independently re-verified the cross-cutting root
causes against source at HEAD. Full per-persona detail in `.agents/testimonials/<slug>.md`.
(Companion to the prior documentation-persona ledger in `.agents/CAMPAIGN_FINDINGS.md`,
whose MAJOR "missing-binding remediation misleads" finding corroborates H1 below.)

## Personas run (batch 1)
| Slug | Persona | Target | `.boe`? | Headline |
|---|---|---|---|---|
| autonomo-iva-303 | Lucía, designer | M303 2T/2024 | YES (after 4 manual workarounds) | engine numbers correct (1365/63/1302); export needs undocumented prorrata workaround + manual casilla 65/07/28 |
| autonomo-130-cumulative | Marco, €20k/yr no expenses | M130 ×4 → M100 | 1 of 5 | cross-period carry arithmetic correct but pipeline deadlocked; only 1T exports |
| iva-crossperiod-303 | Pablo, IVA compensación | M303 1T→2T | 1 of 2 | per-period correct; €420 compensación does NOT carry 1T→2T (945 not 525) |
| gestor-multiclient | Asesoría, 2 clients | M303 + M130 | 1 of 2 | **multi-profile isolation PASS**; M130 exports, M303 blocked (casilla 65) |
| renta-100-fullyear | Elena, salary+rental | M100/2024 | NO | M100 unreachable; 1,882/2,059 casillas manual; silent resultado-chain drop |
| sociedad-200-is | TechVentura SL | M200/2024 | NO | IS rate engine correct (23% micro-empresa → cuota íntegra 18,400 ✅) but ledger P&L not aggregated → would silently file €0; cuota íntegra never reaches cuota a ingresar (00599=0) |

## What is SOUND (verified working)
- **Profile + custom password + encrypted storage**: works once `AEAT_SECRET_STORE_DIR`
  is isolated per profile (see env note). Custom passphrase unlocks the bucket.
- **Multi-profile isolation**: gestor confirmed zero cross-contamination at ledger AND
  modelo level, both switch directions. `config switch` is clean and gestor-friendly.
- **Ledger import + classify + preflight**: semicolon/Spanish-CSV import is robust;
  preflight correctly demands taxable_base/iva_rate/iva_amount facts.
- **Calculation engine arithmetic is CORRECT** everywhere exercised:
  - M303 Lucía: repercutido 1365, soportado 63, resultado 1302
  - M303 Pablo 1T: −420 + compensación-generada 420; 2T régimen general 945
  - M130 Marco: cumulative income 5000→20000; pago 20%; carry casilla 05 = Σ prior (900/1900/2900)
  - M100 Elena (draft only): base 36000, cuota líquida 7453.10, retención 4500, resultado 2953.10 (internally consistent; NOT oracle-checked)
- **NIF control-letter validation**: excellent — names the exact correct letter on refusal.
- **`.boe` fichero export**: valid `<T...>` BOE format for every verified revision.

## CRITICAL findings
**C0 — Cross-period observation deadlock (ROOT CAUSE; unifies IVA-carry + M130 + M100 fold-in).**
`work file` (WorkflowPurpose.FILE, `application/workflow/_engine.py:406-475`) computes the
obligation schedule as-of `today`. For any past/overdue period the obligation is not
*pending* → `obligation is None` → `NO_PENDING_OBLIGATION` abort (or `DEADLINE_PASSED`).
`work file` is the ONLY step that persists the filed observation
(`persist_filed_revision_observation`) the next period's cross-period carry binding reads.
So every binding cross-period aggregation — M130 pagos-fraccionados carry, M303 compensación
carry, M100 M130-fold-in — computes correctly but is operationally unreachable for any
historical reconstruction or late filing. Highest-impact defect; safety-adjacent gate →
needs an ADR, not a blind patch. Proof: 130-cumulative exports only 1T; iva-crossperiod
exports only 1T; the €420 never reaches casilla 110.

**C1 — Modelo 303 un-exportable for every CLI-created profile (no `jurisdiction_scope` source).**
casilla 65 (% atribuible al Estado) derives from `tax_residence.jurisdiction_scope`, which
appears ONLY in `application/modelo/_profile_binding.py` (the consumer) — confirmed at HEAD:
no `profile create`/`edit` flag and no wizard writes it. Absent → casilla 65=0 → casilla 71=0
(silent-zero) → DRAFT_HAS_ERRORS. Workaround: `--binding modelo-303-profile-state-attribution-ratio=100`.
Corroborated by gestor (Ana), autonomo-iva-303, iva-crossperiod-303, prior `modelo-303.md`.
**Best first fix**: operator-settable `jurisdiction_scope` enum (common_regime/foral_unsupported)
on profile create/edit + wizard, default territorio común.

**C2 — Modelo 303 prorrata-porcentaje formula-divergence ERROR blocks export for fully-taxable autónomos.**
A draft ERROR finding on `iva.prorrata-porcentaje` keeps the revision in BORRADOR; only an
undocumented prorrata-volume workaround escapes. (autonomo-iva-303) — needs HEAD confirmation.

**C3 — Modelo 100 unreachable for a normal salary+rental taxpayer.**
verify raises ~33 blocking `cross_period_dependency_unclean` demanding justificante evidence
for withholding/instalment modelos (111/115/123/130/131/193) an employee never files; no
"not applicable" path; `activity-start-date` scopes only the prior YEAR, not same-year relations.

**C4 — Modelo 100 silent drop of the resultado chain (no-silent-under-declaration violation).**
With income entered but the 130/131 relations unsupplied, casillas 0604/0609/0610/**0670
(resultado de la declaración)** are ABSENT from the revision with only a non-blocking AVISO;
those relation ids are NOT listed by `bindings list --missing` → undiscoverable.

## HIGH findings
- **H1 — No ledger base/expense aggregation into modelo casillas.** M303 leaves taxable bases
  (07/28) at 0 while populating cuotas (cuota-without-base, AEAT-rejectable); M130 drops
  deductible expenses from casilla 02; M100 maps NO ledger income. Operator injects every base
  by hand. Systemic across IRPF+IVA. (corroborated by prior-campaign MAJOR finding.)
- **H2 — `DRAFT_HAS_ERRORS` verify abort surfaces zero findings and persists no report.**
  Operator has no path from refusal to cause. (autonomo-iva-303, gestor)
- **H3 — M200 cuota íntegra does not propagate to cuota a ingresar.** Hand-entered resultado
  contable correctly yields base→tipo→cuota íntegra (18,400 at 23%), but DP200014B:00599
  (cuota del ejercicio a ingresar) stays 0 — a calculation-chain break, not just an input gap. (sociedad-200-is)

## MEDIUM findings
- **M1 — `work dependencies` ignores activity-start-date** (over-reports blockers verify scopes out).
- **M2 — M130 casilla 13 minoración basis** uses the prior-year binding; needs grounding
  confirmation whether AEAT bases it on current-period cumulative rendimiento (casilla 03).
  Registry TOML is otherwise correctly grounded.
- **M3 — date-typed profile bindings unsatisfiable via `--binding`** (decimal-only channel);
  `profile create` won't overwrite, only the interactive `edit` wizard can set them.
- **M4 — mandatory casilla 02 at zero**: zero-expense M130 still blocks verify until `--casilla 02=0`.

## Coordinator env/harness notes
- **Isolation requires `AEAT_SECRET_STORE_DIR` per profile** — default `var/secrets` master-key
  custody is GLOBAL and held stale custody, breaking fresh passphrases. (in HARNESS.md)
- **Tool-output redaction** mangles grep results (digits/keywords → `n`/`l`); read the actual
  file before concluding a registry value is wrong.

## Recommended hardening sequence
1. **C1** (clear-cut, low-risk, highest user value): operator-settable `jurisdiction_scope`
   → unblocks M303 for every autónomo. Additive; aligns with closed-enum-in-core + CLI-hint rules.
2. **H1**: ledger→casilla base/expense aggregation bindings (M303 07/28, M130 02) so the
   pipeline stops silently under-declaring; pairs with C4.
3. **C0** (ADR-gated): allow `work file` (local mark-as-filed) for overdue/closed windows so
   late filers and historical reconstructions can seed the cross-period carry.
4. **C2/C3/C4**: ADR-backed fixes; add a "no obligation applies" path for M100.

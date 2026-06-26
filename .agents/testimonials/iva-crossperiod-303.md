# Testimonial — Cross-period IVA compensación (IVA wallet), Modelo 303 1T→2T 2024

- Persona: **Pablo Serrano**, autónomo (natural_person), activity "Comercio", started 2024-01-01.
  NIF given as `78901234F` (see Finding 8 — wrong control letter, corrected to `78901234X`).
- Goal: file Modelo 303 IVA for **1T 2024** (input>output → negative result, a "cuota a
  compensar" of 420) then **2T 2024** (output>input, 945), and verify the tool carries the
  1T compensación of 420 forward into 2T's "cuotas a compensar de periodos anteriores",
  yielding a final 2T result of **525**.
- Environment: real backend, `uv run --no-sync aeat`, isolated root
  `tmp/personas/iva-crossperiod-303`, custom passphrase, profile `pablo`. No live AEAT;
  local `.boe` export only.

> **RE-AUDIT 2026-06-19 against HEAD `627c093ea`.** Between the first pass (2026-06-18) and this
> re-review, peer commit **`3fdcde42c` "fix(modelo): correct silent-zero 303 result, history
> crash, and draft gate"** landed and **resolves my two CRITICAL/MAJOR single-period findings**:
> the casilla-65 silent-zero (now defaults to común 100%) and the prorrata `formula-divergence`
> that blocked verify (build_draft now uses declared formula_inputs for the conditional trace).
> I re-ran the **entire lifecycle from a clean profile with NO workarounds**: 1T now calculates,
> verifies (`granted_verificado_completo true`), and exports a `.boe` straight through. The
> **cross-period carry findings (#2, #4, #5, #6) were re-confirmed and STILL HOLD** on HEAD.
> Statuses are marked ✅ RESOLVED / ❌ OPEN per finding below.
>
> **FIX PASS 2026-06-19 (grounded via vaultspec-rag).** Two safe, well-scoped bugs were fixed
> in this pass (tests added & green):
> - **#7 opaque `DRAFT_HAS_ERRORS`** — the `BUILDING_DRAFT` workflow abort reported only
>   `status=BORRADOR` and discarded `draft.findings`. It now enumerates the blocking findings
>   (`severity:code (casilla)`) in the abort summary + step details, with a `next_action`
>   pointer (`src/aeat/application/workflow/_engine.py`,
>   `_engine_helpers.draft_blocking_finding_descriptions`; regression
>   `test_draft_not_ready_abort_surfaces_blocking_findings`).
> - **NEW locale leak** — the IVA-wallet *blocked* calculate error leaked unrendered
>   `%{divergence}`/`%{reason}` placeholders. Two raise sites in
>   `application/modelo/_iva_wallet_gate.py` (`apply_iva_compensation_decision_binding` and
>   `require_persisted_iva_compensation_decision_matches_revision`) passed
>   `translated_message=` with **no `context`**. Now they pass
>   `context={"divergence", "reason"}`; the CLI renders e.g. *"(filed_history_only): Direct AEAT
>   wallet/cartera evidence is unavailable; … requires explicit taxpayer override before
>   automatic output."* (assertion strengthened in
>   `test_iva_wallet_engine_integration.py`).
>
> **ROOT-CAUSE for #2/#5 (re-characterised, by-design + a real gap).** Grounding the carry showed
> the data path is correctly wired (the `modelo-303-compensacion-pendiente-anteriores`
> previous_filing binding copies the prior period's `iva.compensacion-disponible-fin-periodo`,
> which a seed populates to 420). Auto-application is **intentionally blocked** by the
> reconciliation safety model (`domain/iva_compensation/_reconciliation.py::_missing_wallet_decision`):
> with no live AEAT wallet evidence the local recurrence/seed is "lower-confidence fallback
> evidence and **requires explicit taxpayer override** before automatic output". The remaining
> **genuine gap (ADR-scope, NOT fixed here): there is no operator-facing CLI verb to record that
> override** — `iva-wallet` exposes only `balance`/`seed`/`correct`. So after seeding, a real
> operator hits a (now-legible) blocked calculate with no documented way to apply the carry. A
> second latent issue: `resolve_iva_compensation_decision_for_calculation` returns a *persisted*
> decision without re-reconciling, so a `first_period_zero` decision persisted by an early
> calculate is **sticky** and ignores a later seed. Both are safety/legal-gated decisions
> (`aeat-safety-legal-gates`, `no-silent-under-declaration`) and warrant an ADR + the
> override-verb feature, not an autonomous edit.

## Persona narrative (first person)

My first quarter was all set-up cost: I bought €3.630 of hardware (€630 IVA soportado) and only
invoiced €1.210 (€210 IVA repercutido). So 1T owes me nothing and instead leaves €420 of IVA to
carry forward. In 2T I finally earned — €6.050 invoiced (€1.050 repercutido) against a small €605
software bill (€105 soportado) — €945 of IVA. The whole point: that €420 from 1T should knock my
2T bill down to €525.

On the re-run the 1T side was clean — −420 "a compensar", verified, and a `.boe` with no detours
(the two earlier potholes have been filled). But the carry still never happens. 2T stubbornly
shows €945, never €525. The €420 is generated and even sits in an "IVA wallet" balance, yet
nothing feeds it into the 2T calculation, and 2T verify flatly refuses pending official 1T filing
evidence. The one local switch that would create that evidence — `work file` — is refused because
the 2024 deadline is long past. So as a late filer I remain structurally unable to complete a
two-quarter IVA compensación chain in the app.

## What worked (re-confirmed on HEAD, no workarounds)

- Profile create (NIF letter fixed), CSV import (one file, both quarters), classify all four rows,
  `ledger preflight` 1T & 2T → `ready true, issues 0`.
- 1T `calculate` straight through: casilla 27 (devengada) **210**, casilla 45 (a deducir) **630**,
  casilla 64/66/71 **−420**, **casilla 65 now 100 by default**, `compensacion-generada` **420**.
- 1T `verify` → `completeness_status complete`, `granted_verificado_completo true` (4 advisory
  findings only) — **no DRAFT_HAS_ERRORS** anymore.
- 1T `export` → `.boe` byte_size **7994**, sha256
  `14eaea2fa479b18d94b2d3d4bcfd3f3665755036ae4a577e7c98b6ea13f7fc14`.
- The cross-period clean-state gate is *correct*: 1T's prior dep (303 2023 4T) is scoped out as
  pre-activity; 2T's prior dep (303 2024 1T) is within activity and demands real 1T evidence.

## Friction / breakage

### ✅ RESOLVED since first pass (by peer commit `3fdcde42c`)
1. **Final result silently zero (casilla 65 = 0).** Was: casilla 66/71 and the compensación
   generation all read 0 because casilla 65 "% atribuible al Estado" defaulted to 0; needed
   `--binding modelo-303-profile-state-attribution-ratio=100`. **Now defaults to común-territory
   100%** (Concierto Económico, Ley 12/2002 art. 29; foral refused at creation). Re-verified: a
   bare `calculate` yields casilla 65 = 100, casilla 71 = −420. **No binding needed.**
2. **Opaque `DRAFT_HAS_ERRORS` on verify, root-caused to a `formula-divergence` ERROR on
   `iva.prorrata-porcentaje`.** With prorrata volumes = 0 (ordinary full-deduction case) the 0/0
   formula short-circuited and emitted an incomplete `formula_trace` that failed the draft
   validator, blocking every ordinary 303 — surfaced only as a bare abort with no findings.
   **`build_draft` now uses the declared `formula_inputs` for the conditional casilla's trace**,
   so the spurious divergence is gone. Re-verified: 1T verifies and exports with prorrata volumes
   still 0 and **no workaround**.

### ❌ OPEN — re-confirmed on HEAD `627c093ea`
3. **The €420 does NOT carry 1T→2T.** With 1T verified and even with the IVA wallet seeded to 420
   (balance 420, lot_count 1), 2T `calculate` shows `compensacion-pendiente-periodos-anteriores`
   (casilla 110) = **0**, `compensacion-aplicada-periodo` = 0 → 2T resultado = **945**, not 525.
4. **`work file` refused for the historical period.** The carry the calc reads comes from a
   *filed* 1T revision (the `modelo-303-compensacion-pendiente-anteriores` previous_filing binding
   + the cross-period clean-state). `work file` (the local "mark internally filed" verb that would
   create that observation) refuses with `NO_PENDING_OBLIGATION` — "the AEAT filing-obligation
   window is not open" (2024 1T window closed in 2026). A late filer cannot create the carry record.
5. **`iva-wallet seed` does not bridge into `calculate`.** Seeding 1T=420 populates the wallet
   *balance* but the calculation's compensación binding reads the local *filed-revision recurrence*,
   not the seed lot (seed is documented "para un período anterior al historial local"; 1T is *in*
   local history, so it is a no-op for the carry). Two disconnected stores.
6. **2T `verify` blocks (correctly) on missing official 1T evidence.** Two BLOCKING
   `cross_period_dependency_unclean` findings: modelo=303 year=2024 period=1T,
   blockers `missing_observation, missing_current_filing_record`, origins
   `previous_filing_binding (modelo-303-compensacion-pendiente-anteriores)` and
   `registry_relation (modelo-303-rel-self-compensacion-anteriores)`. Remediation suggests
   `reconcile file … --file PATH`, but that wants an AEAT **justificante PDF**; the exported `.boe`
   is rejected (`pdfplumber failed to open`). With live filing prohibited and `work file`
   window-blocked, **no local path produces the 1T evidence 2T needs** → 2T can be neither verified
   nor exported.

## Input → Output reconciliation

All amounts 21% IVA. Bases/IVA are the persona inputs; casillas are tool output on HEAD.

### Modelo 303 — 1T 2024 (verified + exported, no workarounds)
| Input | Value | Casilla | Expected | Actual | Match |
|---|---|---|---|---|---|
| Income base / IVA (10/02) | 1000 / 210 | 27 cuota devengada | 210 | 210.00 | ✅ |
| Expense base / IVA (20/01) | 3000 / 630 | 45 a deducir | 630 | 630.00 | ✅ |
| Resultado régimen general | 210−630 | 64 | −420 | −420.00 | ✅ |
| % atribución Estado | 100 | 65 | 100 | **100 (now default)** | ✅ |
| Importe atribuible Estado | | 66 | −420 | −420.00 | ✅ |
| Resultado final (a compensar) | | 71 | −420 | −420.00 | ✅ |
| Compensación generada | | (compensacion-generada-periodo) | 420 | 420.00 | ✅ |

### Modelo 303 — 2T 2024 (calculated only; verify BLOCKED)
| Input | Value | Casilla | Expected | Actual | Match |
|---|---|---|---|---|---|
| Income base / IVA (15/05) | 5000 / 1050 | 27 cuota devengada | 1050 | 1050.00 | ✅ |
| Expense base / IVA (12/04) | 500 / 105 | 45 a deducir | 105 | 105.00 | ✅ |
| Resultado régimen general | 1050−105 | 64 | 945 | 945.00 | ✅ |
| **1T compensación carried in** | **420** | **110 compensacion-pendiente-anteriores** | **420** | **0** | ❌ |
| Compensación aplicada | 420 | (compensacion-aplicada-periodo) | 420 | 0.00 | ❌ |
| **Final 2T result** | | **71** | **525** | **945.00** | ❌ |

**Cross-period carry verification: STILL FAILED on HEAD.** The prior period's result (−420, a
compensar) is not reflected in 2T's compensación casilla (110 = 0). Final 2T = 945, not 525.

## Final artefacts

- **1T:** `tmp/personas/iva-crossperiod-303/m303-2024-1T.boe`
  - byte_size **7994**, file_sha256 **`14eaea2fa479b18d94b2d3d4bcfd3f3665755036ae4a577e7c98b6ea13f7fc14`**
  - (Identical bytes to the first-pass export — the `.boe` is now reached with **no workaround**.)
- **2T:** **NOT PRODUCED.** 2T `verify` legitimately blocks on missing official 1T filing evidence
  (Finding 6), which no local path can supply.

## Findings (numbered, by severity, with re-audit status)

1. **[CRITICAL][APP] ✅ RESOLVED (`3fdcde42c`).** `iva.prorrata-porcentaje` `formula-divergence`
   ERROR that blocked verify→export of every ordinary (zero-prorrata) 303 and surfaced only as
   opaque `DRAFT_HAS_ERRORS`. Re-verified fixed: 1T verifies & exports with prorrata volumes 0 and
   no workaround. Regression test `test_build_draft_conditional_formula_trace.py` added.
2. **[CRITICAL][APP] ❌ OPEN.** Cross-period IVA compensación does not auto-carry 1T→2T. €420 is
   generated (and seeded into the wallet, balance 420) but never reaches 2T casilla 110; 2T stays
   945 vs expected 525. The carry requires a *filed* 1T revision observation (previous_filing
   binding) that is unobtainable here (Findings 4–6). Proof: `iva-wallet balance` 420 while 2T
   `calculate` shows casilla 110 = 0.
3. **[MAJOR][APP] ✅ RESOLVED (`3fdcde42c`).** Casilla 65 "% atribuible al Estado" defaulted to 0,
   silently zeroing casilla 66/71 and the compensación generation. Now defaults to común 100%.
   Re-verified: bare `calculate` gives casilla 65 = 100, casilla 71 = −420. Regression test
   `test_state_attribution_ratio.py` added.
4. **[HIGH][APP] ❌ OPEN.** `work file` (the local "mark internally filed" verb that creates the
   carry/observation) refuses historical periods with `NO_PENDING_OBLIGATION` (closed window). A
   late filer therefore cannot establish a cross-period carry at all. Proof:
   `work file --modelo 303 --year 2024 --period 1T` → `NO_PENDING_OBLIGATION`.
5. **[HIGH][APP] ❌ OPEN.** `iva-wallet seed` is disconnected from `calculate`: seeding 1T=420
   updates the wallet balance but is not consumed by the 2T compensación binding (which reads the
   local filed recurrence). For an in-app prior period the seed is a no-op for the carry. Proof:
   balance 420, 2T casilla 110 = 0. Either the seed should feed the binding, or the verb should
   refuse/explain that it only applies to periods prior to local history.
6. **[MAJOR][BOTH] ❌ OPEN.** End-to-end the two-quarter compensación chain is unreachable locally:
   2T `verify` correctly blocks on missing official 1T evidence (`cross_period_dependency_unclean`),
   but live AEAT filing is prohibited, the only local evidence-producing verb (`work file`) is
   window-blocked, and `reconcile file` needs an AEAT justificante PDF (the `.boe` is rejected:
   `pdfplumber failed to open`). The safety gate is *correct*; the gap is there is no local,
   non-official "filed" path that both feeds the carry and is reachable for a past-deadline period.
7. **[MEDIUM][APP] ⚠️ MOSTLY RESOLVED.** `verify`'s `DRAFT_HAS_ERRORS` abort listed no findings.
   Its concrete 303 trigger (the prorrata divergence) is now fixed, so I can no longer reproduce
   the opaque abort on the 303 flow. The general design point — the abort still surfaces no
   underlying finding when it *does* fire — remains latent; worth enumerating draft ERRORs in the
   abort defensively.
8. **[LOW][DATA] (unchanged).** Persona NIF `78901234F` carries the wrong control letter; CLI
   correctly refused and named the correct letter (X). Exemplary refusal, not an app bug.
9. **[LOW][APP] (unchanged).** Non-blocking advisories fire on every cuota-bearing transaction
   asking to attach supporting invoice evidence (`ley-37-1992:art-97`). Reasonable but noisy for a
   bank-statement-only import flow.

## Verdict (re-audited)

**Improved, but the central test still fails.** The peer fix `3fdcde42c` closed both single-period
blockers I reported: 1T now goes calculate → verify → `.boe` **cleanly, with no workarounds** (the
−420 "a compensar" is correctly computed and exported). That is a real, verified win. But the
**cross-period compensación carry still FAILS**: the €420 does not reach 2T (2T = 945, not 525),
and **2T `.boe` still cannot be produced** because the carry pipeline requires *filed* prior-period
evidence that no local path can create for a closed-window historical filing. A real autónomo in
Pablo's situation would now sail through Q1, but would still never see Q1's IVA credit applied to
Q2 — the wallet shows 420 yet the next return ignores it. The remaining gap is the cross-period
plumbing (carry source, `work file` window-block for late filers, and the seed↔calculate
disconnect), not the single-period maths.

## Scorecard (re-audit)
- App capability (single-period 303): **4 / 5** (was 3 — the two blockers are fixed)
- Cross-period compensación pipeline: **1 / 5** (unchanged — carry still unreachable)
- Error-message quality: 3 / 5 (opaque abort no longer triggers on 303; one exemplary refusal)
- Findings: CRITICAL 1 open / 1 resolved, MAJOR 1 open / 1 resolved, HIGH 2 open, MEDIUM 1 mostly
  resolved, LOW 2.

---

## ADDENDUM 2026-06-20 — Company / legal-entity prism (SL, SII-enrolled, monthly)

Re-ran the cross-period 303 from a **limited company** angle to check for the
special provisions companies have that autónomos do not. Profile: `acme`, CIF
`B12345674`, `entity-type legal_entity`, `legal-entity-form sl`,
`incn-prior-12-months 8000000`, `--iva-sii-enrolled`, activity-start 2024-01-01.
Filed Modelo 303 **monthly** (the SII/large-enterprise cadence): 2024-01 (negative)
→ 2024-02 (apply carry).

### Verified WORKS for companies
- **Monthly cadence** — `work create/calculate/verify --modelo 303 --period 01`/`02`
  all accept monthly tokens for the SII-enrolled legal_entity. 01 verify granted
  (prior 2023-12 dependency scoped out by activity-start).
- **casilla 65 = 100** (% atribuible al Estado) resolves for the legal_entity too —
  the peer state-attribution default is entity-type-agnostic.
- **Monthly cross-period carry end to end.** 01 generates −420 (`casilla 71 = -420`,
  `compensacion-generada = 420`). `aeat app modelo iva-wallet override --filing-year
  2024 --period 02 --amount 420 --reason "..." --evidence-locator "..." --confirm`
  records a `taxpayer_override` decision; recalculating 02 yields
  **`iva.resultado` (casilla 71) = 525.00** (945 − 420 applied), `casilla 110 = 420`,
  `compensacion-aplicada = 420`. The override recorder and CLI verb work for MONTHLY
  periods, not just quarters — the carry the autónomo run could not complete now
  completes for the company.

### Findings (company-relevant gaps)
1. **[HIGH][APP] No "a devolver" (refund) disposition for Modelo 303.** The result
   disposition is hardcoded — `_DISPOSITION_SPEC[Modelo.M303].negative =
   ResultDisposition.COMPENSACION` (`src/aeat/core/_result_disposition.py`) — and the
   303 registry has **no refund result casilla** (only "a compensar" casillas; casilla
   109 "Devoluciones acordadas AEAT" is a different, input concept). So a negative 303
   result can never be **elected as a refund**. This blocks a **REDEME-enrolled
   company's monthly refund (devolución mensual)** — its defining provision — and any
   taxpayer's **last-period (4T / December) refund** election. Repro: a negative month
   always routes to compensación with no refund option.
2. **[MEDIUM][APP] `--iva-redeme-enrolled` is a dormant profile fact for the refund
   purpose.** It is accepted at profile-create and persisted, but is **not consumed**
   by the 303 calculation or disposition (SII *is* consumed — for the monthly cadence,
   which works; REDEME is not consumed for refund routing). An operator who declares
   REDEME enrollment gets monthly cadence but no monthly-refund behaviour.
3. **[NOTE] Grupo de entidades (REGE)** — the other company-only IVA provision — is
   modelled as **separate modelos 322 (individual) and 353 (aggregate)** with
   continuity tests, out of 303 scope. Not a gap; noted for completeness.

### Verdict (company prism)
The cross-period compensación **carry** works identically and correctly for a
limited company filing monthly (525 reached via the override). The genuinely
company-specific **refund** provisions (REDEME monthly devolución; last-period
refund election) are **not modelled** for Modelo 303 — the disposition is
carry-forward-only. A REDEME company that must legally request a monthly refund
cannot express that in the app today.

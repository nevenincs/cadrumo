---
tags:
  - '#research'
  - '#modelo-verify-nonzero-guards-residuals'
date: '2026-07-01'
modified: '2026-07-17'
related:
  - "[[2026-07-01-modelo-verify-nonzero-guards-m202-deferred-items-audit]]"
  - "[[2026-07-01-modelo-verify-nonzero-guards-residuals-adr]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-adr]]"
---

# `modelo-verify-nonzero-guards-residuals` research: `M202 casilla-33 minimum-tax floor and M714 deferred edges`

The `modelo-verify-nonzero-guards` campaign (L3 plan, 32/32 steps, closed) shipped ADVISORY silent-under-declaration guards for M200, M131, M202, M123, M151, M714, and M210, and deliberately left three edges as documented non-guards pending prerequisite work it could not do inline. This research grounds the two the M202 deferred-items audit routed forward — M202 casilla 33 (the INCN ≥ €10.000.000 pago-fraccionado mínimo floor) and the two M714 edges (base-imponible → base-liquidable, total-cuota-integra → cuota-a-ingresar) — to a guard-or-documented-non-guard decision with legal grounding attached. It does not re-litigate any shipped guard. Scope note: read against HEAD on 2026-07-01; the M202 minimum provision's constitutional history (below) is the one area flagged as needing operator/tax-expert confirmation before the corpus excerpt is finalized.

## Finding 1 — M202 casilla 33: the minimum-payment provision is now identified, but the guard signal is structurally unreachable

### 1a. The binding legal provision (was unnamed in the deferred-items audit; now grounded)

The INCN ≥ €10.000.000 pago-fraccionado mínimo is established by Ley 27/2014 (LIS) Disposición Adicional Decimocuarta ("Modificaciones en el régimen legal de los pagos fraccionados"), NOT by any article in casilla 33's current legal_refs. The rule: the pago fraccionado of the art. 40.3 modality may not be lower, in any case, than 23 % of the resultado positivo de la cuenta de pérdidas y ganancias of the first 3, 9 or 11 months (the rate is 25 % for contribuyentes taxed under art. 29.6 párrafo primero — credit institutions and hydrocarbon entities at 30 %), applying only to contribuyentes whose importe neto de la cifra de negocios in the prior 12 months is ≥ €10.000.000. Confirmed against the AEAT Manual práctico de Sociedades ("Modalidad regulada en el artículo 40.3 de la LIS. Pago fraccionado mínimo", dated 2023-07-26) and the AEAT FAQ on whether a minimum exists for art. 40.3 payments since 2016 — both state the measure is in force for filing periods from 2016 onward, including 2024/2025. LIS is BOE-A-2014-12328.

The base is a specially-adjusted positive P&L result, not a raw accounting figure: the DA-14ª excludes quita/condonación income, capital increases by credit compensation, the exempt/bonified portion for partially-exempt / local-service / shipping / ZEC / Ceuta-Melilla (50 %) / RIC (90 %) entities, and the mínimo does NOT apply to SICAV/venture-capital, certain shipping regimes, art. 29.3-29.5 entities, or SOCIMI (Ley 11/2009).

Constitutional caveat (must be resolved before finalizing a corpus excerpt, per `legal-grounding-verifies-bundled-authoritative-corpus`): DA-14ª was introduced by RDL 2/2016, which STC 78/2020 (2020-07-01) declared unconstitutional on formal grounds (a decreto-ley may not regulate the deber de contribuir). AEAT's own current surfaces nonetheless describe the mínimo as applicable for 2024/2025, so the excerpt must be sourced from the live consolidated LIS text (`boe.es/buscar/act.php?id=BOE-A-2014-12328`, disposición adicional decimocuarta anchor `#dadecimocuaa`) and its in-force status re-confirmed against that consolidation — the bundled corpus cannot be trusted to carry it (it does not; see 1b), and the RDL-2/2016 origin text must not be cited as if current.

**Resolution (added post-authoring, web-verified against BOE/AEAT):** the constitutional status is settled. STC 78/2020 struck ONLY the original RDL-2/2016 redacción, and on FORMAL grounds (a decreto-ley may not regulate the deber de contribuir). DA-14ª was RE-ENACTED by **art. 71 of Ley 6/2018, de 3 de julio** (BOE-A-2018-9268), and that redacción was UPHELD as compatible with the principio de capacidad económica by **STC 175/2025, de 20 de noviembre** (BOE-A-2025-26690). The 23 %/25 % minimum on the resultado positivo de PyG for INCN ≥ €10.000.000 is therefore in force for 2024/2025. The shipped grounding (corpus excerpt + `is.toml` `ley-27-2014:da-14`) cites the **Ley-6/2018 redacción** as the binding provision, NOT the struck RDL-2/2016 — this Resolution supersedes the RDL-2/2016 framing in the caveat above. The verbatim rule text was lifted from the AEAT Modelo 202 2025 instructions (clave 33) and cross-checked against the BOE STC rulings; the `is.toml` entry is agent-prepared (`reviewed_by = coordinator-web-verified`) and PENDING OPERATOR RE-STAMP per `legal-grounding-verifies-bundled-authoritative-corpus`.

### 1b. The bundled corpus does not carry the minimum; casilla 33's legal_refs are mis-grounded

`src/aeat/_data/corpus/normatives/html/ley-27-2014-art-40.html` is the consolidated art. 40 text but stops at apartado 5; its apartado 3 ends at "pagos fraccionados efectuados correspondientes al período impositivo" with no minimum-payment paragraph. Its only INCN figure is the €6.000.000 threshold that forces the art. 40.3 modality (apartado 3, párrafo 6) — a different threshold from the €10.000.000 minimum-payment gate. grep across `src/aeat/_data/registry/aeat/legal/is.toml` finds no art-30-bis, no da-14, and no disposición-adicional entry for the mínimo.

Casilla 33 (`.../202/revisions/2025-y-siguientes/casillas/0049-33.toml`, byte-identical label/refs in `2019-2022/casillas/0042-33.toml` and `2023-2024/casillas/0042-33.toml`) declares legal_refs = ["ley-27-2014:art-40", "art-29", "art-30", "art-105"] — the framework mechanics, none of which establish the minimum value. Per `registry-calculation-legal-grounding` ("every regulatory value must declare the binding provision that establishes it"), casilla 33 is currently mis-grounded independently of any verify-gate decision. Grounding DA-14ª (authoring the legal-catalogue entry + consolidated-corpus excerpt, then adding it to casilla 33's legal_refs) is a standalone, low-risk correction that does not depend on the guard question.

### 1c. Casilla 33 is consumed (not a dead casilla — contrast casilla 26)

`formulas/0007-modelo-202-cantidad-a-ingresar.toml` computes casilla 34 (cantidad a ingresar) as max(casilla 32, casilla 33). So unlike the audit's separate critical finding on casilla 26 (which was unwired and has since been fixed in commit `cb002833a`), casilla 33 already flows into the headline result: for an INCN ≥ €10M filer with a positive adjusted P&L, casilla 33 should be > 0 and, when it exceeds the ordinary result 32, becomes the amount actually payable. A silent zero here is a genuine under-declaration for the large-taxpayer population the mínimo targets.

### 1d. Why no false-positive-free guard is expressible today (the three concrete blockers)

The semantically-correct guard is: (INCN ≥ €10.000.000) AND (resultado positivo ajustado > 0) ⇒ casilla 33 > 0. None of the three inputs is available to the verify gate:

1. The INCN is not visible to the predicate evaluator. It exists in the system as a Decimal profile fact `taxpayer.incn_prior_12_months`, delivered via the source = "profile" binding `modelo-202-2025-y-siguientes-incn-prior-12-months` (`bindings/0002-...toml`) and consumed at calculate time by `derive_modelo_202_modality`. But `_evaluate_verification_predicates` and `_evaluate_advisory_predicate_fires` (`src/aeat/application/modelo/_verification_actions.py`, signatures near lines 633 and 792) receive only casilla_values (Mapping[CasillaId, Decimal]) and text_values (Mapping[CasillaId, str]) — no binding or profile-fact channel. The €10M gate signal exists but is structurally unreachable by any predicate.
2. The existing categorical operator cannot express a numeric threshold. `casilla_equals_implies_nonzero` (added by `2026-06-30-m210-categorical-conditional-predicate-adr`) gates on a text-casilla equality, not a numeric ≥ literal comparison, and the INCN is not a casilla at all. It is the wrong shape twice over.
3. The minimum's own base is off-form. Casilla 04 (resultado contable después del Impuesto sobre Sociedades) is not the DA-14ª resultado positivo de PyG ajustado (the exclusion set in 1a is not modelled), so even with a gate the antecedent that should drive "the minimum ought to be positive" is not cleanly available.

The nearest naive guard `implies_nonzero(["04", "33"])` was already rejected by the deferred-items audit: casilla 04 is positive for the overwhelming majority of sub-€10M filers who correctly leave casilla 33 blank, so it would false-fire structurally on nearly every M202 filer — the M714-class antipattern (`ledger-iva-advisory-only-on-cuota-bearing-categories`: an advisory that fires on a routinely-legitimate zero trains operators to ignore it). Locked today by `test_committed_modelo_202_minimo_a_ingresar_cn_10m_remains_unguarded`.

## Finding 2 — M714 base-imponible → base-liquidable: legitimate-zero population is real (mínimo exento)

`patrimonio.base-liquidable` = `patrimonio.base-imponible` − mínimo exento (Ley 19/1991 art. 28: €700.000 general, autonomically variable — Comunitat Valenciana €600.000; grounded at `src/aeat/_data/registry/aeat/legal/patrimonio.toml:11` ley-19-1991:art-28). Both casillas are input_kind = "manual" with no formula linkage (`.../714/revisions/2021-y-siguientes/casillas/0001-casillas.toml:35-57`).

A filer with base imponible > 0 but ≤ the mínimo exento legitimately has base liquidable = 0. This is not a rare edge: the M714 filing obligation (Ley 19/1991 art. 37) is triggered independently by patrimonio bruto > €2.000.000, so a taxpayer with, say, €650.000 net base but €2M+ gross assets must file with a legitimately zero base liquidable. `implies_nonzero(["patrimonio.base-imponible", "patrimonio.base-liquidable"])` would false-fire on every such filer, and the CCAA-variable mínimo exento means no fixed constant lets a guard even estimate the boundary. Recommendation: keep deferred (documented non-guard). The prerequisite to make it guardable is to model base-liquidable = max(base-imponible − mínimo_exento_CCAA, 0) as a computed formula (requires a CCAA mínimo-exento table in the registry) — after which a zero is a computed consequence and no advisory is needed (the M200 Phase-2 shape).

## Finding 3 — M714 total-cuota-integra → cuota-a-ingresar: an advisory here would fire on the norm in several CCAAs

Between `patrimonio.total-cuota-integra` (casilla 40) and `patrimonio.cuota-a-ingresar` (casilla 55) sit casilla 45 (cuota minorada) and three legitimate zeroing mechanisms:

- Art. 31 límite conjunto (`patrimonio.toml:50`, ley-19-1991:art-31): IP + IRPF cuota ≤ 60 % of IRPF base imponible; the excess reduces IP cuota but the reduction is capped at 80 % (a 20 % floor). This alone cannot zero the cuota.
- Art. 32 foreign-tax-satisfied deduction and art. 33 Ceuta/Melilla bonificación (75 %) — can be large.
- Autonomic bonificaciones up to 100 % (Madrid and Andalucía have applied a ~100 % IP bonificación): a resident of those CCAAs with a positive total cuota íntegra legitimately has cuota a ingresar = 0. This is not an edge case — it is the typical outcome for the large filer population in those communities.

`implies_nonzero(["patrimonio.total-cuota-integra", "patrimonio.cuota-a-ingresar"])` would therefore false-fire on the most common case in Madrid/Andalucía — an advisory that is not merely noisy but actively miseducating. Recommendation: keep deferred (documented non-guard), and treat as the lowest-value of the three edges to ever guard. Even a full derivation of the deducción/bonificación chain (including CCAA bonificaciones) would make zero a legitimate computed consequence, so the value of that modelling is correctness, not a future guard.

## Summary of recommendations (decision surface for the ADR)

- M202 casilla 33 — documented non-guard (keep deferred), with two attached actions. (i) Immediately actionable and guard-independent: author the DA-14ª legal-catalogue entry + live-consolidated-corpus excerpt and add it to casilla 33's legal_refs (fixes a `registry-calculation-legal-grounding` gap). (ii) A false-positive-free guard requires three prerequisites: a binding/profile-fact value channel into the predicate evaluator, a numeric-threshold predicate operator (fact ≥ literal ⇒ nonzero), and either an on-form resultado-positivo-ajustado base or acceptance of casilla 04 as an approximation. All three are out of scope for registry-authoring and are recorded as the prerequisite stack.
- M714 base-imponible → base-liquidable — keep deferred (documented non-guard). Legitimate-zero via art. 28 mínimo exento (CCAA-variable). Prerequisite: compute base-liquidable with a CCAA mínimo-exento table.
- M714 total-cuota-integra → cuota-a-ingresar — keep deferred (documented non-guard). Legitimate-zero via art. 31 límite conjunto floor + art. 32/33 + CCAA bonificación up to 100 %; an advisory would fire on the norm in Madrid/Andalucía.
- Enforcement. Each non-guard should be pinned by a canary test citing this research by name, so a future change that lands a prerequisite is forced to revisit the decision (the pattern the deferred-items audit already used for casilla 33 and the M714 edges).

## What was not investigated

- The DA-14ª current-consolidation in-force status was confirmed against AEAT's manual/FAQ surfaces; the BOE consolidated DA-14ª tail could not be fetched verbatim by the research persona (page too large for the fetch tool, truncates before the disposiciones adicionales) — the corpus-authoring step must read it at the `#dadecimocuaa` anchor and lift the exact wording.
- The 2019-2022 and 2023-2024 M202 revisions were confirmed to carry a byte-identical casilla 33 (same label/refs) but their formula text for casilla 34 was not re-read verbatim this pass (the deferred-items audit confirmed the max(32, 33) shape is shared).
- No IRPF-side (Modelo 100) coupling for the M714 art. 31 límite conjunto was modelled or investigated; it is noted only as a reason the 40 → 55 edge is not a clean implication.

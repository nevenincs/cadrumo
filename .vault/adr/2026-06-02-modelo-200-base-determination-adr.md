---
tags:
  - '#adr'
  - '#modelo-200-base-determination'
date: '2026-06-02'
modified: '2026-06-02'
related: []
related:
  - '[[2026-06-04-modelo-200-base-determination-research]]'
---



# `modelo-200-base-determination` adr: `Modelo 200 IS base-determination soundness: prevent silent zero-base under-declaration` | (**status:** `accepted`)

## Problem Statement

Round-30 CLI persona testimonials surfaced, and a coordinator reproduction confirmed,
a legal-soundness hole in the Impuesto sobre Sociedades (Modelo 200) calculation: the
verify gate grants `verified_complete` on a draft that under-declares. Concrete repro
(SL company, ejercicio 2024): supply only the resultado contable
`DP200014:00501 = 140000`, calculate, and the base imponible `DP200014:00552`,
base-tras-nivelación `DP200014:01330`, and cuota íntegra `DP200014:00562` all resolve
to `0`. `work verify` then returns `completeness_status = complete`,
`granted_verificado_completo = true`, `finding_count = 0` — i.e. a €140,000-profit
company is allowed to verify (and a human to then file) a €0-tax return.

The root cause is that the base imponible casilla `DP200014:00552` is declared
`input_kind = "manual"`, `required = false`, with no formula deriving it from the
resultado contable. The Modelo 200 revision declares only five formulas; the IS
base-determination chain (resultado contable ± correcciones al resultado contable −
compensación de bases imponibles negativas − reserva de capitalización → base
imponible) is not modeled. Once the base is entered, the downstream chain is correct
(`01330 = 00552 + 01033 − 01034`; `00562 = 01330 × 00558 / 100`, tipo grounded), but
the base itself never derives, so a filer who supplies the accounting result expecting
the base to follow gets a silent zero.

This ADR is the result of the round-30 testimonial audit plus the round-29/30 legal
grounding pass. It records the decision for closing the soundness hole. The companion
infrastructure fix — restoring the verify gate so it can rebuild and evaluate drafts at
all — already landed (`fix(modelo): snapshot + replay date-bindings and relations`,
commit `5531c8560`); this ADR addresses what the now-working gate must actually catch.

## Considerations

- **AEAT authority.** Ley 27/2014 (LIS) Art. 10: «La base imponible estará constituida
  por el importe de la renta obtenida en el período impositivo minorada por la
  compensación de bases imponibles negativas...» and Art. 11–25 (correcciones,
  reserva de capitalización). The AEAT Manual práctico de Sociedades 2024 defines the
  Liquidación I→III chain from `00500/00501` (resultado de la cuenta de pérdidas y
  ganancias) through the correcciones to `00552` (base imponible). The base is a
  derived, mandatory figure — never a free-standing manual entry in a correct filing.
- **The correcciones are many and individually manual.** The revision exposes the
  correccion casillas (`01230`/`01231`, `02301`–`02308`, `03391`–`03397`, and more) as
  manual inputs with no computed aggregate (`total correcciones`) and no computed
  `base imponible previa`. There is no two-casilla shortcut.
- **The verify gate now enforces** (post `5531c8560`) and supports per-modelo
  `verification_predicates` (DSL ops `cap_le_when_positive`, `implies_nonzero`; finding
  kinds `BLOCKING_RULE`, advisory) declared in `verification_expectations` TOMLs.
- **No clean guard exists.** Making `00552` `required = true` false-positives on
  loss/zero-base companies (which declare via `00027`, «base imponible negativa o
  cero») and would red existing M200 flows; a `BLOCKING_RULE` `implies_nonzero` from
  resultado contable to base false-positives on legitimate zero-base cases (negative
  resultado, BIN compensation, ajustes) and the DSL has no op expressing the precise
  "positive profit AND no declared reductions" condition.

## Constraints

- **Substantial, grounded feature.** Modeling the base-determination correctly means
  aggregating every correccion casilla into a computed `base imponible previa` and then
  applying BIN compensation and reserva de capitalización — each summand grounded in a
  specific LIS article. This is feature development, not a bug-fix.
- **Active peer zone.** Modelo 200 is under concurrent development on this branch
  (recent peer commits bind C65 state-attribution to jurisdiction scope and require the
  `tributacion-estado-porcentaje` binding). Any change to the M200 registry or its
  cuota chain must be coordinated to avoid colliding with that campaign.
- **Persisted-record / content-address impact.** Turning `00552` from manual to
  computed changes the casilla's `input_kind` and the engine result set, which affects
  calculation-revision content addressing and demands roundtrip-test updates.
- **Parent-feature stability.** Depends on the now-stable verify gate (`5531c8560`) and
  the existing tipo/cuota chain (`00558`/`00562`), both confirmed correct once the base
  is non-zero.

## Implementation

Two phases, the first safe and small, the second the durable fix.

**Phase 1 — make the under-declaration non-silent (interim).** Add an advisory
`verification_predicate` to the Modelo 200 `verification_expectations` so the verify
gate surfaces a non-blocking finding when the resultado contable is positive but the
base imponible is undetermined (zero) — turning today's silent `finding_count = 0` grant
into an explicit operator-facing advisory to confirm the base. Advisory (not
`BLOCKING_RULE`) is deliberate: it avoids false-positive-blocking legitimate
loss/BIN/ajuste zero-base filings, and the application never files to AEAT (a human
files outside the app), so an explicit alert is the correct safeguard for the interim.
This requires either an advisory-capable conditional predicate op or a narrow new DSL
op ("nonzero-implies-nonzero-when-positive"); the predicate carries its LIS Art. 10
legal ref.

**Phase 2 — model the base determination (durable fix).** Derive the base from the
form's STORED Liquidación column subtotals, NOT a per-leaf re-sum. The faithful chain,
grounded against the AEAT Manual de Sociedades 2024 Cap. 5 and confirmed in the companion
`2026-06-02-modelo-200-base-determination-reference` (which extracts the diseño de
registro 2024 DP-segment layout):

- `DP200014:00550` (base imponible previa) = `DP200014:00501` (resultado contable) +
  `DP200013:00417` (total correcciones de aumento) − `DP200013:00418` (total correcciones
  de disminución) — computed.
- `DP200014:00552` (base imponible) = `max(00550 − 01032 − 00547, 0)`, the non-negative
  clamp encoding «si el resultado es cero, consignar cero» (`01032` = reserva de
  capitalización, Art. 25 LIS; `00547` = compensación de bases imponibles negativas,
  Art. 26 LIS) — computed.

The leaf correcciones (semantic_role `is_correcciones_aumentos` /
`is_correcciones_disminuciones`) feed the `00417`/`00418` subtotals — summing the leaves
*alongside* the subtotals double-counts and is rejected; there is no `sum_by_role`
evaluator op (only `add`/`subtract`/`max`). Because the bare numbers
`00550`/`00547`/`00417`/`00418` resolve to UNRELATED Estado-de-Cambios-en-el-Patrimonio-Neto
records (Prima de emisión, etc.), the implementation creates segmento-qualified
`DP200013`/`DP200014` calc-only records (no `export_refs`, to avoid the page-014 ECPN
fichero collision) and flips `DP200014:00552` manual→computed.

`00547` is the layering seam: Phase 2 lands it MANUAL; the A4 BIN hook then makes it
computed as `00547 = min(bin_disponible, max(€1M, 70%·00550))` — the 70% límite
(Art. 26.1 LIS) applies to the base imponible previa *before* reserva and compensación,
i.e. `00550`. The arts.13/16 value-derivations inside the correcciones stay operator-input
(stateful follow-on sub-engines); the arts.10/11/14 BOE corpus ingest grounds legal_refs
but does NOT block the calc (the base chain cites the grounded art-15/25/26 set). With
this, a zero base is a computed consequence of the declared inputs, not a silent omission,
and the Phase-1 advisory upgrades to a BLOCKING consistency check between the computed and
any operator-entered base.

## Rationale

The correct fix is the derivation, because it makes the under-declaration *impossible*
(the base reflects the declared economic reality) rather than merely *flagged*. But the
derivation is a large grounded feature in an actively-developed modelo; shipping the
Phase-1 advisory first converts a silent, unauditable under-declaration into an explicit
operator alert immediately, at near-zero risk, while Phase 2 is grounded and coordinated.
This sequencing is grounded in the round-30 testimonial repro and the round-29/30
BOE/AEAT grounding pass (Ley 27/2014 Art. 10; AEAT Manual de Sociedades 2024 Liquidación
I→III).

## Consequences

- **Gains.** Phase 1 closes the *silent* hole immediately (operator is alerted before a
  human files), is additive, and carries no calc-correctness risk. Phase 2 delivers the
  AEAT-faithful base determination, which also unblocks correct cuota for every M200
  filer, not just the under-declaration case.
- **Difficulties.** Phase 2 is large (dozens of grounded correccion summands), touches a
  persisted record's content address (roundtrip-test churn), and must be coordinated
  with the active M200 campaign. The Phase-1 advisory needs a predicate op that may not
  exist yet (small DSL extension).
- **Pitfalls.** A rushed BLOCKING guard would red legitimate loss/BIN/exempt filings;
  this ADR explicitly rejects that. A partial base model (some correcciones missing)
  would compute a *wrong* base — worse than an honest zero — so Phase 2 must be complete
  per-correccion before `00552` flips to computed.

## Codification candidates

- **Rule slug:** `no-silent-under-declaration`.
  **Rule:** A modelo verify gate must never grant `verified_complete` with zero findings
  on a draft whose cuota is zero while a positive economic input (resultado contable,
  rendimiento, base) is declared and no offsetting reduction is declared; it must surface
  at least an advisory finding so a human never files a silent under-declaration.

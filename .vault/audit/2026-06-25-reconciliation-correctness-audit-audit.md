---
tags:
  - '#audit'
  - '#reconciliation-correctness-audit'
date: '2026-06-25'
modified: '2026-06-25'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace reconciliation-correctness-audit with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `reconciliation-correctness-audit` audit: `IVA and calculations RAG correctness and completeness audit`

## Scope

Operator-directed RAG-grounded correctness + completeness audit of every IVA and
calculation surface, verifying (1) each landed reconciliation finding is genuinely
fixed at origin HEAD (not committed-by-message-only, not tautologically tested), and
(2) no new IVA/calc correctness or completeness gap exists outside the original
findings. Run as a two-agent swarm: the IVA slice (prorrata, reverse-charge /
intracom / import routing, M303/M390, the compensation wallet) and the non-IVA calc
slice (renta M100/M130/M131, IS M200/M202, retenciones M180/190/193, the cross-period
carry engine). Read-only; no production code touched.

## Findings

### IVA slice — CLEAN (no current defect, no new gap)

- **#7 IVA-1 (M390 box 97 year-end carry) — FIXED + VERIFIED.** Box 97 carries the full
  disponible saldo via the FIFO partition `derive_iva_compensation_year_end_carry_partition`
  in `_carry_forward.py`, consumed through the relation override in `_relation_prefill.py`;
  proven by `test_iva_compensation_history.py` + `test_modelo_390_303_fold_in_live.py`.
- **#12 IVA-2 (M390 box 662 double-count) — FIXED + VERIFIED.** Box 662 excludes applied
  credits; the AEAT identity `[86]=[84]-[85]=[95]-[97]-[98]-[662]` is asserted in
  `test_iva_compensation_history.py`. No double-count.
- **#16 IVA-4 (M303 recargo cross-period) — VERIFIED CORRECT.** Per-period recargo cuota
  bindings (`ledger_iva_aggregation`, `fact=recargo_amount_sum`) scope per quarter with no
  cross-period leakage; `test_e2e_ledger_m303_recargo_cross_period.py`.
- **#15 IVA-3 (M303 base 03/07/28 on non-2023 revisions) — RECLASSIFIED, not a current
  defect.** The current `2023-y-siguientes` revision carries `0004-domestic-base` (ledger
  aggregate). The older `2009-y-siguientes` revision has no `bindings/` directory, so its
  base/recargo casillas are `input_kind=manual` (operator-filled, NOT silently zero). Ledger
  aggregation is a 2023+ feature; this is historical feature-parity, medium-low backfill, not
  a correctness bug on any current filing.
- **No new IVA gaps.** Prorrata (`domain/iva/_prorrata.py`, LIVA art.105), reverse-charge /
  inversión / intracom / import (`domain/iva/_saturation.py` category coverage,
  `_iva_ledger.py`), and the wallet (casillas 110/78/87) are all implemented. Completeness
  gates green (dormant-ledger-resolvers-fire-live, IVA category-coverage,
  `assert_no_novel_source_kinds`, no-silent-under-declaration). 1378 IVA+calc tests pass.

### Coordinator inline spot-checks at HEAD (corroborating)

- #14 IS-4: `00592` `input_kind=computed` formula `modelo-200-cuota-liquida` + `00582` computed
  — genuine. #5 IS-1: M202->M200 modalidad-cuota fold-in present (`8921bf850`). #10 IS-2:
  `roll_forward_balances` BIN continuity present. #2/#20: RefundAccount + REDEME / `core/_iban`
  present. 210 targeted campaign tests green across verification, parity, and refund surfaces.

### #6 RET-1 (CRITICAL) — NOT FIXED (confirmed live defect)

The M180 perceptores binding (`bindings/0001-modelo-180-115-perceptores-anual.toml`,
`2023-y-siguientes`) at HEAD is still `source="relation_prefill"` + `aggregation={op="sum"}`
over `[1T,2T,3T,4T]` — the original quarterly double-count is unchanged in production. Only the
P01 store + P02 resolver infrastructure landed; the P03 cutover (the actual fix) is blocked on
the live casilla-id sweep that owns the M180/190/193 manifests + dependency_classifications. The
double-count remains a live CRITICAL until P03 lands.

### Non-IVA calc slice — 12 fixed, #6 confirmed not-fixed, #15 not-fixed on historical revision

Verified at HEAD (git show/grep/read; RAG mid-reindex so file-content-confirmed):

- **#5 IS-1 GENUINELY-FIXED** — new 40.2 relation reads M202 casilla 03; `00611` subtracts
  `SUM(40.3-c34 + 40.2-c03)`; non-tautological oracle test.
- **#8 IRPF-1 GENUINELY-FIXED** — `_scoped_relation_source_requirements` drops pre-activity-start
  source periods; M131 covered generically but only M130 tested.
- **#9 IRPF-2 GENUINELY-FIXED (1-yr scope)** — carry (previous_filing) AND consume
  (`0435 = max(0, 0432-0433-1389)`), 2 BLOCKING predicates; the full art.48 4-year window is
  explicitly DEFERRED (only the 1-year carry landed).
- **#10 IS-2 GENUINELY-FIXED** — ADVISORY `roll_forward_balances` continuity, identity-based test.
- **#11 RET-3 GENUINELY-FIXED** — per-NIF totals merged before the threshold test (registry-grounded
  3005.06); cross-cohort same-NIF merge not directly pinned (thin test).
- **#13 IS-3 GENUINELY-FIXED (E2E claim overstated)** — first-year flag resolves the unfiled M202
  fold to `Decimal(0)` not `None` (the crash trigger); but coverage stops at the resolver unit, no
  full calculate->verify E2E despite the commit message claiming "verified end-to-end".
- **#14 IS-4 GENUINELY-FIXED** — `00582`/`00592` computed from `00562`; `00599` chain computed;
  independent-oracle test (80.000@25% -> 00599=20.000).
- (IVA #7/#12/#16 independently corroborated as fixed; see IVA slice.)
- **#6 RET-1 NOT-FIXED (confirmed, sharper)** — the M180 (both revs) + M193 bindings still
  `source="relation_prefill"` op="sum"; AND the enrolled `RetencionesAggregationSourceResolver`
  is INERT — it short-circuits empty unless a binding declares `source="retenciones_aggregation"`,
  and ZERO bindings do (the registry re-stamp half of the fix, held in
  `.agents/discarded-wip/p02-enrollment.patch`, never landed). So the wrong sum-relation still
  drives the count; only the code/mesh half of P02 is live and it does nothing on its own.
- **#15 IVA-3 NOT-FIXED on the 2009-2022 revision** — `303/revisions/2009-y-siguientes` has zero
  domestic-base AND zero recargo ledger bindings; base casillas 01/04/07/28 stay manual. Marked
  completed but the gap persists on the historical revision (see GAP-B; severity scope-gated on
  whether 2009-2022 is a live reconstruction target).

No tautological calc tests found among the fixed set.

## New-gap inventory (non-IVA + cross-cutting)

- **GAP-A (campaign-scope correction):** the RET-1 distinct-count defect is confirmed for M180
  (both revs) + M193 ONLY. M190's box is `total_percepciones_count` ("Numero total de
  PERCEPCIONES" = perception RECORDS), so summing across quarters is plausibly CORRECT. Do NOT
  fold M190 into the RET-1 cutover without grounding against the M190 Diseño de Registros first.
- **GAP-B (#15 root, wider):** `303/revisions/2009-y-siguientes` lacks BOTH domestic-base and
  recargo ledger bindings -> a ledger-driven historical M303 leaves base (03/07/28) and recargo
  at 0 (cuota-without-base). Fix only if 2009-2022 is a live reconstruction target.
- **GAP-C (coverage):** M100 revisions 2020-2023 carry only ~5 bindings each (no M130/M131 fold,
  no ledger income/expense, no base-liquidable-negativa carry) vs the full 2024/2025 set; likely
  intentional staged build-out, confirm scope.
- **GAP-D (test-integrity + TOML drift):** the #7/#12 FIFO override has NO discriminating test
  through the full calculate action — the live M390 test passes only because its fixture has no
  carried-pending chain (disponible==generada). Add a full-calculate M390 test with a real
  carried-pending chain. Separately, the registry relations/bindings still declare op=sum that the
  app-layer override silently supersedes, so reading the TOML alone misrepresents the actual
  aggregation (readability/drift hazard).
- **GAP-E (minor coverage):** IS-3 has no full-stack calculate->verify E2E (only the resolver
  unit) despite the commit's E2E claim; #11 cross-cohort same-NIF merge isn't pinned by a test.

### Deeper-pass corrections (non-IVA auditor, round 2 — grounded)

- **GAP-A REVERSED — M190 IS defective (now confirmed, grounded).** The softer round-1 call
  ("M190 counts percepciones=records, maybe fine") was DISPROVEN by grounding the source: M190
  `decl.total-percepciones` = op=add of 9 relations, each op=sum over 4 quarters of M111
  source_output "01", and M111 box "01" is `semantic_role="perceptor_count"` / label "...número
  de PERCEPTORES" (`111/.../casillas/0001-01-03-trabajo_dinerario.toml:4,7`). So M190 sums
  quarterly PERCEPTOR counts — a worker present all 4 quarters counts 4x while the annual file
  holds 1 type-2 record. **#6 RET-1 therefore spans M180 (x2 revs) + M193 + M190 (9 count
  bindings)** — one canonical fix (route the count bindings to the already-enrolled distinct-count
  resolver, which already supports all three via `_RETENCIONES_PERCEPTOR_COUNT_AGGREGATORS`) closes
  the whole family. r2 should still confirm against the M190 Diseño "número de registros tipo 2" at
  re-stamp, but the M111 grounding makes M190 a confirmed over-declaration, not a maybe.
- **GAP-2 (reference, not a defect — the canonical fix shape):** M130 prior-pagos casilla uses a
  TYPED cumulative op `aggregation op="prior_pagos_fraccionados"` (`130/.../bindings/0001-bindings.toml:39-41`),
  not raw sum. The RET-1 count bindings should mirror this typed/distinct-op pattern.
- **GAP-3 (NEW — likely live under-declaration):** M131 estimación objetiva is under-modeled
  (2019-2023: 1 binding; 2024-2026: 2 each, vs M130's 4). The módulos rendimiento chain looks like
  a computed-casilla hole (rendimiento de módulos manual rather than engine-derived), consistent
  with the no-silent-under-declaration rule's M131 note — a positive-módulos filer could silently
  file a low/zero base. Confirm whether módulos rendimiento should be engine-computed.

CLEAN (verified): cross-period carry engine sound (M130 cumulative uses typed previous_filing ops;
REGISTRY_REVISION_DIVERGENCE blocks, unstamped advises); no dormant/unrouted binding source (all 14
source kinds enrolled or in DEFERRED_SOURCE_KINDS); no computed cuota/base casilla without a formula
(M303/M390/M200/M130/M200 cuota chain 00562->00582/00592->00599); M303 resultado uses op=subtract;
M347 threshold registry-grounded.

Headline: 12 of 14 checked findings GENUINELY-FIXED; #6 RET-1 NOT-FIXED (registry half never
landed, resolver inert); #15 NOT-FIXED on the 2009-2022 historical revision. Biggest new
correctness risk = GAP-B; biggest test-integrity risk = GAP-D; M190 is NOT confirmed defective
(GAP-A needs Diseño grounding).

## Recommendations

- Land #6 P03 (the RET-1 distinct-count cutover) the moment the casilla-id sweep commits; it is
  the one open live CRITICAL. No safe pre-commit drive exists (whole-revision validation against
  a dirty tree).
- Track the #15 historical ledger-aggregation backfill (pre-2023 M303 revisions) as a
  medium-low feature-parity item, not a correctness bug.
- Complete the non-IVA slice and merge before declaring the campaign structurally complete.

## Codification candidates

<!-- Findings that satisfy the three durability criteria
(cross-session, constraint-shaped, project-bound) and should be
promoted into project-shared rules under `.vaultspec/rules/rules/`
via `vaultspec-core vault rule promote --from <this-audit-stem>
--as <rule-name>`.

Each candidate names the finding it derives from, the proposed
rule slug (kebab-case, naming the constraint's subject not the
failure), and a one-sentence statement of the rule.

Most audits produce zero codification candidates. Some produce one.
Only the rare framework-wide-pattern audit produces several. -->

No NEW codification candidates from this verification pass — it confirms existing fixes
rather than surfacing a new durable constraint. Pre-existing candidates remain pending
ripeness (one execution cycle after their fix lands): `retenciones-counts-are-distinct-not-summed`
(blocked until #6 P03 lands), `cross-period-carry-balances-are-reconciled` (#10 BIN continuity),
`fichero-refund-account-is-secure-storage-only` (#2). The shared-worktree landing lesson was
already promoted this campaign as `uncommitted-wip-is-not-orphaned`.

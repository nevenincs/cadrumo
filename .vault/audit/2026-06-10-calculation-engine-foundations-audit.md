---
tags:
  - '#audit'
  - '#calculation-engine-foundations'
date: '2026-06-10'
modified: '2026-06-10'
related: []
---



# `calculation-engine-foundations` audit: `Dormant calculation-parts census: every part not enrolled into the live calculate path (sonnet+opus audit swarm)`

## Scope

A four-axis sonnet+opus audit swarm (resolver/source-kind enrollment census; cross-modelo &
relation pipeline census; per-modelo filing-profile coverage; orphan/unreachable parts) over
the calculation engine at HEAD, to make the `calculation-engine-foundations` epic plan
EXPLICIT about every calculation part not yet enrolled into the live operator calculate path.
The live path is `calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`
(`application/modelo/_calculation_actions.py:419`); its authoritative enrollment is the
`merge_source_resolutions((...))` tuple (`:516-534`, three resolvers) plus three pre-mesh
gates (profile, borrador, iva_wallet_decision). Everything else is dormant. Counts/anchors are
the swarm's verbatim HEAD findings; minor cross-axis discrepancies are reconciled below.

## Findings

### F1 (CRITICAL) — every registry relation is dead on the live calculate path

`RelationPrefillSourceResolver` (`application/calculations/_relation_prefill.py:250`,
`owned_sources=("relation_prefill",)`) is NOT in the live mesh tuple; its only production
caller is the Google-Sheets workbook calc-sync (`_config/_google_sync_calc.py:113`). On live
calculate `relation_values` is populated ONLY by explicit `--relation` operator overrides
(`_calculate_input.py:210-217`), so `materialize_relation_binding_values` runs against an empty
dict and materialises nothing. Consequence: ALL 75 registry relations (39 `cross_model_output`,
28 `annual_summary`, 8 `previous_period`) are dead — the cross-modelo fold-ins they back blank
silently. Per domain: **M100** (←130 casilla 19 / ←131 / ←111 / ←115 / ←123 / ←180 / ←184 /
←190 / ←193, feeding the `0604` pagos-fraccionados computed casilla and the retenciones
credits), **M180←M115**, **M190←M111** (22 relations), **M193←M123**, **M200←M202** + M200 self
BIN/dotaciones-deterioro carries, **M202** prior-pagos cumulative + ←M200 cuota-base. EXCEPTION:
the M303 self-compensation `previous_period` relation DOES fire — via the IVA wallet gate (D3,
`_iva_wallet_gate.py`), not the relation mesh — so it is the one relation edge not silently
dead. (Axis B corrected the aggregation ADR's relation-kind counts: there are no `annual`/
`quarterly` relation kinds; `previous_period` is 8 not 6.)

### F2 — dormant source resolvers (implemented, tested, not enrolled)

Each exists with a full `.resolve()` and is exported, but is absent from the live enrollment:
`RelationPrefillSourceResolver` (relation_prefill; F1); `LedgerRentaIncomeAggregationSourceResolver`
(`_modelo_bindings.py:291`, `ledger_renta_income_aggregation` — **M130** actividad-económica
income, 3 bindings); `OssIossLedgerSourceResolver` (`_oss_ioss.py:232`, `ledger_oss_aggregation`
— **M369** OSS/IOSS, 5 bindings across 3 esquemas); `InvoiceCatalogueSourceResolver`
(`invoices/_source_resolver.py:29`, `collectible_invoice`/`payable_invoice` — **M349** + others,
17 bindings; `payable_invoice` is declared by NO registry binding — dead capacity or headroom).

### F3 — source kinds with NO mesh resolver at all (Sheets-pull-only)

These declare bindings but have no `ModeloSourceResolver` — only PULL-path `assemble_*`
functions in `application/calculations/_row_set_assembly.py` used solely by the Sheets calc-sync:
`withholding` (**M190/M193**, 13 bindings — the per-perceptor rollup; a resolver must be BUILT,
not merely enrolled), `atribucion_member` (**M184**, 4), `related_party_operation` (**M232**, 6),
`foreign_asset` (**M720**, 6), `refund_operation` (**M360**, 5). Confirmed: the standalone
`aggregate_per_modelo` CLI verb (`modelo aggregate`) does NOT feed the calculate engine, so these
remain genuinely un-enrolled for calculation.

### F4 — the safety net is built and switched off; the boundary is undocumented-as-gate

`collect_unhandled_source_diagnostics` (`application/aggregation/_source_mesh.py:242`) — which
flags a binding whose declared source has no enrolled resolver — has NO live-calculate caller
(only a unit test). So every F1/F2/F3 blank surfaces ZERO advisory (violates
no-silent-under-declaration). And `_BUCKET_AGGREGATION_OWNED_SOURCES`
(`_calculation_actions.py:89-93`) describes the enrolled set but enforces nothing: a new TOML
binding with a novel `source` passes `--collect-only`, compiles, and silently resolves to blank.
Estimated registry-orphan scale: 50–70 silently-skipped bindings across 7+ source kinds.

### F5 — disconnected-surface drift (Sheets-pull vs live-calculate)

The six `assemble_*` row-set functions + `resolve_relations_from_local_store` +
`resolve_modelo_ledger_binding_values_from_repositories` (`_modelo_bindings.py:347`, the M100
overview-display path) populate casillas the live `calculate_modelo_work_revision` cannot. Both
the Sheets-pull and the live-calculate path persist to the SAME revision, so a calculate-then-
export or export-then-calculate cycle yields divergent, conflicting casilla values with no
detection at save time. This is a correctness/drift hazard distinct from the silent-blank class.

### F6 — per-modelo live-fire matrix (reconciled)

LIVE (aggregation fully fires): M036/M210 (profile-only), M303, M309, M322, M390←M303 (direct
previous_filing), M353←M322 (direct, per_grupo_member), M100/M130(carry)/M131 same-modelo direct
carries, M180←M115 (direct previous_filing). PARTIAL: **M100** — its ledger-expense + direct
previous_filing carries fire, but its relation-based cross-modelo fold-ins (the 0604 credit +
retenciones from 111/115/123/180/190/193 + atribución 184) are DORMANT (reconciles the Axis-C
"LIVE" vs Axis-B "relations dormant" — M100 is partial). DORMANT (aggregation defined, never
fires): **M130** income, **M369** OSS, **M190/M193** withholding, **M349** invoices, **M184**
atribución, **M232** related-party, **M360** refund. MANUAL-ONLY by design: M111/M115/M123, M151,
M308, M347, M714, M721, M840, M720 (foreign-asset pull-only).

### F7 — orphan of unclear intent

`MultiYearResolver` (`_multi_year.py:398`) has a full `.resolve()` but ZERO callers (not even a
test); `PreviousFilingSourceResolver` does not delegate to it. No deprecation note or ADR. Intent
(dead stub vs mid-construction) cannot be determined from code — the epic must adjudicate (wire,
delete, or document). Also low: the `cross_period_dependency_inventory`/`_requirements`
top-level re-exports are vestigial (internal-only callers).

## Recommendations

Mapped to the epic plan waves:
- **F1 + F2 (enroll):** enroll `RelationPrefillSourceResolver`, `LedgerRentaIncomeAggregationSourceResolver`,
  `OssIossLedgerSourceResolver`, `InvoiceCatalogueSourceResolver` in the live mesh under the
  aggregation-taxonomy ADR's canonical taxonomy (relation for cross-modelo fold-in; ledger
  resolvers for projection) — W02.P06 + W03.P08. The relation enrollment + slot-hygiene
  (W03.P07) closes F1 for the whole 75-relation corpus at once.
- **F3 (build-or-defer):** the pull-only kinds need a per-kind decision — BUILD a `ModeloSourceResolver`
  (withholding is the highest-value, M190/M193) or DEFER-with-advisory; never silently blank.
  W02.P06 must enumerate each with its disposition.
- **F4 (non-negotiable):** wire `collect_unhandled_source_diagnostics` into the live path (W02.P05)
  and turn `_BUCKET_AGGREGATION_OWNED_SOURCES` into an enforced startup/registry gate (registry
  sources ⊆ enrolled-or-explicitly-deferred).
- **F5 (drift):** unify the Sheets-pull assemblers and the live calculate path on one resolver
  set so they cannot diverge (W03/W04 + a regression that pull == calculate for a shared revision).
- **F6:** every DORMANT/PARTIAL modelo gets an explicit enroll-or-defer step + an E2E live-fire
  proof (W04). F7: adjudicate `MultiYearResolver` in W02.P04.

## Codification candidates

- **Source:** F4 (the safety net is switched off; boundary unenforced).
  **Rule slug:** `no-dormant-source-resolvers`.
  **Rule:** Every source resolver merged to main MUST be enrolled in the live calculate mesh (or
  deleted), every registry binding `source` kind MUST have an enrolled resolver or an explicit
  deferred registration, and `collect_unhandled_source_diagnostics` MUST run on the live calculate
  path so an unrouted source surfaces a non-blocking advisory — never a silent blank.
- **Source:** F5 (pull vs calculate drift).
  **Rule slug:** `one-aggregation-path-pull-equals-calculate`.
  **Rule:** A casilla's value MUST be produced by the same aggregation logic whether reached via
  the live calculate path or the Sheets-pull path; the two surfaces share one resolver set and a
  regression proves they agree for a shared revision.

(The aggregation-taxonomy + period-revision ADRs already carry the canonical-mechanism, slot-source,
and revision-resolution rule candidates; this audit adds the two enforcement rules above.)

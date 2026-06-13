---
tags:
  - '#research'
  - '#modelo-iva-routing-carry'
date: '2026-06-09'
modified: '2026-06-09'
related: []
---



# `modelo-iva-routing-carry` research: `M303 special-IVA routing grounding and cross-period local-carry wiring design`

Grounding for the two items deferred from the `cli-ledger-testimonials` campaign and
re-scoped as explicitly in-scope: (2) Modelo 303 special-IVA casilla routing, and
(3) automatic cross-period `previous_filing` carry in the local file -> calculate flow.
Both groundings are read-only investigations against HEAD on `chore/eliminate-shims`;
all claims are anchored in the in-repo registry TOML, the LIVA (`Ley 37/1992`) corpus,
and the existing application code. The companion fresh-context verification that
surfaced these gaps is recorded in the `cli-ledger-testimonials` P05 audit addendum.

## Findings

### Item 2 — Modelo 303 special-IVA per-category disposition

The M303 `ledger_iva_aggregation` binding set (identical across the `2009-y-siguientes`
and `2023-y-siguientes` revisions) carries five cuota bindings: repercutido
general/reducido/super-reducido, soportado interiores, and autorepercutido
intracomunitaria. The classifier `_flow_direction_for` in
`src/aeat/application/aggregation/_iva_ledger.py` derives flow purely from the bank
`TransactionDirection` and emits only `REPERCUTIDO`/`SOPORTADO` — never
`INVERSION_SUJETO_PASIVO`, even though the substrate `derive_flow_for_classification` in
`src/aeat/domain/iva/_flow.py` already maps reverse-charge categories to that flow. The
advisory source is `unsupported_ledger_iva_observations` in
`src/aeat/domain/calculations/registry/_ledger_bindings.py`, which flags any declarable
observation no binding consumes.

Per-`IvaCategory` disposition (the 14 declarable values; `RECARGO_EQUIVALENCIA`,
`UNKNOWN`, `ERRONEOUS_INVOICE` are the three non-declarable omissions):

- **Class A — routes to a cuota casilla, already correct:** `DOMESTIC_GENERAL_21`
  (box 03, `art-88`+`art-90`), `DOMESTIC_REDUCED_10` (box 06, `art-91.Uno`),
  `DOMESTIC_SUPER_REDUCED_4` (box 09, `art-91.Dos`); their soportado side feeds box 29
  (`art-92`). All four LIVA articles are grounded in the repo legal catalogue + corpus.
- **Class B — cuota-less by law (the advisory must NOT fire on these):** `DOMESTIC_ZERO`,
  `DOMESTIC_EXEMPT` (`art-20`), `DOMESTIC_NOT_SUBJECT` (`art-7`), `OPERACION_NO_SUJETA`
  (`art-7`). Exempt/zero/not-subject produce no cuota.
- **Class C — off-M303 (cuota-less here):** `INTRA_COMMUNITY_SUPPLY` (exempt entrega
  `art-25`; base-only info box 59 + recapitulativa Modelo 349),
  `INTRA_COMMUNITY_TRIANGULATION` (`art-26`, informativa),
  `EXPORT_THIRD_COUNTRY_ZERO_RATED` (`art-21`, base-only info box 60),
  `REGIMEN_SIMPLIFICADO` (`art-122`/`123`, módulos path).
- **Class D — reverse-charge cuota that SHOULD route but currently cannot:**
  `DOMESTIC_REVERSE_CHARGE` (`art-84.Uno.2º`; output box 13 + deducible box 37; no binding
  exists and the flow is never emitted) and `INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE`
  (`art-84` + `art-15`; binding exists routing to the semantic
  `iva.autorepercutido.intracomunitaria` but is unreachable because the bank-direction
  classifier never produces `inversion_sujeto_pasivo`). `IMPORT_THIRD_COUNTRY` is a
  special case: output is settled at customs (DUA), only the deducible side (box 32/33)
  could appear on M303 and that input is not normally ledger-sourced.

Actionable tiers:

1. **Tier 1, fully grounded, ship-now:** fix `_flow_direction_for` to consult the
   `IvaCategory` via `derive_flow_for_classification` so reverse-charge categories emit
   `INVERSION_SUJETO_PASIVO`; add the net-zero devengado/deducible M303 bindings for
   `DOMESTIC_REVERSE_CHARGE` (boxes 13/37). Binding `legal_refs` = `ley-37-1992:art-84`
   (+ `rd-1624-1992:art-71`, `orden-eha-3786-2008:art-1`) — all already present in the
   catalogue + corpus, so no new grounding is required. The same flow fix makes the
   existing AIC binding reachable.
2. **Tier 1, ship-now, no grounding needed:** refine `unsupported_ledger_iva_observations`
   to exclude the Class B + Class C categories, so the `#64` advisory stops false-firing
   on cuota-less operations and keeps firing only on `DOMESTIC_REVERSE_CHARGE`,
   `INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE`, and `IMPORT_THIRD_COUNTRY` until their
   bindings land.
3. **Tier 2, grounding-gated:** eight LIVA articles are absent from BOTH the legal
   catalogue (`legal/*.toml`) and the corpus (`corpus/normatives/html/`): `art-7`,
   `art-13`, `art-15`, `art-17`, `art-20`, `art-22`, `art-25`, `art-26`. Per the
   registry-calculation-legal-grounding rule, no binding citing them may ship until each
   is defined with real BOE text + a resolvable `corpus_ref`. This gates the box-59
   (`art-25`) and box-60 (`art-22`) substantive grounding upgrades, the AIC official-box
   parity (boxes 10/11/36/37, `art-15`), and any import-deducible routing (`art-17`).

### Item 3 — cross-period local-carry wiring design

`PreviousFilingSourceResolver` (`src/aeat/application/calculations/_multi_year.py`) has
zero production callers; the calculate mesh in
`src/aeat/application/modelo/_calculation_actions.py` merges only the IVA + renta ledger
resolvers. `file_modelo_revision` passes `obs_repo` only to the read-side cross-period
clean-state guard and never calls `save_observation`, so locally-filed observations are
never persisted; the only production writer is the live AEAT-remote-capture path. Thus
local cross-period carry is manual-only (operator re-enters prior values via `--casilla`,
lifted by `_lift_previous_filing_casilla_overrides_to_bindings`).

Design (mirrors the live-capture template):

- **Persist on local file:** project the filed `CalculationRevision.observations` (all
  casillas, already provenance-bearing) into a `RegistryModeloObservation` keyed by
  `(modelo, filing_year, period)` in the bucket-scoped repository, via a new
  `persist_filed_revision_observation` helper called from `persist_filed_revision` after
  the catalogue saves, co-emitted with `MODELO_FILED` (the two-event composition pattern).
- **Enroll** `PreviousFilingSourceResolver` in the calculate mesh; its `binding_values`
  flow through the existing `backend_binding_values` channel. Precedence is already clean:
  auto fills the gap, the manual casilla-lift no-ops when the binding is already resolved,
  and caller `--binding` (highest precedence) overrides.
- **Safety (load-bearing):** the cross-period clean-state guard treats any `source_kind`
  not in `_OFFICIAL_SOURCE_KINDS` (`aeat_sede_justificante`, `aeat_sede_live_capture`,
  `aeat_csv_register`) as the blocker `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`. Locally
  filed observations must therefore carry a NON-official `source_kind` (`app_filing`) and
  must NOT be added to `_OFFICIAL_SOURCE_KINDS`: auto-carry makes a prior value available
  for calculate/draft, but filing a dependent period still requires external evidence.

Decisions requiring an ADR ruling: **D1** `app_filing` stays non-official (safety); **D2**
allow caller `--binding` override of carried `previous_filing` (keep it out of the
owned-binding rejection set); **D3** the resolver excludes the M303 IVA-compensation
binding (the iva-wallet decision owns it); **D4** grupo `per_grupo_member` fan-in is an
explicit non-goal for local filing. Mechanical (no ruling): persist-all-casillas, the
`(modelo, filing_year, period)` key, mesh-wiring location, co-emission ordering.

Minimal change set: a new `persist_filed_revision_observation` helper; edits to
`persist_filed_revision` + `file_modelo_revision` to call it; the resolver enrollment in
`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`; the owned-binding
rejection exclusion for `previous_filing`; the 303-compensation exclusion in the resolver;
top-level re-exports for any new public symbol. Tests: a local file -> calculate carry
E2E, a clean-state regression proving `app_filing` stays non-official, a 303-exclusion
regression, and an override-precedence test.

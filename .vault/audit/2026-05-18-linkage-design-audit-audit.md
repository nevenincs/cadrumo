---
tags:
  - '#audit'
  - '#linkage-design-audit'
date: '2026-05-18'
modified: '2026-06-29'
related:
  - "[[2026-05-15-linkage-design-audit-research]]"
  - "[[2026-05-15-linkage-design-audit-reference]]"
  - "[[2026-05-18-linkage-design-audit-plan]]"
  - "[[2026-05-15-linkage-design-audit-audit]]"
  - "[[2026-05-16-linkage-design-audit-audit]]"
  - "[[2026-05-17-linkage-design-audit-audit]]"
---

# `linkage-design-audit` audit: `Wave 4 close-out`

## Scope

Final close-out audit for the linkage-design epic. Covers the
operator-surface, identity-propagation, schema-attached
classification, and registry-data-backfill work delivered in the
fourth and final execution wave, plus the cumulative outcome
across all four waves measured against the 102-row inventory.

## Findings

### Severity: high — earlier closure claim was wrong

The previous draft of this audit stated "98 of 102 inventory rows
closed (96%)" based on inventory edits, not verification. A
scripted re-audit (`scratch/reaudit_inventory.py`) now covers
**all 102 inventory rows** and produces verdicts derived from
greps against current code:

| verdict           | count | share |
|-------------------|------:|------:|
| verified          |    48 |   47% |
| regressed         |    30 |   29% |
| partial           |    16 |   16% |
| open              |     2 |    2% |
| wontfix-confirmed |     4 |    4% |
| unverified        |     2 |    2% |

Honest closure: **48 of 102 rows verified (47%)**, not 96%.
Counting partials as "ingredient delivered" raises that to
**64 of 102 (63%)**. The 30 regressed rows are fixes that were
claimed `fixed (Wave N)` in the inventory but whose anti-pattern
is still present at the named site.

### Severity: high — historical regressed-row list with 2026-06-29 corrections

Every row listed below was marked `fixed (Wave N)` in the inventory
but the re-audit found the original anti-pattern still present at
the named site. Current-state notes identify rows whose original
anti-pattern has since been closed or narrowed.

- **Typed observation envelope (Wave 3, T-01).** `R003`, `R004`,
  `R005` — `RegistryCalculationResult.values` and
  `CalculationRevision.casilla_values` still typed as
  `Mapping[str, Decimal]`. The `CasillaObservation` envelope landed
  on `RegistryModeloObservation` (`R002` verified/currentized) but the
  surrounding calculation-result types kept the bare mapping.
- **Discriminated selector unions (Wave 1, T-01 / T-02).** `R007`
  is closed in current state: `DataBindingDefinition.selector` now
  stores a hydrated per-source pydantic selector model (`BindingSelector`)
  rather than the broad raw `BindingSelectorMap` authoring shape. The
  serializer projects the concrete model back to the authored selector
  mapping for dump/JSON compatibility. The same 2026-06-29 pass narrowed
  two production consumers of this gap: binding-derived export
  records now consume `BindingFixedExportSelector` /
  `BindingRowExportSelector` through `binding_export_selector`, and
  Detalle row-set assembly / Sheets layout now consume
  `BindingRowSetSelector` through `binding_row_set_selector`. The same pass
  narrowed public binding query rows: they now expose
  `BindingSelectorQueryProjection` / `BindingSelectorQueryEntry` ordered
  entries instead of the raw selector map. A follow-up 2026-06-29 pass made the
  construction-time selector registry fail closed for all 1,060 bundled
  registry bindings, including `withholding` and `retenciones_aggregation`;
  mesh-only `borrador` / `iva_wallet_decision` source kinds are refused as
  `DataBindingDefinition.source` values. The final 2026-06-29 pass verified
  all 1,060 bundled bindings carry concrete selector model instances and no
  production raw `binding.selector.get` / subscript path remains. Current-state recheck on
  2026-06-29 closed
  `R008` and `R009`: `RelationDefinition` now stores
  `source_revision_selector: RelationRevisionSelector` and
  `period_alignment: RelationPeriodAlignment`; legacy revision-id
  selector aliases, empty alignment maps, and retired `same_period`
  alignment are rejected at schema construction. The same recheck
  closed `R011`: `RelationDefinition` now uses
  `source_casilla_id: CasillaId`, rejects legacy `source_output`, and
  production code has no `relation.source_output` access.
- **Relation/selector internal plumbing (Wave 1/3).** `R014` —
  current-state recheck on 2026-06-29 closed the old
  `str(relation.source_output)` coercion: relation requirements group
  by `relation.source_casilla_id`; `R013` also closed the retired
  `RegistryRelationSourceRequirement`/`source_output` shape by using
  `RegistryFoldRequirement.source_modelo: ModeloId` and
  `source_casilla_ids: tuple[CasillaId, ...]`. `R016` —
  current-state recheck on 2026-06-29 closed the production
  `binding.selector.get("source_modelo")` path: record-design closure
  now asks the typed `binding_source_modelo(binding)` helper. `R015`
  is closed in current relation code: selector helpers consume typed
  `RelationRevisionSelector` attributes and no production
  `relation.source_revision_selector.get(...)` path remains; `R020` —
  current-state recheck on 2026-06-29 found
  `WorkbookParityReference.fixture_id` is now typed as
  `WorkbookFixtureId`; the remaining gap is absence of a
  fixture-catalogue lookup, not a bare string; `R024` — two
  `CasillaSchema` shapes still coexist (`runtime.py` + `_protocols.py`).
- **Renta routing (Wave 2, T-05).** `R025`, `R026` — current-state
  recheck on 2026-06-29 found the old unvalidated constant finding
  closed. `FIRST_SLICE_EXPENSE_CASILLAS` is the canonical
  Renta-domain routing table, `_ledger_expenses.py` re-exports the
  same object, and a `CrossDomainSnapshotCheck` validates every routed
  casilla against the Modelo 100 snapshot. The registry-side resolver
  consumes a Protocol and no longer imports `domain.renta`.
- **Errors / CLI surfaces (Wave 3/4).** `R045` —
  `RegistryValidationError` has no typed context field. `R050`,
  `R053` — `--relation` flag absent on `work calculate`;
  `RegistrySnapshotError` not caught in Google export. `R054` —
  `str(work_unit.modelo)` coercion still present.
- **Type-escape rows (Wave 1, T-11).** `R057`, `R058`, `R059` —
  `tomllib.loads`, session_store, authenticator still produce
  `dict[str, Any]`. `R068`, `R070` — magic-key `.get()` calls
  in `sede/_declarations.py` and `master_key`. `R073` —
  `CounterpartAggregationObservation.source_kind` still bare
  `str`. `R075` — public query selector still `Mapping[str, object]`.
  `R077` — `cast(RuleKind, ...)` still present.
- **Export plumbing (Wave 3, T-12).** `R089` —
  `fields_by_casilla: Mapping[str, ...]` still bare.
- **Workflow + filing (Wave 4, F14 / F20).** `R096` —
  `FilingDraft.schema_version: str` still bare; no `snapshot_ref`.
  `R097` — `WorkflowStep.details: dict[str, str] | None` still
  raw. `R101` — `LiveCrossReferenceDecision.oracle_id: str | None`
  still untyped. `R102` — no `OracleFilingObservation` subtype.

### Severity: medium — historical 16 partial closures; 12 remain after 2026-06-29 recheck

These rows landed a structural ingredient but the full fix did not.
Current-state recheck on 2026-06-29 closed the old `R017`, `R018`,
and `R021` validation-order claims for production access:
`ValidatedRegistryAuthority.load` runs full-tree `validate_registry`
before serving snapshots, and production snapshot builds now call
`check_all_id_references(snapshot)` before returning. `R046`,
`R047`, `R048` — CLI / review / diagnostics surfaces partially
expose `legal_refs` / cross-domain checks. `R095` — only
`profile_tax_id: str` (bare) on `FilingDraft`, not the typed
`SubjectTaxId` claimed.

Historical partial list: `R006`, `R017`, `R018`, `R019`, `R021`,
`R022`, `R046`, `R047`, `R048`, `R060`, `R064`, `R067`, `R069`,
`R071`, `R074`, `R095`. Current-state recheck closes `R017`,
`R018`, `R019`, and `R021`; the remaining partial set is `R006`,
`R022`, `R046`, `R047`, `R048`, `R060`, `R064`, `R067`, `R069`,
`R071`, `R074`, `R095`.

### Severity: informational — the 48 verified rows

What did actually land, grouped by theme:

- **Typed envelope foundation.** `CasillaObservation` on
  `RegistryModeloObservation` (`R002`); `AlgorithmBindingDefinition`
  targets / inputs / outputs typed (`R012`); relation source
  references currentized to `source_casilla_id` / typed fold
  requirements (`R011`, `R013`, `R014`).
- **Capability flags replace hard-wired modelo strings.**
  `_borrador_binding` migrated to capability lookup (`R034`);
  renta-ledger default removed (`R035`); `ModeloDefinition.output_sensitivity`
  schema field exists (`R036`); justificante repository reads
  `output_sensitivity` from schema (`R037`).
- **Registry → renta import inversion** (`R028`).
- **CCAA canonicalisation.** RentaCCAA migrated (`R029`); CCAA
  factories present (`R030`); M100 2025 dispatch labels canonical
  (`R031`).
- **Registry data backfill.** M100 2025 per-casilla `export_refs`
  (`R032`); M100 cross_model_output backfilled for 2020-2024
  (`R033`); M303 `form_number` declared (`R098`).
- **CLI typed payloads + emit.** `SchemaEnvelope` at 20+
  `register_schema` sites (`R043`); no raw-dict `_emit` in
  `_modelo.py` (`R044`); `--prefill-relations` flag on Google
  export (`R052`); `relation_values` plumbed through application
  (`R051`); typed work_unit_id parse (`R055`).
- **Other cross-domain.** `core/identity` propagated to filing
  (`R094`); informative-class registry-wide invariant (`R100`);
  `LiveCrossReferenceDecision` / `DependencyClassificationDefinition`
  separation (`R099`).
- **Type-escape clean-up (T-11 subset).** R001, R010, R015, R023,
  R027, R056, R061-R063, R065-R066, R072, R076, R078-R086, R087,
  R090-R093 — 25 individual type-escape and validation-erasure
  sites confirmed clean.

### Severity: medium — gate status snapshot

Running the unified linkage-health dashboard at close-out:

- ty: PASS (0 errors, 0 warnings).
- pyright `src/aeat/domain`: 32 errors, 97 warnings — driven by
  `reportPrivateUsage` (41), `reportUnnecessaryIsInstance` (33),
  `reportMissingParameterType` (23), `reportUnusedFunction` (15).
- pyright `src/aeat/application`: 146 errors, 97 warnings — driven
  by `reportMissingParameterType` (130), `reportPrivateUsage`
  (73), `reportArgumentType` (15), `reportUnusedFunction` (14).
- import-linter: 2 contracts kept, 2 contracts broken (the
  `layered` and `domain-not-application` legacy contracts) —
  recorded as inherited debt, not new regression.
- suppression inventory: 175 total ty:ignores. 99 are external-API
  shim suppressions (pydantic generics, click decorators); 76 are
  internal. The internal count is the actionable follow-up surface.
- pydantic-duplicate audit: 813 BaseModel subclasses; 4 name
  duplicates; 86 field duplicates across modules; 272 high-
  similarity pairs. The similarity heuristic is intentionally
  noisy — the actionable surface is the name-duplicate set.

The dashboard is now the canonical successor to the agent-driven
discovery phase. Pyright errors are the next actionable surface
once the canonical structural work is locked in.

### Severity: low — deferred items

Four inventory rows remain open and are explicitly tracked as
follow-up:

- Two import-linter contracts (`domain.deadlines._profiles` and
  `domain.profile._keys` lazy imports) need a deeper refactor that
  was out of scope for the typed-envelope and capability-flag
  work.
- One extra-forbid gap on a single legacy pydantic model is left
  as-is because its sole caller is a registry-internal builder
  that already constrains keys upstream.
- One row is owned by the corpus-registry packaging plan
  (separate execution stream).

Five rows are recorded as wontfix-document with rationale captured
inline in the research record.

## Recommendations

- **Do not treat this epic as closed.** The structural work
  named in earlier drafts of this audit was not delivered. A
  follow-up phase is needed to land the selector discriminated
  unions, the remaining relation/standalone-validation ordering work,
  the `WorkflowStep.details` typed union, the FilingDraft typed
  identity / snapshot reference, the Oracle typing, the CLI
  `--relation` flag, and the Google-export `RegistrySnapshotError`
  catch. The old `RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS` removal item
  is no longer a live prerequisite after the 2026-06-29 recheck: the
  current design keeps Renta-owned routing and validates it at snapshot
  construction.
- Re-run the re-audit script against the remaining 67 unvisited
  inventory rows before any subsequent closure claim. Extend the
  script with one verdict function per row so the verdict is
  derivable from code rather than from memory.
- The reference appendix coverage table should be regarded as the
  authoritative state going forward. Inventory cells in the
  research record were edited optimistically during execution;
  the reference table is now grounded in the re-audit.
- Keep the `scratch/` tooling on disk. The re-audit script joins
  the suppression-inventory, pydantic-audit, and linkage-health
  scripts as durable infrastructure.
- Pyright error counts (32 in domain, 146 in application) and the
  76 internal ty:ignores remain real follow-up surface but are
  secondary to landing the structural fixes above.

---
tags:
  - '#audit'
  - '#linkage-design-audit'
date: '2026-05-18'
modified: '2026-05-18'
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

### Severity: high — full list of 30 regressed rows

Every row listed below was marked `fixed (Wave N)` in the inventory
but the re-audit found the original anti-pattern still present at
the named site:

- **Typed observation envelope (Wave 3, T-01).** `R003`, `R004`,
  `R005` — `RegistryCalculationResult.values` and
  `CalculationRevision.casilla_values` still typed as
  `Mapping[str, Decimal]`. The `CasillaObservation` envelope landed
  on `RegistryFilingObservation` (`R002` verified) but the
  surrounding calculation-result types kept the bare mapping.
- **Discriminated selector unions (Wave 1, T-01 / T-02).** `R007`,
  `R008`, `R009`, `R011` — `DataBindingDefinition.selector`,
  `RelationDefinition.source_revision_selector`, `period_alignment`,
  `RelationDefinition.source_output` all still bare `Mapping[str, ...]`
  or `CasillaId | str` union escapes.
- **Relation/selector internal plumbing (Wave 1/3).** `R014` —
  `str(relation.source_output)` coercion still present; `R016` —
  `binding.selector.get("source_modelo")` raw lookup still
  present; `R020` — `WorkbookParityReference.fixture_id` still
  bare `str`; `R024` — two `CasillaSchema` shapes still coexist
  (`runtime.py` + `_protocols.py`).
- **Renta constant (Wave 2, T-05).** `R025`, `R026` —
  `RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS` constant still defined
  in `domain/renta/_ledger_expenses.py` and the validator still
  uses it. Note: the cross-package re-validation in
  `_bindings.py` (`R027`) IS removed.
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

### Severity: medium — 16 partial closures

These rows landed a structural ingredient but the full fix did not.
Most actionable next-phase candidates: `R017`, `R018`, `R021` —
the validation functions are defined and tested but **not wired
into `build_snapshot`**, so production registry builds skip
referential-integrity and relation-closure gates entirely. `R046`,
`R047`, `R048` — CLI / review / diagnostics surfaces partially
expose `legal_refs` / cross-domain checks. `R095` — only
`profile_tax_id: str` (bare) on `FilingDraft`, not the typed
`SubjectTaxId` claimed.

Full partial list: `R006`, `R017`, `R018`, `R019`, `R021`, `R022`,
`R046`, `R047`, `R048`, `R060`, `R064`, `R067`, `R069`, `R071`,
`R074`, `R095`.

### Severity: informational — the 48 verified rows

What did actually land, grouped by theme:

- **Typed envelope foundation.** `CasillaObservation` on
  `RegistryFilingObservation` (`R002`); `AlgorithmBindingDefinition`
  targets / inputs / outputs typed (`R012`).
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
  unions, the `_check_all_id_references` wiring at `build_snapshot`,
  the `WorkflowStep.details` typed union, the FilingDraft typed
  identity / snapshot reference, the Oracle typing, the CLI
  `--relation` flag, the Google-export `RegistrySnapshotError`
  catch, and the removal of `RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS`.
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

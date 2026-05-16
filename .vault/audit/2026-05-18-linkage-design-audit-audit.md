---
tags:
  - '#audit'
  - '#linkage-design-audit'
date: '2026-05-18'
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
scripted re-audit (`scratch/reaudit_inventory.py`) re-walked a
35-row sample against current code and found:

- **14 rows verified** (anti-pattern actually gone).
- **11 rows regressed** (claim of `fixed` was wrong; the
  anti-pattern is still present at the named site).
- **3 rows partial** (a structural ingredient landed; the full fix
  did not).
- 2 rows `open` and 4 rows `wontfix-confirmed` (these match the
  inventory's labels).

On the sampled subset, ~31% of `fixed` claims do not hold up.
67 rows of the 102 were not visited by the re-audit script and
remain unverified.

### Severity: high — structural fixes that did not land

The following defect-class closures named in the reference
appendix are wrong as written; the underlying anti-pattern is
still present in current code:

- **Discriminated selector unions** on `DataBindingDefinition.selector`,
  `RelationDefinition.source_revision_selector`, and
  `period_alignment` (T-01 / T-02). All three are still bare
  `Mapping[str, ...]`. The `BindingSelector` discriminated `Union`
  does not exist in `_schema.py`.
- **Snapshot referential-integrity gate** (T-03 / T-09). The
  `_check_all_id_references` validator is defined and tested but
  **not invoked by `build_snapshot`**. Production builds do not
  run the 21-typed-ID existence check; only the dedicated tests do.
- **`WorkflowStep.details` discriminated union** (operator surface).
  `details: dict[str, str] | None` is still in `_models.py`. The
  `WorkflowStepDetails` union does not exist.
- **FilingDraft typed identity**. `subject_tax_id` was claimed
  added; the field present is `profile_tax_id: str` (bare `str`).
  `schema_version: str` is still bare `str`; no `snapshot_ref`
  field exists.
- **Oracle typing**. `LiveCrossReferenceDecision.oracle_id: str | None`
  remains untyped. No `OracleFilingObservation` subtype exists.
- **CLI `--relation` flag on `work calculate`** is absent. The
  application-layer plumbing (`relation_values` kwarg) is present;
  the CLI surface is not.
- **`_load_snapshot` error handling** on the Google export path
  does not import or catch `RegistrySnapshotError`.
- **`RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS`** hardcoded mapping is
  still present in `domain/renta/_ledger_expenses.py`.

### Severity: informational — what actually did land

- `CasillaObservation` typed envelope on
  `RegistryFilingObservation` (verified).
- `AlgorithmBindingDefinition` target / inputs / outputs typed
  (verified).
- `_MODELO_100` gate replaced with capability lookup in
  `_borrador_binding` (verified).
- `_renta_ledger` modelo default removed (verified).
- Registry → `domain/renta` import inversion (verified).
- `RentaCCAA` migration to canonical CCAA enum (verified).
- `SchemaEnvelope` adoption at 20+ `register_schema` sites in
  `_modelo_payloads.py` (verified).
- No raw-dict `_emit` calls remain in `_modelo.py` (verified).
- Justificante repository reads `output_sensitivity` from schema
  (verified).
- `--prefill-relations` flag on `aeat config export` (verified).
- M303 `form_number` declared; M100 2025 per-casilla `export_refs`
  present (verified).

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

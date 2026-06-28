---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-03-calculation-truth-registry-rebuild-plan]]"
---

# modelo-100-bulk-segmentation-audit

`registry/aeat/modelos/100.toml` is **145,900 lines** and grows ~10% per
fiscal year. This audit measures the bulk drivers, identifies the
redundancy pockets that can be eliminated without information loss, and
proposes a phased path from a single 145K-line file to a maintainable
structure under ~50K lines through pydantic-default elimination plus
cross-revision deduplication.

## findings: where the bulk lives

| Element kind | Lines | % of file |
| :----------- | ----: | --------: |
| casillas | 113,139 | 77.5% |
| formulas | 13,542 | 9.3% |
| constructs | 2,553 | 1.7% |
| parameters | 1,219 | 0.8% |
| application_links | 611 | 0.4% |
| bindings | 447 | 0.3% |
| live_cross_references | 193 | 0.1% |
| dependency_classifications | 144 | 0.1% |
| relations | 136 | 0.1% |
| workbook_parity_refs | 118 | 0.1% |
| export_layouts | 92 | 0.1% |

**Casillas dominate at 77.5%.** They are the leverage point.

## findings: per-revision growth

| Revision | Lines | Casilla blocks |
| :------- | ----: | -------------: |
| 2020 | 19,922 | 1,531 |
| 2021 | 21,742 | 1,693 |
| 2022 | 23,744 | 1,852 |
| 2023 | 24,622 | 1,929 |
| 2024 | 26,087 | 2,062 |
| 2025 | 29,720 | 2,235 |
| **Total** | **145,900** | **11,302** |

Year-over-year growth is steady. Without intervention the 2026 revision
will land near 31,000 lines, and the file will hit 200K by 2028.

## findings: redundancy fingerprint

Across 11,302 casilla blocks:

| Field | Value | Count | % of casillas |
| :---- | :---- | ----: | ------------: |
| `required` | `false` | 11,295 | **99.9%** |
| `binding` | (omitted) | 11,272 | 99.7% |
| `formula` | (omitted) | 11,267 | 99.7% |
| `input_kind` | `"manual"` | 11,218 | **99.3%** |
| `data_type` | `"money"` | 8,219 | **72.7%** |
| `data_type` | `"text"` | 2,078 | 18.4% |
| `data_type` | `"decimal"` | 502 | 4.4% |
| `data_type` | `"boolean"` | 500 | 4.4% |
| `data_type` | `"integer"` | 3 | 0.0% |

The three top-frequency fields are above 70% — strong default-eligible.

## findings: cross-revision duplication

| Stratum | Count | Cumulative casilla blocks |
| :------ | ----: | ------------------------: |
| Unique casilla IDs (across all revisions) | 2,254 | — |
| ID present in all 6 revisions | 1,476 | 8,856 (78% of all blocks) |
| ID present in 5+ revisions | 1,697 | 8,485 |
| ID present in 3+ revisions | 1,946 | 5,838+ |
| ID present in only 1 revision | 172 | 172 |

**1,476 of 2,254 unique IDs (65%) repeat verbatim 6 times each.** Those
8,856 blocks are pure duplication carrying ~80,000 lines that could
collapse to ~1,476 shared blocks with per-revision overrides for the
small subset that differs.

## proposed phased plan

### Phase 1 — Pydantic defaults (no schema breaking change)

**Effort**: small. **Risk**: low. **Savings**: ~30,700 lines (21%).

Add defaults to `CasillaDefinition` at
`src/aeat/domain/calculations/registry/_schema.py:788`:

```python
class CasillaDefinition(RegistryModel):
    id: CasillaId
    number: str
    label: str
    section: tuple[str, ...]
    data_type: Literal["decimal", "money", "integer", "ratio", "text", "boolean"] = "money"
    required: bool = False
    input_kind: Literal["manual", "bound", "computed", "informational"] = "manual"
    formula: FormulaId | None = None
    binding: BindingId | None = None
    validation_refs: tuple[str, ...] = ()
    export_refs: tuple[ExportFieldId, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs
```

Then run a sweep over `100.toml` (and other modelos that use the same
schema) removing lines where the value already equals the new default.
Estimated savings:

- Drop `required = false` × 11,295 → save 11,295 lines
- Drop `input_kind = "manual"` × 11,218 → save 11,218 lines
- Drop `data_type = "money"` × 8,219 → save 8,219 lines

**Total Phase 1 savings: ~30,732 lines** (21% of file).

The schema validator at line 805-808 (`_validate_input_kind`) keeps
working — it validates `input_kind == "computed"` requires a formula,
which is unaffected by defaults.

### Phase 2 — File segmentation (registry loader change)

**Effort**: medium. **Risk**: medium. **Savings**: maintainability,
not lines.

Split `registry/aeat/modelos/100.toml` into a directory:

```
registry/aeat/modelos/100/
  manifest.toml          # modelo-level metadata + revision list
  shared/                # cross-revision shared elements
    constructs.toml
    parameters.toml
    legal_refs.toml
  revisions/
    2020.toml
    2021.toml
    2022.toml
    2023.toml
    2024.toml
    2025.toml
```

Each revision file holds only that year's data (~5,000 lines after
Phase 1 + Phase 3). Manifest file is small.

**Backend changes required** (
`src/aeat/domain/calculations/registry/_load.py` and friends):

- Loader detects directory mode if `manifest.toml` exists at
  `registry/aeat/modelos/{modelo}/`.
- In directory mode, loader merges `shared/*.toml` + `revisions/*.toml`
  into the same in-memory `Modelo` structure that single-file mode
  produces. Public API unchanged.
- Validator runs identically; no schema change.
- Snapshot / scenario test framework unchanged.

### Phase 3 — Cross-revision deduplication (schema extension)

**Effort**: large. **Risk**: medium. **Savings**: ~80,000 lines.

Introduce a `revisions.shared` block where casillas common to all (or
declared) revisions live once. Per-revision blocks become smaller:

```toml
[[revisions.shared.casillas]]
id = "0003"
number = "0003"
label = "Rendimientos del trabajo dineraria"
section = ["...", "..."]
applies_to_revisions = ["2020", "2021", "2022", "2023", "2024", "2025"]
legal_refs = [...]
source_refs = [...]

# Per-revision overrides only when the field differs:
[[revisions."2025".casillas_overrides]]
id = "0003"
label = "Rendimientos del trabajo dineraria (2025 update)"
```

Loader merges shared + overrides per revision at load time. The
in-memory representation stays the same; per-revision Modelo still
has 2,235 casillas in 2025, but the on-disk file shrinks.

**Estimated Phase 3 savings: ~80,000 lines** if applied to all 1,476
shared-across-6-revisions IDs.

### Phase 4 — Section-based grouping (deferred)

**Effort**: large. **Risk**: high.

Many casilla blocks share section paths (e.g. 892 share
`["toma_datos_ampliada", "inmuebles", "inmueble"]`). Section blocks
could declare the path once with casillas inside:

```toml
[[revisions."2025".sections."inmuebles_inmueble"]]
section = ["toma_datos_ampliada", "inmuebles", "inmueble"]

  [[revisions."2025".sections."inmuebles_inmueble".casillas]]
  id = "0050"
  ...
```

Defer until Phases 1-3 land; the marginal saving (a single line per
casilla declaration) is small relative to the work to refactor every
section reference in the codebase.

## projected end state

| Phase | Lines | % of original |
| :---- | ----: | ------------: |
| Today | 145,900 | 100% |
| After Phase 1 (defaults) | ~115,000 | 79% |
| After Phase 1 + 2 (split, no dedup) | ~115,000 (across 8+ files) | 79% |
| After Phase 1 + 2 + 3 (dedup) | ~50,000 (across 8+ files) | 34% |

The largest single revision file under Phase 1 + 2 + 3 would land near
~5,000 lines (vs. 29,720 today for 2025).

## non-negotiables — information preservation

Every phase must preserve:

- **All 11,302 casilla declarations** in their entirety (no field
  removal; defaults eliminate redundancy at the file layer only)
- **Every `legal_refs` entry** — schema integrity for the audit pipeline
- **Every `source_refs` entry** — corpus authority for citations
- **Every formula expression** verbatim
- **Every binding selector** — cross-modelo wiring depends on it
- **Every section path** — used by exporter / live-replay surface
- **Every workbook_parity_ref** — parity tape coverage
- **Every revision boundary** — formal validity windows

The phases land mechanically (script-driven). After each phase, the
canonical test suite must pass with no behavioral changes:

- `src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py`
- `src/aeat/domain/calculations/registry/test_renta_2025_synthetic_profile.py`
- `src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
- `src/aeat/domain/calculations/registry/test_modelo_100_drift_detection.py`

## execution sequencing

The phases compose well if landed in order:

1. **Phase 1 first** — pydantic defaults + sweep. One PR, single commit
   per modelo. Reversible. Test suite catches regressions immediately.
2. **Phase 2 second** — file split. Loader change + structural move.
   PR can land alongside the directory move. Test suite validates the
   merged in-memory shape matches single-file load.
3. **Phase 3 third** — cross-rev dedup. New schema construct
   (`shared` block + overrides). Per-modelo migration scripts.

Phases can run in this order on modelo 100 only first, then on the
remaining annual-revision modelos (only modelo 100 has the bulk
problem; other modelos use the "y-siguientes" pattern and are < 1,000
lines each).

## next actions

- Land Phase 1 immediately on modelo 100 (it is reversible, low-risk,
  and unblocks ~30K lines of pure noise)
- Write an ADR formalizing the file-split + shared-block schema
  extension before Phase 2/3 land
- Update `.vaultspec/` rules / docs to capture the segmentation
  guidelines so future modelos follow the pattern from day one

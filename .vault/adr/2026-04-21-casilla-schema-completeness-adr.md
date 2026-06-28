---
tags:
  - "#adr"
  - "#casilla-schema-completeness"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-casilla-schema-completeness-research]]"
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
  - "[[2026-04-21-pdf-taxonomy-adr]]"
  - "[[2026-04-12-filing-draft-engine-adr]]"
---

# `casilla-schema-completeness` adr: `make-the-casilla-corpus-complete-provenanced-and-cross-validated` | (**status:** `accepted`)

## Problem Statement

The casilla corpus has 4 / 4 / 3 entries for modelos 130, 303, 390 — respectively 21 %, ~5 %, ~0.4 % of real form coverage. Rulesets in `src/aeat/domain/formulas/_rulesets/` already reference casillas that are absent from the corpus (Modelo 130 ruleset: 9 formula casillas vs 4 in corpus), producing silent correctness bugs: drafts built today are missing most of the casillas the form requires. No test catches this. PDF-extraction work (clusters D, F) against real filing PDFs will produce `ExtractedCasilla` tuples whose IDs the corpus does not recognise, and the builder will silently drop them. Before any extractor is useful, the corpus must (a) cover every real-form casilla, (b) agree with its ruleset, and (c) carry source citations so the legal authority of every entry is auditable.

## Considerations

- AEAT publishes four independent sources that define a modelo's casillas: **BOE order** (legal), **Manual práctico** (operational), **interactive form XML on Sede electrónica** (machine-readable), **printed form PDF** (human-readable). Only the XML path is ready for deterministic ingest; BOE is parseable but pattern-narrow (Modelo 130 only today); Manual is stub.
- `CasillaSchema` (at `src/aeat/application/filing/_protocols.py`) already models `id`, `value_type`, `required`, `formula_inputs`, `min_value`, `max_value`, `default` — adequate for the real-form casilla set but missing provenance fields.
- Rulesets (`src/aeat/domain/formulas/_rulesets/modelo_*.py`) are today the de-facto source of truth for "which casillas exist" on the modelos that have a formula implementation. They cover 130 and 303 only; no 390 ruleset exists (see #221).
- The formula engine (`src/aeat/domain/formulas/_engine.py`) exposes `Engine.audit_against(ruleset, provided, tolerance) -> AuditReport` — cluster E's round-trip verification primitive. The primitive can only audit casillas the ruleset knows; extending the ruleset is therefore part of this cluster's scope for 130 / 303.
- Year-over-year casilla renumbering is a real phenomenon (303 *autoliquidación rectificativa* renumbered casillas from 2024-09 onward). The ADR must bake in versioning.
- Trilingual labels per project mandate — Spanish authoritative, English + Hungarian companion.
- The repo already has `corpus/casillas/modelo_*/YYYYXX.json` as the on-disk shape. We extend, not replace.

## Constraints

- **No breakage of `#271` shipping contract.** `aeat.domain.justificante`, `FilingDraft.draft_id` hash shape, `SubmittedFiling`, amendment baseline flow — all untouched.
- **Strict+frozen pydantic v2** for every record; extra fields forbidden.
- **Spanish label authority**; English + Hungarian as companions. `Translatable` TypedDict.
- **No cert coupling**; all authoritative sources are publicly fetchable.
- **No test skips**; every schema test runs in `@pytest.mark.unit` with module-level markers.
- **Relative imports** inside `src/aeat/`.
- **Reproducibility**: any auto-generated corpus artefact must carry the SHA-256 of its source input file so upstream drift is detectable.

## Implementation

### 1. Extend `CasillaSchema` with provenance

Edit `src/aeat/application/filing/_protocols.py`:

```python
class CasillaSource(BaseModel):
    """Authoritative citation chain for one casilla."""
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    kind: Literal["boe", "manual", "interactive_form_xml", "printed_form_pdf"]
    citation: str             # e.g., "Orden HAC/610/2024, art. 3.2"
    url: AnyHttpUrl | None
    retrieved_at: date | None
    snapshot_sha256: str | None  # SHA-256 of the source file, for drift detection


class CasillaSchema(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    id: str
    value_type: Literal["decimal", "int", "str", "bool", "date"]
    required: bool
    formula_inputs: tuple[str, ...] = ()
    min_value: Decimal | int | None = None
    max_value: Decimal | int | None = None
    default: FilingScalar = None
    label: Translatable                        # NEW — trilingual
    description: Translatable | None = None    # NEW — long-form trilingual
    sources: tuple[CasillaSource, ...]         # NEW — ≥1 source required
    valid_from: date | None = None             # NEW — year versioning
    valid_to: date | None = None               # NEW — year versioning
```

The existing 11 corpus files (4+4+3) are rewritten to carry `label`, `sources`, `valid_from=date(2025,1,1)`. Backwards-compatible: pydantic migration is handled in the loader (cluster plan §2).

### 2. Enforce corpus ↔ ruleset agreement

New test at `src/aeat/application/filing/test_schema_completeness.py`:

```python
@pytest.mark.unit
@pytest.mark.domain_infra
def test_corpus_covers_every_ruleset_casilla_for(
    modelo: str, año: int,
) -> None:
    """Every casilla mentioned in the ruleset must appear in the corpus."""
    collection = build_runtime_schema_provider().get_collection(modelo)
    ruleset = load_ruleset(modelo, año)
    corpus_ids = {c.id for c in collection.all()}
    ruleset_ids = set(ruleset.casilla_ids())
    missing = ruleset_ids - corpus_ids
    assert not missing, f"Ruleset references casillas missing from corpus: {sorted(missing)}"
```

Parametrised per `(modelo, año)` pair that both sides have. The test lives alongside the schema provider and runs on every unit sweep. Currently fails on Modelo 130 (5 missing casillas); its success is the acceptance gate for step 4.

### 3. Define the schema-complete bar per modelo

For Modelo N to count as "schema-complete":

- Every casilla ID printed on the real AEAT form for that modelo in that year appears in `corpus/casillas/modelo_N/YYYY.json`.
- Every casilla in the corpus has a `sources` tuple with ≥1 entry.
- Every casilla with `formula_inputs` non-empty has its inputs also in the corpus.
- The ruleset for that modelo (if it exists) references only casillas in the corpus; the corpus references only formulas the ruleset implements.
- A test file `test_schema_modelo_N.py` asserts the count equals the AEAT-published form's casilla count and that no casilla is missing provenance.

### 4. Delivery order

1. **Modelo 130 (2025)** — 19 casillas. Ruleset exists. Smallest. Target delivery: cluster plan.
2. **Modelo 303 (2025)** — ~88 casillas. Ruleset exists. Complete after 130.
3. **Modelo 390 (2025)** — ~680 casillas. Ruleset **missing**; tracked in #221. This cluster delivers the corpus; #221 delivers the ruleset. The cross-validation test is parametrised skip for 390 until #221 lands.
4. **Modelos 111, 115, 180, 190** — deferred. Added row per modelo in `docs/coverage/modelos.md` with status `🚧 corpus` placeholder.
5. **Modelo 100 (RENTA)** — cluster F scope.

### 5. Source strategy: interactive form XML as primary

`src/aeat/domain/schema/_forms_xml_loader.py` (new):

- Downloads the AEAT interactive form XML for a given `(modelo, año)` from the public Sede electrónica URL pattern.
- Stores the raw XML under `corpus/_sources/interactive_forms/modelo_N/YYYY.xml` with its SHA-256 recorded.
- Parses the XML into the shared `CasillaSchema` shape; writes to `corpus/casillas/modelo_N/YYYY.json`.
- Deterministic output: same input XML → same output JSON bytes (sorted keys, fixed number formatting).

A separate `just regen-corpus` target re-runs the loader for every `(modelo, año)` pair. The loader is **not** invoked at runtime; corpus JSON is committed.

Fallback for modelos where the interactive form XML is unavailable: a BOE PDF fallback wired to `src/aeat/domain/schema/_boe_extractor.py`. Implemented only if needed — scope depends on which modelos XML covers.

### 6. Ruleset completion (scoped to cluster)

- Modelo 130 ruleset extended from 9 to 19 casilla formulas (or 19 casilla literals where no formula exists — the ruleset registers literals too).
- Modelo 303 ruleset extended from 12 to ~88 casilla formulas / literals.
- Modelo 390 ruleset: **not scope of this cluster**; tracked in #221.

Each ruleset extension follows the existing shape in `_rulesets/modelo_130_2025.py`: a registry of named formulas and literals keyed by casilla ID.

### 7. Coverage-matrix updates

`docs/coverage/modelos.md` gains a casilla-count column:

| Modelo | … | Casillas in corpus | Target casillas (real form) | % coverage |
| --- | --- | --- | --- | --- |

Updated as each modelo ships.

### 8. Explicitly out of scope

- Any PDF extractor code. That's cluster D.
- Modelo 100 corpus. That's cluster F.
- Modelo 390 ruleset. Tracked in #221.
- Per-casilla legal interpretation. Ruleset authors resolve semantic ambiguity; corpus only enumerates IDs and types.
- Translation of labels. ES authoritative; EN and HU can land on best-effort and carry a `needs_human_review` flag that the CLI can surface as advisory — but label-completeness is not a merge gate.

## Consequences

- The corpus becomes authoritative for "which casillas exist on the form." Any extractor (cluster D) can rely on the corpus; any formula ruleset can pin against it.
- Silent correctness bugs (Modelo 130 drafts missing 15 of 19 casillas) are caught by a parametrised test on every unit sweep.
- Provenance is trackable: every casilla carries a `sources` tuple citing BOE / manual / XML / PDF with SHA-256 snapshots. An audit against the AEAT source is a `git log` + hash check away.
- Year versioning via `valid_from` / `valid_to` means the 2024→2025 renumbering of Modelo 303 post-*autoliquidación rectificativa* is representable.
- Real-PDF extraction becomes feasible: when Kent drops a real declaración PDF into cluster D, every casilla ID the extractor finds is in the corpus, and the builder honours it instead of silently dropping.
- Cluster E's round-trip verification runs over the full form, not 21 %.
- Modelo 100 gains a concrete schema target for cluster F instead of "figure it out later."

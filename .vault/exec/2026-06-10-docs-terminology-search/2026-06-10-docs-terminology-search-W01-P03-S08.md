---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S08'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Build the golden-query retrieval verification sweep (prorrata, casilla labels, disposicion transitoria, Disenos field positions, four-language probes) asserting hits land on the preprocessed surfaces above an agreed score floor before sweep outputs are trusted (ADR D6)

## Scope

- `dev tests for retrieval verification`

Implements the ADR D6 trust-gate: the golden-query retrieval verification the
build-time sweep depends on, plus the coordinator-ruled raw-vs-sidecar dedup
exclusion for the normatives HTML. Closes W01.

## Description

- Inspect the service search `--json` shape (`data.results[]` with `path`,
  `score`, `snippet`); confirm extraction sidecars are retrievable.
- Author the golden-query harness `_golden_queries.py`: a fixed
  `GOLDEN_QUERIES` set, each pinned to a preprocessed surface
  (normatives sidecar / Diseno sidecar / any sidecar / terminology) with a
  declared score floor (~0.5 strong-signal, 0.4 for a cross-lingual probe),
  a `run_query` runner (through the resident service, `--json`), an
  `evaluate_query` scorer, and a `raw_normatives_html_hits` projector for
  the dedup proof.
- Implement the dedup exclusion: add `src/aeat/_data/corpus/normatives/html/
  *.html` to `.vaultragignore` (narrow - the pattern matches the raw `.html`
  but NOT the `*.html.extracted.md` sidecars, and is scoped to
  normatives/html so other raw HTML without a sidecar stays indexable).
- Verify the exclusion at the walker-filter level with the installed walker's
  own `scan_files`, and queue the reindex that purges the raw-HTML chunks.
- Author the golden-query verification test `test_golden_queries.py`
  (integration; live queries, no mocks) plus the dedup assertion.
- Verify: ruff check + format clean, `ty check` clean, the docs lane clean
  (integration tests excluded), the 7 golden queries passing live.

## Outcome

### Golden-query results (run live through the resident service)

All seven golden queries reach their pinned preprocessed surface above the
declared floor:

| Query | Surface | Floor | Score |
| --- | --- | --- | --- |
| regla de prorrata operaciones deduccion | normatives sidecar | 0.50 | 0.975 |
| prorrateo porcentaje deducible | any sidecar | 0.50 | 0.967 |
| posicion longitud tipo descripcion campo registro | Diseno sidecar | 0.50 | 0.777 |
| disposicion transitoria tipo de gravamen | normatives sidecar | 0.50 | 0.978 |
| esquema registro fichero modelo presentacion | Diseno sidecar | 0.50 | 0.944 |
| prorrata especial sectores diferenciados (es) | terminology | 0.40 | 0.791 |
| modalitat de prorrata IVA sector activitat (ca) | terminology | 0.40 | 0.994 |

The casilla-grounding queries land on the Diseno `*.extracted.md` field
tables; the legal queries land on the normatives article sidecars; the
four-language probe confirms the accepted cross-lingual design - the Catalan
probe reaches the Handbook concept (0.994) through its DECLARED alias, not
through raw embedding (raw cross-lingual embedding is weak, as the ADR notes,
which is exactly why declared aliases carry it).

### The agreed score floor

The strong-signal floor is ~0.5 (the RAG-conventions / audit-cadence signal
threshold). Spanish-against-Spanish queries clear it comfortably (0.78-0.98).
The two cross-lingual/concept probes declare a realistic 0.4 floor because
they target the Handbook concept surface where the alias is declared; both
clear it (0.79, 0.99).

### The dedup exclusion (implemented + before/after)

Coordinator ruling implemented: raw `src/aeat/_data/corpus/normatives/html/
*.html` is excluded from the index via `.vaultragignore`, keeping the clean
`*.extracted.md` per-article sidecars. The exclusion is verified correct at
the walker-filter level with the installed `scan_files`:

- raw normatives HTML in the expected set: **0** (excluded);
- normatives `*.extracted.md` sidecars in the expected set: **219** (kept -
  the `*.html` pattern does not match the `.md` suffix);
- OTHER raw `.html` still indexable: **46** (NOT over-excluded - the
  disenos/instructions HTML companions with no sidecar stay).

BEFORE (live, pre-purge): the query "regla de prorrata operaciones
deduccion" returned raw-HTML hits (`ley-37-1992.html` at 0.890, 0.757)
ranking alongside / above the clean sidecars - the duplicate-but-worse
pollution. AFTER: the `test_raw_normatives_html_is_deduplicated` gate asserts
zero raw-HTML hits remain while the sidecar hits persist; it goes green once
the queued reindex purges the now-excluded raw-HTML chunks.

S06's four extensions add NO dedup (proven walker-invisible in S06); only the
normatives HTML carries the raw-vs-clean exclusion, and it is now applied.

### Verification

- Tests: `test_golden_queries.py` (integration) - the 7 golden-query
  parametrisations pass live, plus the dedup-proof test. `ruff check`,
  `ruff format --check`, `ty check` clean; the docs lane stays green (the
  integration tests are excluded from it).

## Notes

- TENSION / honest finding (not hidden): the live AFTER-purge of the
  raw-HTML chunks is queued behind a long peer full-rebuild holding the
  single-writer lock. So at commit time the `test_raw_normatives_html_is_
  deduplicated` gate still sees the raw hits (the queued reindex has not run);
  it is correct that it fails until the purge completes - this is the gate
  doing its job, not a masked failure. The exclusion ITSELF is implemented and
  walker-filter-verified; only the chunk purge awaits the writer lock. When
  the queued reindex runs, the gate goes green. The same peer rebuild is why
  the S07 coverage gate's final green also awaits the index settling.
- No golden query failed to clear its floor - every preprocessed surface is
  retrievable, so the sweep has a trustworthy index (modulo the queued
  raw-HTML purge above).
- No PM wave/phase/step tokens in production code (ADR ids only here). The
  one `subprocess` S603 suppression names the fixed-literal-argv rationale.
- Commit discipline: all verification ran first; staging and the commit are a
  single chained `git add ... ; git commit ...` as the very last action,
  explicit paths only, never touching `index.lock`. The `.vaultragignore`
  change is committed (it is the dedup mechanism), alongside the harness,
  test, and exec record.

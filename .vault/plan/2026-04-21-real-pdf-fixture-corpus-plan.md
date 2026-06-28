---
tags:
  - "#plan"
  - "#real-pdf-fixture-corpus"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-real-pdf-fixture-corpus-adr]]"
  - "[[2026-04-21-real-pdf-fixture-corpus-research]]"
---

# `real-pdf-fixture-corpus` plan

## Goal

Land the three-layer corpus scaffolding — directories, manifests, scrub library, guard hook, synthetic generator primitives, pytest markers — so that clusters D / E / F can start producing tests immediately. Does **not** ship per-modelo generators (those live with their clusters) or pull in user filings (that is a one-shot local recipe the user triggers).

## Phase 1 — Directory layout + pytest markers

### Step 1.1 — Directory skeleton

Create under `tests/fixtures/pdf_corpus/`:

- `l1_public_anchors/` with `_manifest.json` placeholder (empty `entries: []` array).
- `l1_public_anchors/modelo_130/`, `modelo_303/`, `modelo_390/`, `modelo_100/` — empty placeholders with `.gitkeep`.
- `l2_scrubbed_private/` with `_consent_log.jsonl` empty file (append-only ledger).
- `l2_scrubbed_private/modelo_*/` empty placeholders.
- `l3_synthetic/_generators/` with `.gitkeep`; `l3_synthetic/__init__.py`.

### Step 1.2 — pytest markers

Register in `pyproject.toml` under `[tool.pytest.ini_options] markers`:

```
"fixture_tier_l1: test uses committed or fetched public AEAT anchors",
"fixture_tier_l2: test uses scrubbed private anchors from the user archive",
"fixture_tier_l3: test uses on-the-fly synthetic generator output (no fixtures)",
```

Note the existing axis-A / axis-B markers continue unchanged.

### Step 1.3 — Tier-matrix enforcement test

New `tests/test_fixture_tier_markers.py`:

- Walks every test in the project; asserts that any test pulling from `tests/fixtures/pdf_corpus/**` carries exactly one `fixture_tier_*` marker.
- Marker: `pytest.mark.unit`, `pytest.mark.domain_infra`.

## Phase 2 — Scrub library

### Step 2.1 — `src/aeat/adapters/inbound/pdf/_scrub.py`

Prerequisite: cluster A's `src/aeat/adapters/inbound/pdf/` package exists (this plan depends on cluster A executing first; if cluster A hasn't executed yet, it ships alongside this plan on the same PR).

Files:

- `src/aeat/adapters/inbound/pdf/_scrub.py` — implements `ScrubSidecar` pydantic record + `scrub_filing(source_pdf, *, output_dir, rng_seed, consent_revocable_until) -> tuple[Path, ScrubSidecar]`.
- `src/aeat/adapters/inbound/pdf/test_scrub.py` — markers `@pytest.mark.unit`, `@pytest.mark.domain_financial_input`.

### Step 2.2 — Scrub unit tests

Against synthetic justificantes generated in-test:

- Determinism: same input → same output bytes (hash equal across runs).
- NIF redacted: input `12345678A` → output `00000000T`; no residual occurrences of the original NIF anywhere in extracted text.
- Amount redacted: input `1.234,56` → output `X.XXX,XX` with X from the seeded RNG, same digit count.
- CSV redacted: output CSV is deterministic from `(filename, scrub_version)`.
- Guard-pattern sanity: run guard-pattern regexes over the scrubbed text; assert zero hits.
- `ScrubSidecar` round-trip: JSON model-dump → model-validate-JSON is identity.
- Revocation stamp: `consent_revocable_until` honoured; None means permanent.

### Step 2.3 — Guard-pattern pre-commit hook

New `scripts/check_l2_scrub_guard.py`:

- Takes a list of PDF paths from stdin (pre-commit hook convention).
- For each, extracts text with pdfplumber; applies guard regex set.
- Exits non-zero on any hit.

Added to `prek.toml`:

```toml
[[repos.hooks]]
id = "check-l2-scrub-guard"
name = "check L2 scrubbed fixtures contain no residual PII"
entry = "uv run python scripts/check_l2_scrub_guard.py"
language = "system"
files = "^tests/fixtures/pdf_corpus/l2_scrubbed_private/.*\\.pdf$"
```

### Step 2.4 — `just scrub-from-drive` recipe

Added to `justfile`:

```
scrub-from-drive DRIVE_FILE_ID OUT_DIR='tests/fixtures/pdf_corpus/l2_scrubbed_private/{{modelo}}' CONSENT_DAYS='365':
    #!/usr/bin/env bash
    set -euo pipefail
    TMP="$(mktemp -d)"
    trap "rm -rf '$TMP'" EXIT
    uv run aeat drive cat "$DRIVE_FILE_ID" > "$TMP/source.pdf"
    uv run python -m aeat.adapters.inbound.pdf._scrub --input "$TMP/source.pdf" --output-dir "{{OUT_DIR}}" --consent-days "{{CONSENT_DAYS}}"
    echo "Review the scrubbed PDF visually, then git add it + the sidecar"
```

The temp dir is deleted on exit regardless of success.

## Phase 3 — Synthetic generator primitives

### Step 3.1 — `_generator_shared.py`

`tests/fixtures/pdf_corpus/l3_synthetic/_generators/_generator_shared.py`:

- Strict+frozen pydantic `PageLayout`, `CasillaBox`, `LabelAnchor` primitives describing AEAT's layout conventions.
- Reportlab helpers: `draw_header(canvas, modelo, año, page_num, page_count)`, `draw_casilla_box(canvas, box, label_es, value)`, `draw_footer(canvas, csv, tax_id, submitted_at)`.
- Spanish number formatting helper `format_amount(value: Decimal) -> str` producing `1.234,56` or `1.234.567,89`.
- A4 page setup with standard AEAT margins.

### Step 3.2 — Shared `ModeloGenParams` + `GroundTruth`

```python
class ModeloGenParams(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    modelo: str
    año: int
    template_revision: str               # e.g., "303.2024.09"
    tax_id: str
    casilla_values: Mapping[str, Decimal | str]

class GroundTruth(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    params: ModeloGenParams
    extracted_casillas: tuple[ExtractedCasilla, ...]   # uses cluster A type
```

The per-modelo generators (delivered in cluster D) take `ModeloGenParams` and return `(pdf_bytes, GroundTruth)`.

### Step 3.3 — Tests for the shared primitives

`tests/fixtures/pdf_corpus/l3_synthetic/_generators/test_generator_shared.py`:

- Round-trip `PageLayout` / `CasillaBox` pydantic shape.
- `format_amount(Decimal("1234.56")) == "1.234,56"` and analogous cases including negative / zero / very large.
- Helper functions produce non-empty bytes when rendered; text extraction returns the drawn labels.

## Phase 4 — L1 manifest + fetch tooling

### Step 4.1 — `_manifest.json` schema

```json
{
  "schema_version": "1",
  "entries": [
    {
      "id": "modelo_303_boe_orden_hac_819_2024",
      "url": "https://www.boe.es/boe/dias/2024/08/05/pdfs/BOE-A-2024-16129.pdf",
      "sha256": "…",
      "fetched_at": "2026-04-21T00:00:00Z",
      "license": "BOE public-domain per Ley 29/2011",
      "modelo": "303",
      "año": 2024,
      "template_revision": "303.2024.09",
      "purpose": "layout-anchor"
    }
  ]
}
```

### Step 4.2 — `scripts/fetch_l1_anchors.py`

- Reads `_manifest.json`.
- For each entry: if the file is not already cached under `.cache/l1_anchors/<sha256>.pdf`, fetches the URL; verifies SHA-256 against the manifest; caches.
- Exits non-zero on any SHA-256 mismatch (upstream drift detection).
- Gated on `AEAT_FIXTURE_OFFLINE` env var — when set, never attempts fetch; fails loudly if a required file is missing locally.

### Step 4.3 — CI hook

Adds a step to the existing CI workflow that runs `uv run python scripts/fetch_l1_anchors.py` before the test step, populates `.cache/l1_anchors/`, and hard-fails on drift.

## Phase 5 — Coverage-matrix + docs

### Step 5.1 — `docs/coverage/modelos.md`

Add columns `L1 anchors`, `L2 anchors`, `L3 generator` per modelo with ❌ / 🚧 / ✅ / count semantics.

### Step 5.2 — `docs/concepts/pdf-fixture-corpus.md`

- Describes the three-layer model.
- Explains `just scrub-from-drive` for Kent.
- Explicitly addresses "what to do if I notice residual PII in a committed fixture" (commit a revocation entry + `git revert`).

## Phase 6 — Quality gates

- `uv run ruff check src/aeat/adapters/inbound/pdf/ tests/fixtures/pdf_corpus/` — clean.
- `uv run ty check src/aeat/adapters/inbound/pdf/` — clean.
- `uv run pytest -m unit src/aeat/adapters/inbound/pdf/ tests/fixtures/pdf_corpus/` — green.
- Guard-pattern hook executes on a sample scrubbed fixture (generate one in-test against a synthetic; verify guard passes).

## Kent UX roleplay

- **Kent wants to contribute real fixtures**: he runs `aeat oauth-client login`, then `aeat drive find "name contains 'modelo'"`, picks a file ID from the listing, runs `just scrub-from-drive <file-id> CONSENT_DAYS=365`. A scrubbed PDF + sidecar JSON appear under `tests/fixtures/pdf_corpus/l2_scrubbed_private/modelo_N/`. Kent opens the PDF, sees fictional data, commits. If he missed PII the pre-commit hook refuses. If he wants to revoke later, he runs `git revert` on the commit and appends a revocation entry.
- **Kent develops an extractor**: his unit tests parametrise over L3 synthetic input generated fresh each run — zero I/O to fixtures on disk. Passing L3 is necessary but not sufficient.
- **Kent runs the fidelity check**: he invokes `just test-fixture-fidelity MODELO=130` which parametrises over `(año, template_revision)` and asserts the L3 generator output matches the L1 / L2 anchors within tolerance.
- **CI runs**: L1 + L3 always; L2 runs only when L2 fixtures are present on the branch.

## Live-testing posture (honest)

- L3 tests: fully autonomous, no PDFs on disk.
- L1 tests: I can author the manifest + fetch script autonomously; the initial manifest entries will be populated from the web-search findings already on file.
- L2 tests: **requires Kent** — the user — to run `just scrub-from-drive` locally. No agent can do this because (a) no Drive scope in the sandbox, (b) no consent authority to bind scrubbed derivatives to the repo on the user's behalf. The scrub library + hook land autonomously; the fixtures themselves are user-driven.

## Non-goals

- No per-modelo generator (lands in cluster D).
- No extractor code (cluster D).
- No calc-verification wiring (cluster E).
- No automatic real-PDF ingestion from Drive — always manual, always user-gated.
- No change to existing `tests/fixtures/justificantes/_generate.py` — it keeps its current synthetic-receipt responsibility.

---
tags:
  - "#adr"
  - "#real-pdf-fixture-corpus"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-real-pdf-fixture-corpus-research]]"
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
  - "[[2026-04-21-pdf-taxonomy-adr]]"
  - "[[2026-04-21-casilla-schema-completeness-adr]]"
---

# `real-pdf-fixture-corpus` adr: `three-layer-corpus-public-anchors-scrubbed-privates-synthetic-parametrised` | (**status:** `accepted`)

## Problem Statement

Extractor work (cluster D), calc-verification (cluster E), and Modelo 100 (cluster F) all depend on having a test corpus that meets three mutually conflicting demands: **scale** (hundreds of parametrised cases), **authority** (matches AEAT's real rendering), **PII-safety** (no leakage of anyone's real tax data). No single sourcing path satisfies all three. This ADR locks a three-layer strategy — public anchors + scrubbed private anchors + synthetic parametrised — plus the scrubbing pipeline, the commit policy, and the fidelity-validation rule that ties the layers together.

## Considerations

- AEAT publishes enough **public material** (Manuales prácticos, BOE orders, Renta Web Open simulator output, Diseño de Registro specs) to establish layout ground truth and a small set of filled-case reference samples — **but not enough for parametrised scale**.
- Kent has his own **private archive** of real filings (likely in Google Drive, named "MODELO *"). Those are authoritative but PII-laden — usable only as scrubbed derivatives, and only with explicit consent recorded per-file.
- A **synthetic PDF generator** mirroring AEAT's rendering can supply unlimited parametrised scale, but only if its fidelity is validated against real anchors; an unvalidated generator is worse than no generator because it produces false confidence.
- The project's `aeat drive` CLI (`src/aeat/entrypoints/cli/drive.py`) + `aeat.adapters.outbound.aeat.auth` Google OAuth plumbing already exist. A separate scrubbing library belongs under the new `src/aeat/adapters/inbound/pdf/` package cluster A defines.
- The `Engine.audit_against` primitive (`src/aeat/domain/formulas/_engine.py:51`) expects a known-good `(casilla_id, value)` mapping. The synthetic generator's ground truth *is* that mapping — the two primitives pair cleanly.
- CI cannot pull user-private data; CI runs L1 + L3 only. L2 (scrubbed privates) runs locally + in the owning contributor's branch builds.
- Project mandate: Pydantic v2 strict+frozen for every boundary record; no bare dicts; relative imports; `AeatError`-rooted exceptions.

## Constraints

- **No raw real PDFs** ever enter the repo. Even scrubbed derivatives commit only after explicit consent + scrub-policy validation.
- **No PII in conversation logs** — the probe-don't-download rule: listings are safe; downloads of real filings route to a scrub script, not into any Claude / agent context window.
- **Deterministic scrubbing** — same input file name → same scrubbed bytes; re-running scrub on a committed derivative is a no-op.
- **Hash-pinning** for L1 public anchors so drift is detectable without committing megabytes.
- **License respect** — L1 commits either (a) hash-pin + fetch-at-test-time with an audit log, or (b) excerpt (≤1 page) under fair-use for education.
- **No test skips** introduced; layered markers instead (`fixture_tier_l1 / l2 / l3`).
- **Revocation** — each L2 derivative carries a sidecar consent record; revocation removes the file via `git revert` and appends a revocation log.

## Implementation

### 1. Three-layer corpus

Directory layout under `tests/fixtures/`:

```
tests/fixtures/
├── justificantes/                 # existing — synthetic receipts (layer L3 for justificantes)
├── pdf_corpus/
│   ├── l1_public_anchors/
│   │   ├── _manifest.json         # URL + SHA-256 + fetch date + license note per entry
│   │   ├── modelo_130/
│   │   │   ├── boe_orden_ha_xxx_pinhash.txt   # hash-pin; fetched at test time
│   │   │   └── manual_practico_excerpt_130_2025.pdf  # <=1 page, fair-use excerpt
│   │   ├── modelo_303/
│   │   └── …
│   ├── l2_scrubbed_private/
│   │   ├── _consent_log.jsonl     # append-only consent + revocation records
│   │   ├── modelo_130/
│   │   │   ├── 2024Q1_a1b2c3_scrubbed.pdf
│   │   │   └── 2024Q1_a1b2c3_scrubbed.json     # sidecar: (original_sha256, scrubbed_sha256, scrub_version, scrubbed_at, fields_touched, consent_revocable_until)
│   │   └── …
│   └── l3_synthetic/              # source-only; PDFs generated at test time
│       ├── _generators/
│       │   ├── modelo_130_generator.py
│       │   ├── modelo_303_generator.py
│       │   └── …
│       └── _generator_shared.py   # reportlab layout primitives (AEAT-mimicking)
```

### 2. New `src/aeat/adapters/inbound/pdf/_scrub.py` library

Lives in the package cluster A opens. Public API:

```python
class ScrubSidecar(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    original_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scrubbed_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scrub_version: str                         # semver; bump when scrub rules change
    scrubbed_at: datetime                      # UTC
    fields_touched: tuple[str, ...]            # nif | amounts | names | csv | dates | …
    consent_revocable_until: datetime | None   # None = permanent; else a future date
    fixture_tier: Literal["l2"]


def scrub_filing(
    source_pdf: Path,
    *,
    output_dir: Path,
    rng_seed: str | None = None,
    consent_revocable_until: datetime | None = None,
) -> tuple[Path, ScrubSidecar]:
    """Deterministic PII scrubber for AEAT filings."""
```

Behaviour:

- NIF → `00000000T` (individual) / `B00000000` (empresa).
- Monetary amounts → synthetic amounts from `random.Random(seed_from_filename)` preserving digit count and currency formatting.
- Names → `DEMO AUTÓNOMO` / `DEMO EMPRESA`.
- CSV → 16-char upper-alphanum hash of `(filename, scrub_version)`.
- Dates → preserved by default (dates are not PII); fields whose names contain `ID` or `número` get replaced with seeded synthetic IDs.
- Addresses, phone numbers, emails, IBANs → `REDACTED` uppercase placeholder of matching character length.

Implementation uses pypdf or pikepdf for byte-level writes, not re-rendering, so the layout is preserved for extractor testing.

### 3. Guard-pattern pre-commit hook

`scripts/check_l2_scrub_guard.py` (new) runs on every staged `tests/fixtures/pdf_corpus/l2_scrubbed_private/**/*.pdf`:

- Extracts text via pdfplumber.
- Runs a hard-coded set of regex "guard patterns": Spanish NIF regex (`\b[0-9]{8}[A-Z]\b` excluding the fictional `00000000T`), IBAN regex, email regex, Spanish phone regex, 4-digit-year + full-name heuristic.
- Any match on any guard pattern fails the commit.

Added to `prek.toml` as a repo-local hook gated on file-path match.

### 4. Synthetic generator module family

Under `tests/fixtures/pdf_corpus/l3_synthetic/_generators/`:

- `_generator_shared.py` — reportlab primitives that reproduce AEAT's layout conventions: A4 margins, font families (Helvetica as Arial stand-in; switch to embedded TTF Arial if redistribution-compatible), label placement grid, Spanish number formatting (`1.234,56`), boxed casilla rendering.
- `modelo_N_generator.py` per modelo — `generate(modelo_N_params: ModeloNGenParams) -> tuple[bytes, GroundTruthMap]`.
- `ModeloNGenParams` is a strict+frozen pydantic record covering: `año`, `template_revision`, `tax_id`, `casilla_values: Mapping[str, Decimal | str]`, plus modelo-specific extras (e.g., régimen for 130).
- `GroundTruthMap = tuple[ExtractedCasilla, ...]` — identical shape to cluster D's extractor output so tests compare apples to apples.

### 5. Fidelity-validation rule

For every `(modelo, año, template_revision)` tuple the generator supports:

- **At least 3 real anchors** must exist across L1 + L2 to count the generator as "fidelity-verified."
- A `test_generator_matches_anchors[modelo, año, template_revision]` test (parametrised) asserts that generating a PDF for the same inputs produces a byte-region-equivalent output to the anchor (tolerance on font-hinting / PDF serialisation differences; tolerance ≥ 98 % per-page text-bbox agreement).
- When < 3 anchors exist, the test is `pytest.mark.xfail(strict=True, reason="fidelity-unverified — fewer than 3 anchors")`. The `strict=True` flips it to a hard fail the moment anchors land.

### 6. CI tier policy

- `fixture_tier_l1` marker: runs in CI; requires network access OR pre-downloaded hash-pinned files (controlled by `AEAT_FIXTURE_OFFLINE=1`).
- `fixture_tier_l2` marker: runs locally + in branch CI if the branch includes L2 fixtures; CI step checks the consent log is current.
- `fixture_tier_l3` marker: runs everywhere; no network, no fixtures, just the generator.
- The markers compose with the existing axis A (`unit` / `live_read` / `live_write`) and axis B (`domain_*`). Sample: `@pytest.mark.unit`, `@pytest.mark.domain_financial_input`, `@pytest.mark.fixture_tier_l3`.

### 7. Drive-sourced path workflow (one-shot, local)

The flow for bringing Kent's real filings into L2:

1. Kent runs `aeat oauth-client login --scope drive` (existing).
2. Kent runs `aeat drive find "name contains 'modelo'"` — lists filenames.
3. Kent runs (new `just` recipe): `just scrub-from-drive DRIVE_FILE_ID CONSENT_DAYS=365` — downloads the file to a temp dir, runs `scrub_filing`, writes the scrubbed PDF + sidecar under `tests/fixtures/pdf_corpus/l2_scrubbed_private/modelo_N/`, and deletes the temp file.
4. Kent reviews the scrubbed output manually (open PDF, confirm no residual PII), commits with an explicit consent message in the PR.
5. The commit triggers the guard-pattern pre-commit hook (step 3); any residual PII fails the commit.

No agent / CI process ever holds the pre-scrub bytes.

### 8. Coverage-matrix updates

`docs/coverage/modelos.md` gains three columns:

| Modelo | … | L1 anchors | L2 anchors | L3 generator |
| --- | --- | --- | --- | --- |

With counts per `(modelo, año, template_revision)`. Ties to cluster B's schema-complete axis: a modelo is "extraction-ready" when `L3 ≥ fidelity-verified` AND `L1 + L2 ≥ 3 anchors` AND `corpus complete`.

### 9. Explicitly out of scope

- No extractor code (cluster D).
- No calc-verification wiring (cluster E).
- No Renta Web Open integration — it's a URL we may hit manually to generate L1 anchors but not an automated test surface.
- No scrubbing of anything **outside** AEAT filing PDFs (e.g., banking statements, invoices) — narrower scope than a general-purpose PII redactor.
- No replacement of dates — dates are not PII per GDPR Art. 4; only timestamped IDs get replaced.

## Consequences

- **The sourcing question stops being a blocker.** Clusters D/E/F start against L3 generators on day one; L1 anchors land autonomously from public sources; L2 scrubbed privates land when the user opts in and runs the scrub recipe.
- **Zero PII leakage into agent contexts / CI / git history.** The scrub library + guard pattern + consent log form a defence-in-depth stack.
- **Fidelity is observable.** Every generator's real-world fidelity is measured by an anchor test; drift trips the build.
- **Parametrised calc-verification works.** Tests can sweep `@pytest.mark.parametrize` across the casilla input space; `Engine.audit_against` checks every case.
- **User consent is first-class.** Nothing enters the repo without a sidecar record; revocation is supported; every scrubbed file carries its own audit trail.
- **Synthetic generator doubles as a product surface** — once built, Kent could generate a mock justificante / declaración for training / demo purposes. Not scope now, but a latent win.
- **A new `src/aeat/adapters/inbound/pdf/_scrub.py` library** lands; consumable by CLI surfaces, CI jobs, and future product features beyond fixtures.

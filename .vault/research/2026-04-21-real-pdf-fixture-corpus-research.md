---
tags:
  - "#research"
  - "#real-pdf-fixture-corpus"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
  - "[[2026-04-21-pdf-taxonomy-adr]]"
  - "[[2026-04-21-casilla-schema-completeness-adr]]"
---

# real-pdf-fixture-corpus research

## Problem

PDF-extraction work (clusters D / F) and calc-verification (cluster E) are useless without a test corpus that the extractor can be measured against. Three constraints make this non-trivial:

1. **PII**: real filings are legally-protected personal tax data.
2. **Authority**: synthetic fixtures we invent ourselves might not mirror AEAT's real rendering, so an extractor that passes against them may fail against real PDFs.
3. **Scale**: calc-verification wants the full `(modelo, año, régimen, casilla permutation)` matrix, not a handful of hand-picked samples.

The research below inventories every sourcing path we can actually use and recommends a **three-layer corpus strategy** (synthetic generator + publicly-available anchors + scrubbed-private anchors) that gives us scale without PII leakage and layout authority without legal risk.

## Available sourcing paths

### Path 1 — Publicly-fetchable AEAT materials

Surveyed via web search; every URL below was verified fetchable at research time. All are public-domain or AEAT-informational with explicit reuse-for-education language.

- **AEAT Manual práctico PDFs** — per-year, per-tax monolithic PDFs at `sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/`. Examples:
    - `IRPF/IRPF-2024/ManualRenta2024Tomo1_es_es.pdf` (2.5 MB class)
    - `IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf`
    - `IVA/Manual_IVA_2024.pdf`
    - `IVA/IVA_2024/Imagenes/Cap_9_303_es_es.pdf` (Modelo 303 chapter offprint)
    - `IVA/IVA_2024/Imagenes/Cap_7_303_4T_es_es.pdf` (Modelo 303 Q4 chapter)
- **BOE orders** — PDFs of each *Orden HAC/EHA* approving a modelo. Contains the full form rendering as annex. Examples:
    - `BOE-A-2024-16129.pdf` (Orden HAC/819/2024 — Modelo 303 post-2024-09 amendments)
    - `BOE-A-2007-6032` (Orden EHA/672/2007 — Modelo 130 base order)
- **Renta Web Open** at `sede.agenciatributaria.gob.es/.../renta-web-open.html` — anonymous Modelo 100 simulator. No cert, no NIF validation. Outputs a watermarked *vista previa* PDF. Best pathway for filled-example Renta PDFs.
- **Diseño de Registro specs** — flat-file record layouts, e.g. `Disenyo_registro/ant_100_199/archivos/dr130.09.pdf`. Not a filing PDF but an authoritative per-casilla type / width / ordering reference.

**Evidence of parsability**: every PDF fetched is static (no XFA overlay), pdfplumber-parseable for text regions; BOE annex form images would need OCR only for layout inspection, not for text. Licensing: BOE is public-domain; AEAT manuals carry "carácter informativo y no vinculante" — reusable for tests.

**What they're useful for**:

- Layout ground truth (font sizes, label placements, box positions).
- Chapter-embedded *casos prácticos* give realistic input → output numeric pairs.
- Manual chapter text provides authoritative field semantics for extractor heuristics.

**What they can't do**: scale. There are maybe 20–30 filled-case studies across all manuals, not the hundreds we need for parametrised testing.

### Path 2 — User's private archive (Kent's own filings)

The project ships a `aeat drive` CLI (`src/aeat/entrypoints/cli/drive.py`) with `ls`, `find`, `fetch` backed by the existing `aeat.adapters.outbound.aeat.auth` Google OAuth plumbing. A probe against the primary working directory's current auth state returned `403 insufficientPermissions` — fallback to ADC without the Drive scope. The authenticated-OAuth path would work once the user runs `aeat oauth-client` with Drive scope, but:

- **This is the user's property.** We do not pull real filings into my context or the repo.
- **Names only, never contents.** A listing (`aeat drive find "name contains 'modelo'"`) yields filenames and IDs; that alone is high-value intelligence (which modelos and años the user has filed) without leaking tax data.
- **Scrubbing is mandatory before anything crosses into the repo.** Any derivative the extractor tests reference must be PII-scrubbed and annotated so the provenance is clear.

**Recommended use**: the user's archive is the **anchor corpus** — a dozen or two scrubbed real filings that validate the synthetic generator's layout fidelity. No raw bytes are committed; only scrubbed derivatives with deterministic redaction.

### Path 3 — Synthetic generator mirroring AEAT's rendering

This is the force-multiplier. A Python module (`tests/fixtures/justificantes/_generate.py` already exists; the new generator sits alongside it) that:

1. Takes a `(modelo, año, tax_id, casilla_values: dict[str, Decimal])` input.
2. Renders a PDF using reportlab with **AEAT-mimicking layout**: same A4 sizing, same fonts (Helvetica as a Type1 stand-in for Arial — AEAT's embedded font), same label anchors, same bbox widths for numeric values, same Spanish-thousands formatting `1.234,56`.
3. Outputs `(pdf_bytes, ground_truth_casilla_map)` so the extractor test can assert `extract(pdf_bytes) == ground_truth_casilla_map`.

The generator is the ground truth; the extractor's job is to re-derive the ground truth from the pixels/text stream it produces. This gives us:

- **Scale**: one `@pytest.mark.parametrize` decorator can sweep 10 000 synthetic cases per modelo.
- **Zero PII**: every input is fictional (all-zeros NIF, synthesised names, CSV `ABCD...`).
- **Calc-verification end-to-end**: after extraction, the test runs `Engine.audit_against(ruleset, extracted_values)` — every computed casilla is re-derived from the literals; any discrepancy > rounding tolerance is a real correctness bug.
- **Template-drift armour**: when AEAT changes a form template year-over-year, the generator grows a `template_revision` knob; the extractor's bounding-box maps grow matching versions; fixture generation + extraction test both update in lock-step.

**Fidelity check**: the synthetic generator is only as good as its correspondence to reality. The anchor validation rule: every synthetic template revision MUST pass layout-equivalence assertions against a small set of scrubbed real samples (path 2) or publicly-available samples (path 1). If the synthetic extractor succeeds but the real extractor fails, we catch it at the anchor layer.

## Three-layer corpus proposal

| Layer | What it contains | Scale | Licensing | PII | Commits |
| --- | --- | --- | --- | --- | --- |
| **L1 — Public anchors** | Scrubbed excerpts or hash-pins of BOE / Manual / Renta-Web-Open PDFs | ~10–20 per modelo | AEAT informational / BOE public-domain | None | Yes (bytes) |
| **L2 — Scrubbed private anchors** | Deterministically-redacted derivatives of user's real filings | ~5–10 per modelo | User-consented | Redacted | Yes (scrubbed bytes only) |
| **L3 — Synthetic parametrised** | Generated at test time from the synthetic generator | ∞ (parametrised) | Project-authored | None | Generator source; no bytes |

Extractor tests run in three tiers: L3 unit tests (deterministic, offline, unlimited), L1 integration tests (real fetch or committed hash-pinned bytes), L2 regression tests (scrubbed real filings on disk, `@pytest.mark.domain_financial_input`).

## PII scrubbing pipeline (cluster-C scope to define; not to implement here)

For path 2 → L2 derivatives, the scrubbing pipeline must be deterministic, reversible-on-input-hash-only, and auditable. Proposal outline:

- NIF redaction: replace Kent's real NIF with a fictional one (`00000000T` for individual, `B00000000` for empresa) consistently across the file.
- Amount redaction: replace all monetary values with semantically plausible synthetic amounts generated from a seeded RNG per-filing.
- Name redaction: replace any name occurrence with `DEMO AUTÓNOMO` / `DEMO EMPRESA`.
- CSV redaction: replace the CSV with a synthetic 16-char alphanumeric string derived from a hash of the file name (stable so re-scrub is idempotent).
- Date redaction: decided per-field — most dates stay (dates aren't PII); only timestamped IDs get replaced.
- Registry: every scrubbed derivative carries a sidecar JSON recording `(original_sha256, scrubbed_sha256, scrub_version, scrubbed_at, fields_touched)` for auditability — the original never touches the repo.

## Cross-cluster implications

- **Cluster D (extractor)** — runs its tests against all three layers; every test case is tagged with the layer it belongs to so quality can be tracked per-layer.
- **Cluster E (verification)** — uses L3's ground-truth maps to compute the "extraction accuracy" metric per modelo per template revision.
- **Cluster F (Modelo 100 / RENTA)** — the synthetic generator's complexity explodes for 100. Proposal: cluster F builds a per-anexo generator mini-module; L3 for Renta parametrises only a curated handful of "typical" cases; L1/L2 fills the rest.
- **Cluster H (CI)** — CI runs L1 + L3; L2 runs only locally unless / until a `live_read`-analogous marker for "scrubbed real fixtures" is introduced (proposed: `domain_financial_input` + a new `fixture_tier` marker).

## Open questions (for the ADR)

1. **L1 commit policy** — do we commit raw BOE / Manual PDFs (bytes + SHA-256) or only their URLs + hash-pins that we fetch at test time? Recommendation: **hash-pin + fetch**. Avoid bloating the repo with hundreds of megabytes of PDFs; keep a redistribution-permission audit trail; allow `AEAT_FIXTURE_OFFLINE=1` env var for CI without network.
2. **L2 scrub tooling location** — `scripts/scrub_filing.py` (one-shot) vs. `src/aeat/adapters/inbound/pdf/_scrub.py` (library + CLI)? Recommendation: **library** under the new `_pdf_import` package so clusters D / E can call it directly.
3. **Deterministic scrubbing** — seeded RNG per-file, stable across re-runs? Recommendation: **yes**; the seed is the SHA-256 of the original file name (not contents) so re-scrubbing the same file twice produces byte-identical output, but the seed is not recoverable from the scrubbed output.
4. **User consent flow** — how does Kent authorise committing his scrubbed derivatives? Recommendation: a `just scrub-filing` recipe with a `--accept-commit-policy` flag that records consent in the sidecar JSON.
5. **Synthetic fidelity** — how many real anchors per modelo do we need to trust the generator? Recommendation: **≥3 real samples per `(modelo, año, template_revision)` tuple**; if fewer are available, the generator for that tuple is flagged "fidelity-unverified" and its tests run with a `xfail(strict=True)` that flips to xpass once anchors land.
6. **Template-revision schema** — how do we key fixtures? Recommendation: `(modelo, año, template_revision)` where `template_revision` is a semver-like string the BOE order assigns (e.g., `303.2024.09`).
7. **Cleanup policy** — what happens when a user revokes consent? Recommendation: each L2 scrubbed artifact has a `consent_revocable_until` stamp; after expiry it's locked; before expiry `git revert` removes the artifact and the sidecar is appended to a revocation log.

## Risk register

- **Synthetic drift from reality** — generator matches today's AEAT but AEAT changes next year. Mitigation: anchor validation every release; automated CI check that fetches current BOE PDFs and compares layout fingerprints.
- **Scrub leakage** — a PII field missed by the scrubber surfaces in a committed fixture. Mitigation: a hard-coded "guard pattern" regex set (NIF regex, IBAN regex, name-like capital-word-pair regex) that must return zero matches on any scrubbed output before it can be committed; enforced by pre-commit hook.
- **License drift** — AEAT changes terms of use on Manuales prácticos. Mitigation: the hash-pin commit records the fetch date; a follow-up check can confirm the current version still has compatible terms.
- **Over-reliance on synthetic** — all tests pass against L3 but the extractor fails on real PDFs. Mitigation: CI requires at least one passing L1 test per modelo before the `aeat filing import --from-declaracion <modelo>` support flag is registered.

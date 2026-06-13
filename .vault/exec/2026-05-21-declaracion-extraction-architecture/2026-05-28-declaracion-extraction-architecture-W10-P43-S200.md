---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S200'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
  - "[[2026-05-28-borrador-extraction-architecture-research]]"
---

# `declaracion-extraction-architecture` W10.P43.S200 — borrador architectural audit

## Step

Audit `src/aeat/adapters/inbound/borrador/` for architectural pattern — per-modelo
extractor class vs registry-profile-driven extraction. Make ADR-level decision.

## Execution

### UNIT 1 — Borrador module anatomy

**Entry-point:** `parse_borrador(pdf_path, *, artefact_kind_override, año_override,
extraction_profile, parse_mode)` in `_parser.py`.

**Extraction model — per-año class dispatch.** `_parser.py` calls `get_extractor(año)`
from `_extractors/__init__.py`, which resolves `_REGISTRY_BY_AÑO: dict[int, type]`
mapping year integers to concrete extractor classes. The sole registered class is
`Modelo100ObservedV2025Extractor` (año 2025) in
`_extractors/modelo_100_summary_v2025.py`.

**No ABC.** `Modelo100ObservedV2025Extractor` is a plain class with
`año: ClassVar[int] = 2025`. No ABC, no `(modelo, año, revision)` tuple key,
no `DeclaracionExtractor`-style base. The `_REGISTRY_BY_AÑO` dict is a simple
year→class dispatch for future layout versioning.

**`BorradorExtractionProfile` Protocol.** Defined in `_schema.py` as a structural
Protocol. It is an _optional caller-supplied_ argument — not looked up from
`RegistrySnapshot.extraction_profiles`. When supplied, the extractor filters to
`target_casillas` and validates coverage.

**Exception hierarchy.** `BorradorParseError` → `PdfModeloImportError`. No
`missing/malformed/ambiguous/coverage` structured attributes — this gap mirrors
the justificante gap closed in `W10.P41.S198`.

### UNIT 2 — Registry cross-check

- W02 ADR scope: `declaracion_pdf` surface only; borrador not mentioned.
- Registry TOML: zero `borrador_pdf` extraction profile fragments in the data tree.
  Three M100 profiles exist for 2021–2023 with `surface = "declaracion_pdf"` only.
- Schema: `ExtractionProfileDefinition.surface` enumerates `"borrador_pdf"` — the
  type system supports it; no instances have been authored.
- `RegistrySnapshot.extraction_profiles` has no borrador entries at runtime.

### UNIT 3 — Verdict

**Outcome: (b) — architectural divergence from post-W02 declaracion; exception
formally accepted with ADR amendment.**

Three concrete divergences from `parse_declaracion`:
1. No `RegistrySnapshot` consultation at parse time.
2. Per-año class dispatch instead of stateless `_find_casilla_hits`.
3. No `borrador_pdf` TOML profiles exist.

The divergence is justified: the borrador extractor's purpose is observed-value
extraction of all printed casilla rows, not registry-defined target filtering.
Per-año dispatch is appropriate for Renta PDF layout versioning.

### UNIT 4 — Documentation authored

- Research document: `.vault/research/2026-05-28-borrador-extraction-architecture-research.md`
- ADR amendment added to `.vault/adr/2026-05-21-declaracion-extraction-architecture-adr.md`
  (section "2026-05-28 amendment — borrador surface architectural exception") formally
  accepting the per-año class dispatch and `BorradorExtractionProfile` Protocol as the
  canonical borrador extraction model. Follow-up obligation: add
  `missing/malformed/ambiguous/coverage` structured attributes to `BorradorParseError`.

### UNIT 5 — Tests

`uv run --no-sync pytest src/aeat/adapters/inbound/borrador/ -q --tb=line`:
11 passed, no regressions. Audit was read-only; no code changes.

## Honest verdict

The borrador surface is architecturally aligned with the post-April codebase
direction (no ABC, no `(modelo, año, revision)` registry) but diverges from the
post-W02 declaracion surface in that it does not consult `RegistrySnapshot` at
parse time. The divergence is justified by the surface's purpose and accepted
via ADR amendment. The open discipline debt is structured exception attributes on
`BorradorParseError` — a follow-up task, not a blocker.

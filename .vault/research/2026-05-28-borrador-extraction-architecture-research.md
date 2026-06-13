---
tags:
  - '#research'
  - '#declaracion-extraction-architecture'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
  - "[[2026-04-21-declaracion-extractor-adr]]"
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
---

# `declaracion-extraction-architecture` research: `borrador-surface-architectural-audit`

Audit of `src/aeat/adapters/inbound/borrador/` to determine whether the
borrador parser uses the registry-profile-driven extraction that W02
(`2026-05-21-declaracion-extraction-architecture-adr`) established for
the declaración surface, or a different extraction pattern.

## Findings

### UNIT 1 — Borrador module anatomy

**Entry-point signature.**
`parse_borrador(pdf_path, *, artefact_kind_override, año_override,
extraction_profile, parse_mode)` in `src/aeat/adapters/inbound/borrador/_parser.py`.

**Extraction model — per-año class dispatch.**
`_parser.py` calls `get_extractor(año)` from `src/aeat/adapters/inbound/borrador/_extractors/__init__.py`,
which looks up a concrete extractor class from `_REGISTRY_BY_AÑO: dict[int, type]`:

```
_REGISTRY_BY_AÑO = {
    2025: Modelo100ObservedV2025Extractor,
}
```

The concrete class `Modelo100ObservedV2025Extractor` in
`src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py`
implements `extract(pdf_path, artefact_kind, extraction_profile)` returning
a `BorradorObservation`.

This is a **per-año class keyed by tax year integer**, NOT a registry-profile
lookup on `RegistrySnapshot.extraction_profiles`.

**Does the extractor extend an ABC?** No. `Modelo100ObservedV2025Extractor` is a
plain class with `año: ClassVar[int] = 2025`. There is no ABC, no
`DeclaracionExtractor`-style base class, no `(modelo, año, revision)` tuple key.
The per-año registry is a simple `dict[int, type]` — structurally lighter than
the superseded `2026-04-21` pattern.

**Role of `BorradorExtractionProfile`.**
`_schema.py` defines `BorradorExtractionProfile` as a structural `Protocol`
(duck-typed interface). The extractor accepts it as an _optional caller-supplied_
argument. When provided, the extractor filters observed casillas to the profile's
`target_casillas` and validates coverage against `min_coverage`. The profile is
**not** looked up from a `RegistrySnapshot` inside the adapter — the caller
supplies it. The `parse_borrador` entry point uses `BorradorParseMode.REGISTRY_PROFILE`
to signal that the caller intends profile-mode extraction, but the profile object
itself arrives as a parameter, not from registry consultation.

**`_extractors/` summary.** One file, one class, no ABC, no inheritance chain.
The "extractor registry" is a year→class mapping, used to future-proof year-revision
transitions (2026, 2027, etc.) without a branch in the main parser.

**Exception hierarchy.** `BorradorParseError` in `_errors.py` subclasses
`PdfModeloImportError` (from `adapters.inbound.pdf._errors`), which is a
domain-specialised error. It does NOT yet carry the `missing/malformed/ambiguous/coverage`
structured attributes that `DeclaracionParseError` carries — the same gap that
was closed for `JustificanteParseError` in `W10.P41.S198`.

**`_parsers/` directory.** Thin backend isolation — `extract_pages_text` delegates
to the shared `adapters.inbound.pdf._pdfplumber` helper. Pattern is identical to
the declaracion and justificante surfaces.

### UNIT 2 — Cross-check against W02 ADR and registry

**W02 ADR scope.** The `2026-05-21-declaracion-extraction-architecture-adr`
scopes exclusively to `declaracion_pdf` extraction profiles and the
`parse_declaracion` surface. The word "borrador" does not appear in the ADR body.
The W02 ADR superseded the `2026-04-21-declaracion-extractor-adr` which itself
also scoped to declaración PDFs. Borrador was not in scope for either ADR.

**Registry TOML.** There are no `borrador_pdf` extraction profile TOML fragments
anywhere under `src/aeat/_data/registry/`. The three M100 extraction profile files
that exist cover revisions 2021–2023 and carry `surface = "declaracion_pdf"`.
Revision 2025 has no extraction_profiles fragment at all. No `surface = "borrador_pdf"`
entry exists in the registry data tree.

**Schema support.** `ExtractionProfileDefinition.surface` in
`src/aeat/domain/calculations/registry/_schema.py` does enumerate `"borrador_pdf"`
as a valid surface literal — so the registry schema can represent borrador
extraction profiles. None have been authored.

**Registry snapshot exposure.** `RegistrySnapshot.extraction_profiles` is typed
as `Mapping[ExtractionProfileId, ExtractionProfileDefinition]` and is populated
from TOML. Since no `borrador_pdf` profiles exist in TOML, no borrador profiles
appear in the snapshot at runtime. The borrador extractor never consults the
snapshot — it uses the caller-supplied Protocol duck-type.

### UNIT 3 — Architectural verdict

**Verdict: (b) — architectural divergence from post-W02 declaracion, with
recommendation to document the exception.**

The borrador surface diverges from `parse_declaracion` in three concrete ways:

1. `parse_declaracion` looks up an `ExtractionProfileDefinition` from
   `RegistrySnapshot.extraction_profiles` by `surface = "declaracion_pdf"` at
   parse time. `parse_borrador` does not consult the registry snapshot; a profile
   is optionally supplied by the caller.

2. `parse_declaracion` has no extractor class whatsoever — it calls
   `_find_casilla_hits` directly. `parse_borrador` delegates to a per-año
   concrete class from `_REGISTRY_BY_AÑO`.

3. No `borrador_pdf` extraction profiles exist in the registry TOML tree.

**Is the divergence justified?**
Partially yes. The borrador surface has a genuinely different purpose:
it extracts _all observable casilla/value rows_ printed on the PDF as an
observed-value record, not a registry-defined subset for a specific use-case.
The per-año class approach provides a clean migration path for year-on-year
layout changes in Renta PDFs — a justifiable engineering choice given that
Renta Web Open layout can change each año independently of registry revision
logic. The `BorradorExtractionProfile` Protocol as an optional caller-supplied
filter is also well-motivated: callers (CLI, application layer) can pass a
registry profile to constrain what the parser returns without making the
adapter itself registry-aware.

**Is the divergence undocumented?**
Yes. No ADR documents why borrador uses per-año class dispatch rather than
registry-profile-driven extraction, nor why no `borrador_pdf` profiles exist in
the TOML tree. The W02 ADR simply never addressed the surface.

**Gap not yet closed — `DeclaracionParseError` structured attributes.**
`BorradorParseError` does not yet carry `missing/malformed/ambiguous/coverage`
structured attributes. This gap mirrors the justificante gap that `W10.P41.S198`
closed for `JustificanteParseError`. It is a parallel discipline debt.

## Recommended ADR direction

Two options:

**Option A — Document the architectural exception (preferred).**
Author an ADR amendment to `2026-05-21-declaracion-extraction-architecture-adr`
documenting the borrador surface as a formally-accepted architectural variant:

- Per-año class dispatch for Renta PDF layout versioning is accepted as the
  borrador extraction model.
- `BorradorExtractionProfile` as an optional caller-supplied Protocol is accepted
  as the borrador/registry integration boundary.
- No `borrador_pdf` TOML profiles are required; the Protocol is the integration
  contract.
- `BorradorParseError` gains `missing/malformed/ambiguous/coverage` structured
  attributes, aligned with `DeclaracionParseError` and `JustificanteParseError`.

**Option B — Migrate borrador to registry-profile-driven extraction.**
Author `borrador_pdf` TOML profiles, make `parse_borrador` look them up from the
snapshot, and retire the per-año class registry. This aligns the surface with
declaracion structurally but loses the clean per-año layout-versioning capability.
Higher migration cost, lower architectural gain given the surface's purpose.

Option A is preferred. The borrador surface is architecturally coherent as-is;
the only debt is the undocumented exception and the missing structured exception
attributes.

## Scope of follow-up work

- ADR amendment to the W02 ADR formally accepting the borrador architectural
  exception (document `_REGISTRY_BY_AÑO` per-año dispatch as the accepted
  borrador pattern; document `BorradorExtractionProfile` Protocol as the
  registry-borrador integration boundary).
- `BorradorParseError` structured attribute parity with `DeclaracionParseError`
  (add `missing`, `malformed`, `ambiguous`, `coverage`; update error-raising
  sites and tests).
- These are independent tasks; neither requires migrating the extractor classes.

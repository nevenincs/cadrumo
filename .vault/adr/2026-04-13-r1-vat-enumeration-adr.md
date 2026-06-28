---
name: r1-vat-enumeration-adr
description: Architecture decision record for the Track B R-1 VAT enumeration substrate.
type: adr
tags:
  - "#adr"
  - "#r1-vat-enumeration"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-r1-vat-enumeration-research]]"
  - "[[2026-04-13-r1-vat-enumeration-plan]]"
---

# r1-vat-enumeration adr

> **PARTIALLY-SUPERSEDED 2026-05-19**: The Value-Added Tax direction in this ADR is reversed: Spanish stems are authoritative for tax-domain identifiers, IvaInvoiceClassification is canonical, and domain/vat migrates into domain/iva. The 27-state rate table, 16-member category enumeration, citation-backed catalogue shape, and Pydantic-strict substrate decisions remain in force; only the VAT-prefixed identifiers and the domain/financial/vat package path are reversed.
> See `2026-05-19-spanish-stem-terminology-authority-adr` for the canonical
> rename ledger and Spanish-stem terminology authority.


## status

Accepted — 2026-04-13.

## context

Track B (Transaction Data Pipeline, umbrella EPIC #104) needs a
strictly-typed, hand-reviewed enumeration of Spanish VAT situations
and a minimal EU rate table before downstream categorisation and
provider-tagging layers can run. The substrate has to be importable
by peer subpackages (financial/providers, financial/categories)
without creating cycles, and must fit the project's pydantic-first,
trilingual, citation-backed corpus-as-code pattern already used by
`aeat.domain.normatives` and `aeat.domain.manuals`.

## decision

Introduce `src/aeat/domain/financial/vat/` as a new subpackage that exposes:

- `VATCategory: StrEnum` — 16-member closed catalogue of the VAT
  situations the TDP classifier distinguishes (domestic rates,
  exemptions, non-subject, intra-community supply / acquisition /
  triangulation, export, import, recargo de equivalencia, régimen
  simplificado, erroneous invoice, unknown).
- `EUMemberState: StrEnum` — all 27 current EU member states, ISO
  3166-1 alpha-2 lowercase values.
- `VATRateKind: StrEnum` — general, reduced, super-reduced, zero,
  exempt.
- `VATRate: _StrictFrozen` — frozen pydantic record with
  `member_state`, `kind`, `pct: Decimal` (0 ≤ pct ≤ 100),
  `effective_from`, `effective_until`, `boe_or_directive_reference`.
- `Citation: _StrictFrozen` — frozen pydantic record with `source:
  CitationSource`, `article`, `url`, `quoted_text_es`, `retrieval_date`.
- `VATRegulation: _StrictFrozen` — the main rule record, carrying a
  tuple of citations (min 1 enforced by model validator), trilingual
  label/description/triggers/iva_treatment, modelo references,
  reverse-charge flags and notes.
- `VATCatalogue: _StrictMutable` — strict mapping wrapper used both
  for the in-memory `VAT_CATALOGUE_2025` singleton and for future
  loaded-from-disk catalogues.
- `VAT_RATE_TABLE` — a `Mapping[EUMemberState, tuple[VATRate, ...]]`
  with ≥50 entries, ES and DE fully expanded, every other member
  state at least `GENERAL`.
- `VAT_CATALOGUE_2025` — hand-curated, one `VATRegulation` per
  `VATCategory`, ≥32 `Citation` records in aggregate, every citation
  backed by Spanish quoted text from Ley 37/1992 (or Directive
  2006/112/EC where EU-level citing is more natural).
- `lookup_rate`, `cite`, `load_vat_rules_from_manual`,
  `verify_catalogue`, plus a dedicated error hierarchy rooted at
  `VatError(AeatError)`.

A Typer sub-app `aeat vat` exposes `categories list`, `rates list`,
`show`, `rule` and `verify`, mirroring the `aeat normatives` CLI
ergonomics.

Configuration adds a single new setting,
`aeat_vat_catalogue_root: Path`, defaulting to
`corpus/financial/vat`. The loader does NOT attempt to parse the
Manual práctico IVA PDF; when no structured `{year}.json` file is
present it falls back to the in-memory `VAT_CATALOGUE_2025` and logs
the fallback at INFO.

## alternatives considered

- **Python dataclasses / bare dicts.** Rejected — violates the
  project-wide pydantic v2 mandate and the strict / frozen invariant.
  Dataclasses cannot enforce the trilingual authoritative-`es`
  contract without a lot of bespoke plumbing.
- **Enums only, no per-regulation metadata.** Rejected — downstream
  categorisation needs the `declares_in_modelos`, `requires_*` flags,
  and the citation audit trail. A bare enum cannot carry those.
- **Extend `aeat.domain.normatives` directly with VAT records.** Rejected —
  `aeat.domain.normatives` codifies the *act* (Ley 37/1992 with article
  metadata). The R-1 substrate codifies *rules about transactions*
  that happen to cite articles of that act. Collapsing the two
  conflates axes (normative reference vs. transaction classifier)
  and would leak across Track A and Track B boundaries.
- **Parse the Manual práctico IVA PDF at import time.** Rejected — a
  parsing job is a multi-week effort that belongs to a separate
  issue. The substrate must land with a working fallback.
- **Separate repo / package.** Rejected — corpus-as-code is a
  project invariant; splitting this out would fragment the review
  story and complicate `just lint/typecheck/test/hooks`.

## consequences

- Peer features #73 (`financial/providers`) and #77
  (`financial/categories`) can now import `VATCategory`,
  `VAT_CATALOGUE_2025`, and `lookup_rate` without needing their own
  VAT plumbing.
- The `corpus/financial/vat/` directory is reserved as the on-disk
  home for structured year-keyed VAT catalogues. The loader already
  knows how to hand off to this directory; populating it is a
  follow-up.
- Manual práctico IVA extraction (#???) can later produce a
  `{year}.json` file that plugs into `load_vat_rules_from_manual`
  without any further code changes.
- `tests/test_config.py` gains one new variable (`AEAT_VAT_CATALOGUE_ROOT`);
  `.env.example` and `Settings` stay aligned by construction.
- No regressions in Track A (`aeat.domain.normatives`, `aeat.domain.manuals`,
  `aeat.adapters.outbound.aeat.export`) — the substrate is additive and untouched.

## related

- Issue #85 (this feature)
- Issue #87 (financial categorisation, consumer of this substrate)
- EPIC #104 (Transaction Data Pipeline umbrella)
- `[[2026-04-13-r1-vat-enumeration-research]]`
- `[[2026-04-13-r1-vat-enumeration-plan]]`

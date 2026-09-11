---
tags:
  - '#research'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:f143bc3b344c6d0659d7e7bfa307cae311c9b3f5117c0d9cd5fe28d5ec045d3d'
related:
  - "[[2026-09-09-facts-registry-plan]]"
  - "[[2026-09-09-facts-registry-governed-fact-catalogue-adr]]"
---
# `facts-registry` research: raw IVA authority retirement evidence

The approved S81â€“S85 objective remains correct, but the steps are not implementable as written: each retained IVA legal table requires a new closed fact-family contract, and `domestic_zero` has no general legal grounding. The evidence favors a new ADR followed by an amended plan, then an explicitly approved migration and deletion sequence; removing the raw paths first or coercing them into generic mappings would lose legally operative meaning.

## Findings

### Four closed fact families are required before migration

The accepted governed-fact ADR requires a closed family, query, result, provider, validation, and tooling lifecycle for new payload semantics; it rejects flattening divergent payloads into generic dictionaries. ` .vault/adr/2026-09-09-facts-registry-governed-fact-catalogue-adr.md:109` and `src/cadrumo/domain/calculations/registry/facts/schema.py:130` show the present seven-family boundary. The reader inventory establishes that catalogue regulation, place-of-supply, postal territory, and territorial carve-out semantics are each outside that union. A new ADR must define their payloads, selectors, result/provenance projection, validation, provider enrollment, artifact format, and consumer migration before the corresponding TOML readers can be deleted.

### Catalogue migration has an unresolved substantive question

`src/cadrumo/_data/registry/aeat/iva/catalogues.toml:80` records that LIVA Article 91 supports only a narrow donation provision, not a general domestic zero rate. The retirement ledger therefore requires re-grounding or splitting `domestic_zero` before migration: `dev/registry/analysis/facts_iva_retirement.toml:11`. The ADR must choose one evidence-backed disposition: split into exact legal cases, make the category unsupported until grounded, or retire it after a consumer sweep. The source evidence does not support choosing among those options by inference.

### Place and territory facts have non-interchangeable legal absences

Place-of-supply uses ordered references, a distinguished establishing reference, intentional legal silence, and an exempt R99 sentinel: `src/cadrumo/domain/iva/place_of_supply.py:73`. Postal territory distinguishes malformed input from an unmatched valid prefix and combines legal and geography provenance: `src/cadrumo/_data/registry/aeat/iva/territories.toml:14`. Carve-outs encode a three-way disposition and must refuse parent cycles: `src/cadrumo/_data/registry/aeat/iva/territory_carve_outs.toml:79`. Generic mapping or override payloads would conflate those distinct states, so the no-legacy objective requires new precise models rather than adapter preservation.

### S81â€“S85 need an amended deletion matrix

S81 omits live paths including `src/cadrumo/core/resources/_repos/iva_catalogues.py:36`, the catalogue cache/parser, `IvaCitation` and `IvaRegulation` types, the local catalogue verifier, and their consumers. The S58 audit independently records that raw readers and IVA-local grounding keep sole authority unproven: `.vault/audit/2026-09-11-facts-registry-s58-handoff-audit.md:20`. The amendment must name every deletion target and replace the ledger's obsolete suggestion to project the old `IvaCatalogue` API with direct canonical fact-result consumers or a newly defined canonical result model.

### Evidence prerequisites prevent unsupported replacement

The legal variants require pinning LIVA Article 3 and Articles 68â€“70 plus category-specific provisions to their actual effective windows. Postal territory also needs a versioned authoritative postcode-prefix source for 35, 38, 51, and 52. Carve-outs need a verified technical-country identity source while retaining `country_names.toml` as technical vocabulary. The current BOE consolidated LIVA text is available at https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740&p=20260228&tn=2, but each proposed fact still needs its own source window and anchored evidence; current facts validation must not be weakened to admit an unsupported broad claim.

## Sources

- `.vault/adr/2026-09-09-facts-registry-governed-fact-catalogue-adr.md:109`
- `.vault/plan/2026-09-09-facts-registry-plan.md:198`
- `.vault/audit/2026-09-11-facts-registry-s58-handoff-audit.md:20`
- `dev/registry/analysis/facts_iva_retirement.toml:11`
- `src/cadrumo/domain/calculations/registry/facts/schema.py:130`
- `src/cadrumo/domain/iva/catalogue.py:33`
- `src/cadrumo/domain/iva/place_of_supply.py:73`
- `src/cadrumo/domain/iva/establishment.py:226`
- `src/cadrumo/domain/iva/_grounding.py:52`
- `src/cadrumo/_data/registry/aeat/iva/catalogues.toml:80`
- `src/cadrumo/_data/registry/aeat/iva/territories.toml:14`
- `src/cadrumo/_data/registry/aeat/iva/territory_carve_outs.toml:79`
- https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740&p=20260228&tn=2

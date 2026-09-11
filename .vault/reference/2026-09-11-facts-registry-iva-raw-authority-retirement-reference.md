---
tags:
  - '#reference'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:aacbc833979767b24cd780985a7bdfc413b554518bb982edcf8d8b6c3efe8ae8'
related:
  - "[[2026-09-11-facts-registry-iva-raw-authority-retirement-research]]"
---
# `facts-registry` reference: raw IVA authority reader inventory

## Summary

The four remaining raw IVA legal tables are operative authority, not removable data residue. They have no lossless representation among the currently enrolled scalar, bracket, mapping, entity-set, override, event, and multi-output fact families. Each therefore requires a closed typed payload, query/result, validator, provider enrollment, artifact serialization, authority-only consumer migration, and detector teeth before its raw reader and file can be deleted. `country_names.toml` is deliberately retained as separately classified technical vocabulary.

### Catalogue regulations

`src/cadrumo/domain/iva/catalogue.py:33` reads `iva/catalogues.toml` directly and `src/cadrumo/core/resources/_repos/iva_catalogues.py:36` projects it by year. The replacement must preserve 21 category rules, reverse-charge and supplier-NIF flags, manual-reference and exemption semantics, and per-citation legal identifier, verbatim quotation, verified-or-unresolved state/reason, and closed citation window. The existing resolver's exact-year and evidence refusal behavior is at `src/cadrumo/domain/iva/catalogue.py:140`; neither mappings nor multi-output facts carry per-entry citation disposition. The current `IvaCatalogue` facade must not survive as a forwarding compatibility adapter.

### Place of supply

`src/cadrumo/domain/iva/place_of_supply.py:73` owns 22 closed-window rules keyed by classifier rule id; `src/cadrumo/domain/iva/classification.py:935` consumes the selected rule. A replacement must keep ordered legal references, exactly one establishing reference, goods/services/intentional legal silence, notes, and the citation-free R99 exemption sentinel. `None` supply nature is a legal meaning, not absent data. The new fact family must prove classifier parity, unknown and uncovered-window refusal, and an authority-only projection without retaining the raw loader.

### Postal territorial applicability

`src/cadrumo/domain/iva/establishment.py:746` reads grouped two-digit prefixes from `territories.toml`. The legal behavior distinguishes a valid unmatched postal prefix (mainland) from malformed or unavailable input (no inference), and needs both LIVA legal evidence and administrative-geography provenance. The replacement needs unique prefix validation, a closed territorial scope, grouped-prefix payloads, exact-prefix parity, and explicit malformed-input refusal.

### Territorial carve-outs

`src/cadrumo/domain/iva/establishment.py:226` reads the 12 records in `territory_carve_outs.toml`. Each record has exactly one disposition: assimilate to a parent country, establish a direct scope, or deliberately establish nothing. The fact family must preserve dynamic parent resolution, alpha-2 validation, evidence, parent existence, and acyclic-chain refusal. A generic map would erase the intentional non-answer and cannot validate the parent graph.

### IVA-local grounding

`src/cadrumo/domain/iva/_grounding.py:52` validates raw-table legal evidence at runtime for place-of-supply and territorial loaders. Its removal is safe only after provider validation and the published authority retain equivalent evidence, provenance, and refusal semantics at runtime. Compiler-only validation is insufficient for product behavior.

### Required replacement gates

Port the useful semantic assertions rather than preserving raw-adapter tests: exact resolution, window, no-match, exempt/silent, parent-cycle, malformed-selector, evidence mutation, artifact-only runtime, and consumer parity. Then remove S81â€“S85 holds from `dev/registry/analysis/facts_iva_retirement.toml`, make `dev/registry/tests/test_facts_catalogue_quality.py:217` require their absence, and remove raw-read exceptions in `dev/quality/tests/test_governed_fact_runtime_reads.py:420`.

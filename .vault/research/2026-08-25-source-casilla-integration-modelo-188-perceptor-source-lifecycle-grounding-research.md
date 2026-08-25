---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:06ae4b074091c0732477e2f829253a0ce7516cbac09c136c46da3358c0616ff5'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` research: `modelo 188 perceptor source lifecycle grounding`

This research establishes the exact historic and current M188 evidence boundary. It does not make a source-connectivity disposition: the current record proves filing destinations and requirements, but does not evidence a canonical external source fact, native grain, holder, or secure owner. It supports a present **no-current-candidate** finding, not a claim that M188 tax facts are inapplicable.

## Findings

### Exact eras are a composite historic record plus the current 2023-onward revision

BOE-A-1999-22372 originally approved the annual M188 summary, perceptor sheets, and Annex-V physical/logical record design (BOE XML SHA-256 `d984df98c7bc26d7c0afb689250e31c393fd51a9ef3f20edadc550692c2118a7`). BOE-A-2007-18192 altered type-2 additional information and keys (SHA-256 `79d9d41311387d4a8424c89ca35de60acbce8b5ad2d6664414647dfddf8b91ca`); BOE-A-2015-11074 added positions 153--210 for renta-vitalicia and related fields (SHA-256 `fc71c6e65271ff5922250eb5f8c1fc544b41b22b063a5b9b7239357569122c41`); and BOE-A-2017-15845 changed type-2 positions and first applied for exercise 2017 (SHA-256 `71701bc68ab9426e45dedced76ce45071ca3fb45eaac62e5461b084fa6625cfa`). Those sources form the needed historic composite for 2019--2022; the current raw design cannot be backdated into that interval.

BOE-A-2023-24412 Article 5 changes type-1 declarant NIF and type-2 perceptor, representative, and province fields, first applying to exercise 2023 filed in 2024 (BOE XML SHA-256 `1b0fc692dbdd8d3e522838785cce59def4ecd9a4b1d077a80cdaddb855b2bd94`). AEAT's current catalogue identifies M188 as Orden EHA/3021/2007 updated by Orden HFP/1284/2023. The bundled current primary design is `DR_Mod_188_2023.pdf`, 106,418 bytes, SHA-256 `30ced236b558de21383c3eba6339cb720fc9a704d38eaa574dd9be55cf90f9e3`. The active registry therefore selects only `2023-y-siguientes/0A` and refuses 2019--2022; it preserves the temporal boundary rather than treating the 2023 PDF as prior-era proof.

### Official destinations require a distinct repeated perceptor fact grain

The 2023 type-1 record identifies the declarant and annual summary. Its type-2 record has perceptor and representative identity and domicile attributes, modality, signed capital-income amount, additional information, reductions, withholding base, rate, withheld amount, accrual exercise, and key. Summary values aggregate type-2 rows by positive versus negative-or-zero withholding base, and the same perceptor may occur more than once. A future lossless source lifecycle must therefore establish durable perceptor-row identity, multiplicity, provenance, and absence, zero, and correction semantics; a summary total, record coordinate, or generic repeated-record transport cannot establish them.

### Existing application paths are manual summary destinations, not a source lifecycle

The loaded `188/2023-y-siguientes/0A` snapshot is applicability-grade with five manual `resumen` casillas (`01`--`05`). It has no bindings, formulas, export layouts, or extraction profiles. The narrow parity test only checks those five current-design summary spans. Application links describe consumers; they do not create an insurer or perceptor fact carrier, acquisition path, resolver, or source owner.

Those five genuine direct-manual summaries remain preserved. They are not a repeated-row ingress or substitute for perceptor identity, multiplicity, modality, value provenance, or correction/absence rules. Exact source-connectivity, filing-producer, resolver, and storage scans found no M188-specific carrier, secure repository, candidate row, source-mesh resolver, producer namespace, parser, or canonical lifecycle.

### Filing transport and post-filing reads do not become value sources

AEAT's M188 procedure offers file presentation and, from 2020, consultation/cancellation. They are filing transport and post-filing read routes. The official record design, export coordinates, and a parsed filed declaration describe what is submitted, not pre-filing acquisition of an insurer/declarant fact, native perceptor-row grain, source identity, encrypted persistence, or provenance. Generic filing-observation storage cannot supply that missing evidence.

## Current evidence boundary

No source-connectivity candidate is currently supportable: no official or repository evidence identifies a canonical external source fact and holder, native source grain, fact-to-destination mapping, or encrypted non-lossy owner. This does not declare required M188 facts tax-inapplicable and does not change the five manual casillas, the 2019--2022 temporal refusal, or export boundaries.

A later source-connectivity step may reopen only after all of the following are evidenced and reviewed: (1) exact hash-pinned 2019--2022 historical composite selection where that period is in scope; (2) an official canonical source fact and authoritative holder, native row grain, durable identity, acquisition/ingress provenance, and absence/duplicate/correction semantics; (3) an exact one-era type-1/type-2 destination map with derivation, aggregation, sign, unit, and rounding rules; (4) an encrypted, non-lossy owner with replay and provenance; and (5) separately governed producer/map/render/generated-byte evidence for any export connection.

## Sources

- https://www.boe.es/buscar/doc.php?id=BOE-A-1999-22372
- https://www.boe.es/buscar/doc.php?id=BOE-A-2007-18192
- https://www.boe.es/buscar/doc.php?id=BOE-A-2015-11074
- https://www.boe.es/buscar/doc.php?id=BOE-A-2017-15845
- https://www.boe.es/buscar/doc.php?id=BOE-A-2023-24412
- https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI08.shtml
- https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_188/manifest.json`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_188/files/01-188-diseno-de-registro-actualizado-en-2023.pdf.extracted.md`
- `src/cadrumo/_data/registry/aeat/modelos/188/revisions/2023-y-siguientes/revision.toml`
- `src/cadrumo/_data/registry/aeat/modelos/188/revisions/2023-y-siguientes/casillas/c01__c05.toml`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_187_188_194_registry.py`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_188_resumen_matches_its_design.py`
- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py`
- `.vault/reference/2026-08-24-registry-completeness-closure-modelo-188-design-era-coverage-reference.md`
- `.vault/audit/2026-08-25-registry-temporal-coverage-s46-m188-design-era-review-audit.md`

---
tags:
  - '#adr'
  - '#modelo-303-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-303-calc-verify-research]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-25-mandatory-citations-adr]]"
---

# `modelo-303-calc-verify` adr: Tier-L calc-verify-roundtrip | (**status:** `accepted`)

## Problem Statement

EPIC `#316` requires per-modelo calc-verify-roundtrip coverage for Modelo 303 across 2024, 2025, and 2026. The repository already had 2024 and 2025 rulesets plus a 2025 extractor/generator path, but no 2026 ruleset, no 2026 extractor registration, no rule-delta manifest, and no M303-specific L1 anchor decision.

## Considerations

The M130 reference implementation establishes the pattern: separate per-year ruleset modules, year-scoped formula IDs, BOE-cited rule-delta documentation, mutation-harness enumeration, and explicit L1 anchor handling.

Modelo 303 differs from M130 because the scoped formula graph is rate-bucket heavy. The core computed surface is `03`, `06`, and `09` for 4 / 10 / 21 percent output VAT, `44` and `45` for deductible VAT and régimen-general result, and `64`, `66`, `69`, `71` for the result chain.

Primary BOE sources confirm no numeric change for the represented régimen-general rates:

| Source | Role |
| :--- | :--- |
| LIVA art. 90, `BOE-A-1992-28740#a90` | 21 percent general IVA rate |
| LIVA art. 91, `BOE-A-1992-28740#a91` | 10 percent reduced and 4 percent super-reduced rates |
| RIVA art. 71, `BOE-A-1992-28925#a71` | liquidation period and self-assessment framework |
| Orden EHA/3786/2008, `BOE-A-2008-20953` | Modelo 303 official form |
| Directiva (UE) 2020/285 and AEAT 2026 control-plan note | small-enterprise franquicia watch-list, not implemented in this base ruleset |

## Constraints

The implementation must not expand into `#345` IVA complexity children. Franquicia, prorrata derivation, recargo de equivalencia, simplified regime, bienes de inversión deep regularisation, OSS/IOSS, and foral/regional regimes are independent rule families outside the current base régimen-general formula graph.

Every computed casilla must keep a non-empty `LegalCitation`. Tests must use real rulesets, real formula engine evaluations, real synthetic PDFs, and real CLI invocations. No mocks or live AEAT submission paths are involved.

## Implementation

The 2026 ruleset is implemented as a structural clone of the 2024 / 2025 scoped graph. It imports the shared casilla and citation tuples from the 2024 module, declares `modelo_303.2026.*` formula IDs, and binds the stable 21 / 10 / 4 percent rates to a 2026 `ParameterTable`.

The extractor registry adds `Modelo303V2026Extractor` as a thin subclass of `Modelo303V2025Extractor`. The synthetic layout and 33-casilla regex map are unchanged; only `TemplateRevision(modelo="303", año=2026, revision="2026.01")` differs.

> **Correction — 2026-05-21.** The per-modelo `DeclaracionExtractor` ABC,
> `GenericDeclaracionExtractor`, the `_extractors/` class registry, and all
> per-modelo extractor subclasses described in this section were subsequently
> deleted. Declaración extraction is now driven entirely by registry
> `declaracion_pdf` extraction profiles. The `Modelo303V2026Extractor` class
> described here no longer exists. See ADR
> `2026-05-21-declaracion-extraction-architecture-adr`.

The round-trip strategy is L3 synthetic PDF generation followed by `parse_declaracion` and `aeat filing import --from-declaracion`. The integration class keeps the existing English, Spanish-default, partial-extraction, and discrepancy-classifier cases, and adds a 2026 happy-path case.

The L1 decision is an explicit waiver: no public real declaration PDF is pinned because a real Modelo 303 declaration contains taxpayer-specific data. Public legal anchors remain in BOE citations, while executable extraction evidence comes from the L3 generator.

## Rationale

A clone is safer than attempting to encode future special-regime behavior without a casilla-level mandate. The current ruleset only represents a narrow, already-tested régimen-general liquidación graph; the BOE sources for that graph remain stable. The franquicia material is real policy context, but current evidence points to separate/future model surfaces rather than a change to these computed casillas.

The per-year file preserves future divergence. If a 2026 or later amendment changes a rate or introduces a new M303 casilla in the scoped graph, the year-specific formula IDs and effective date window give the registry a clean place to express it.

## Consequences

Modelo 303 now resolves and verifies for 2024, 2025, and 2026 with 100 percent citation coverage on computed casillas and mutation-harness enumeration for the new 2026 nodes.

The implementation is deliberately honest about exclusions. Users should not read `modelo_303.2026` as full support for every 2026 IVA special regime; it is the scoped Kent-relevant régimen-general verify surface. The deferrals are documented in the rule-delta manifest and L1 waiver.

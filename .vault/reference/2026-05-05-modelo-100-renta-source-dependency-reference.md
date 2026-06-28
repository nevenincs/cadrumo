---
tags:
  - '#reference'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-modelo-100-renta-aggregation-audit]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-adr]]'
  - '[[2026-05-04-live-filing-data-capture-adr]]'
---



# `modelo-100-renta` reference: source families and dependency boundaries

Topic: Modelo 100 Renta source and dependency grounding for the central AEAT
legal calculation registry.

Audit surface: official AEAT Modelo 100 procedure, AEAT Modelo 100 record
designs, AEAT Renta 2025 manual and presentation help, BOE Modelo 100 order,
BOE LIRPF and RIRPF consolidated law/regulation, and existing local Renta
corpus/resource manifests.

Rewrite scope: this document does not design runtime code and does not preserve
the old Renta ruleset architecture. It records the resource boundary that the
Modelo 100 registry design and implementation must consume.

## Reference Principle

Modelo 100 is the annual IRPF settlement parent. Its registry definition must
derive legal calculations from BOE law/regulation and AEAT official guidance,
then reconcile observations from read-only AEAT or local filing artefacts.
Record designs, XSDs, dictionaries, PDFs, and Renta WEB Open can prove schema,
layout, parser, or parity behaviour. They cannot replace the legal calculation
basis.

The existing Renta rulesets, rental helpers, amortization helpers, category
profiles, inbound/outbound extractors, and old vault documents are discovery
inputs only. They do not own Modelo 100 casillas, legal constants, formulas, or
dependency classifications after the central registry is implemented.

## Official Resource Families

| Family | Role | Local registry or corpus anchor | Official reference |
|---|---|---|---|
| Modelo 100 procedure | Procedure identity, presentation surfaces, live-data surfaces, core legal references. | Pending `registry/aeat/modelos/100.toml` source ledger. | `https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G229.shtml` |
| Modelo 100 current record designs | 2025 dictionary, toma-de-datos dictionary, and XSD source/layout evidence. | `aeat-dr-100-2025-dictionary`, `aeat-dr-100-2025-input-dictionary`, `aeat-dr-100-2025-xsd`. | `https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html` |
| Modelo 100 historical record designs | 2020-2024 dictionary, toma-de-datos dictionary, XSD, and older PDF/XLS/XLSX artefacts. | `aeat-dr-100-2020-*` through `aeat-dr-100-2024-*`; local record-design corpus. | `https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/ejercicios-anteriores-modelos-100-199.html` |
| Renta 2025 practical manual | Official AEAT guidance by Renta chapter, including work income, real-estate capital, movable capital, economic activities, special regimes, gains/losses, bases, minimums, quotas, deductions, and result. | `aeat-renta-2025-manual-parte1`; local manual corpus. | `https://sede.agenciatributaria.gob.es/Sede/Ayuda/25Manual/100.html` |
| Renta 2025 presentation help | Official form-completion guidance and form sections. | Pending source ledger entries by section. | `https://sede.agenciatributaria.gob.es/Sede/Ayuda/25Presentacion/100.html` |
| BOE Modelo 100 order | Official approval of Modelo D-100 and Modelo 100/102 documents for ejercicio 2025, filing procedures, borrador/datos fiscales procedures, and annual changes. | `orden-hac-277-2026:art-3`; `boe-modelo-100-2025-form`; local BOE HTML corpus. | `https://www.boe.es/buscar/doc.php?id=BOE-A-2026-7041` |
| LIRPF | Primary legal authority for IRPF income classes, reductions, bases, quotas, deductions, payments on account, declaration obligations, and final settlement. | Existing `ley-35-2006:*` legal entries; add missing articles per construct. | `https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764` |
| RIRPF | Regulatory authority for IRPF procedures, retention/payment rules, objective/direct estimation detail, and borrador/datos fiscales provisions. | Existing `rd-439-2007:*` legal entries; add missing articles per construct. | `https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820` |
| Renta WEB Open | Read-only parity surface for synthetic/manual comparison only. It is not authenticated, does not validate taxpayer census data, and does not permit presentation. | Live/static cross-reference guard and parity evidence ledger only. | `https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/renta-ayuda-tecnica/renta-web-open.html` |
| Authenticated AEAT surfaces | Read-only observations for user-owned filed data, fiscal data, borrador, declaration, PDF, submitted-file, and justificante content. | Encrypted observation store and remote-state guard only. | Modelo 100 procedure and live-filing data capture ADR. |

## Local Corpus Coverage Ledger

The local official record-design manifest currently contains 29 Modelo 100
artefacts retrieved on 2026-05-03. For filing-grade central registry work, the
current supported revision candidate set is ejercicio 2020 through ejercicio
2025 because each of those years has a declaration dictionary, toma-de-datos
dictionary, and XSD in the local corpus. Earlier 2009-2019 artefacts are useful
historical layout evidence but are not filing-grade supported revisions until a
separate support-boundary decision retains them.

| Ejercicio | Declaration dictionary source ref | Toma-de-datos source ref | XSD source ref | Local evidence |
|---|---|---|---|---|
| 2020 | `aeat-dr-100-2020-dictionary` | `aeat-dr-100-2020-input-dictionary` | `aeat-dr-100-2020-xsd` | Manifest has `diccionarioXSD_2020.properties`, `diccionarioDlgXSD_2020.properties`, and `Renta2020.xsd`. |
| 2021 | `aeat-dr-100-2021-dictionary` | `aeat-dr-100-2021-input-dictionary` | `aeat-dr-100-2021-xsd` | Manifest has `diccionarioXSD_2021.properties`, `diccionarioDlgXSD_2021.properties`, and `Renta2021.xsd`. |
| 2022 | `aeat-dr-100-2022-dictionary` | `aeat-dr-100-2022-input-dictionary` | `aeat-dr-100-2022-xsd` | Manifest has `diccionarioXSD_2022.properties`, `diccionarioDlgXSD_2022.properties`, and `Renta2022.xsd`. |
| 2023 | `aeat-dr-100-2023-dictionary` | `aeat-dr-100-2023-input-dictionary` | `aeat-dr-100-2023-xsd` | Manifest has `diccionarioXSD_2023.properties`, `diccionarioDlgXSD_2023.properties`, and `Renta2023.xsd`; historical AEAT page lists January 2026 updates. |
| 2024 | `aeat-dr-100-2024-dictionary` | `aeat-dr-100-2024-input-dictionary` | `aeat-dr-100-2024-xsd` | Manifest has `diccionarioXSD_2024.properties`, `diccionarioDlgXSD_2024.properties`, and `Renta2024.xsd`; historical AEAT page lists January 2026 updates. |
| 2025 | `aeat-dr-100-2025-dictionary` | `aeat-dr-100-2025-input-dictionary` | `aeat-dr-100-2025-xsd` | Manifest has `diccionarioXSD_2025.properties`, `diccionarioDlgXSD_2025.properties`, and `Renta2025.xsd`; current AEAT page lists 14 April 2026 updates. |

The Renta 2025 manual corpus is currently represented by two source refs:

| Source ref | Manual part | Local evidence |
|---|---|---|
| `aeat-renta-2025-manual-parte1` | Renta 2025 practical manual, part 1. | Manifest has `source.pdf`, fetched on 2026-04-12, SHA-256 `60e6b2d71c97d93a9e0943e6ff8c886f4dd6d3741a797cb8001dcbcadfb33528`. |
| `aeat-renta-2025-manual-deducciones-autonomicas` | Renta 2025 autonomous deductions manual part. | Manifest has `source.pdf`, fetched on 2026-05-05, SHA-256 `88a12fbe5ce9de01fc6a04941db498cd30ef959c85bf6106bfdc3611c13f3481`. |

The BOE Modelo 100 order corpus is represented by `boe-modelo-100-2025-form`
and `orden-hac-277-2026:art-3`. The local HTML corpus was retrieved on
2026-05-05 and verifies the article that approves Modelo D-100 for ejercicio
2025.

The next source-ledger gap is not the record-design corpus or the 2025 annual
Modelo 100 order. It is the complete LIRPF/RIRPF article set by construct and
the CCAA legal corpus required by autonomous deductions and autonomous quota
rules.

## Dependency Classification

Every supported modelo must have one explicit relation to Modelo 100 before a
filing-grade Renta snapshot can be emitted. The relation can be direct annual
settlement input, factual evidence, or explicit non-dependency. The
classification is based on legal/source meaning, not on whether older code once
read or produced a matching number.

| Modelo | Relation to Modelo 100 | Required registry treatment |
|---|---|---|
| 111 | Direct annual-settlement dependency for work, professional, agricultural, prize, and related retentions or payments on account where they contribute to Renta income/withholding facts. | Bind through source periods and recipient/payer facts; reconcile with Modelo 190 where present. |
| 190 | Direct annual-summary dependency for work/professional recipient summaries and withholding reconciliation. | Bind annual recipient facts to Renta work/professional constructs with traceable source-period provenance. |
| 115 | Direct dependency when rental retentions affect taxpayer Renta facts or payer-side evidence is required for the taxpayer role. | Bind urban-rental withholding facts to real-estate capital constructs and reconcile with Modelo 180. |
| 180 | Direct annual-summary dependency for urban-rental withholding, payer/property evidence, and reconciliation. | Bind annual property/payer facts to real-estate capital constructs. |
| 123 | Direct dependency for movable-capital retentions and payments on account. | Bind source periods to movable-capital constructs and reconcile with Modelo 193 where present. |
| 193 | Direct annual-summary dependency for movable-capital income and withholding reconciliation. | Bind annual movable-capital facts to Renta movable-capital constructs. |
| 130 | Direct dependency for direct-estimation instalment payments, current-year economic-activity evidence, and previous-year values required by the selected Renta revision. | Bind filed/observed instalment facts through read-only observation profiles and hard-fail when required prior-period data is unavailable. |
| 131 | Direct dependency for objective-estimation instalment payments, activity/module evidence, and current-year objective-estimation reconciliation. | Bind filed/observed instalment and activity facts to the objective-estimation construct. |
| 303 | Factual evidence only for VAT context, invoice/expense reconciliation, and VAT deductibility checks. | It must not decide IRPF income, expense, or casilla treatment. |
| 390 | Factual evidence only for annual VAT-summary reconciliation. | It must not decide IRPF formulas or final settlement. |
| 347 | Factual evidence only for third-party operation reconciliation. | It must not create Renta calculation inputs unless a Modelo 100 construct declares a separate legal/source binding. |
| 349 | Factual evidence only for intra-community operation reconciliation. | It must not create Renta calculation inputs unless a Modelo 100 construct declares a separate legal/source binding. |
| 369 | Factual evidence only for OSS/IOSS VAT context. | It must not decide IRPF income or final settlement. |
| 840 | Factual evidence only for IAE activity and municipality context. | It can support activity classification but cannot own Renta calculation values. |
| 036/037 | Factual evidence only for identity, activity, regime, schedule, and obligation context. | It can support applicability and profile facts but cannot own annual Renta calculation values. |
| 202 | Explicit non-dependency for Modelo 100 calculation. | Corporate-tax instalment evidence belongs to a different tax scope unless a future official source proves a concrete Renta relation. |
| 200 | Explicit non-dependency for Modelo 100 calculation. | Corporate annual tax evidence belongs to a different tax scope unless a future official source proves a concrete Renta relation. |
| 232 | Explicit non-dependency for Modelo 100 calculation. | Related-party reporting can be evidence only if a specific Modelo 100 construct later declares a lawful link. |
| 720 | Explicit non-dependency for Modelo 100 calculation. | Foreign income, gains, imputations, or assets must be represented through Modelo 100 legal/source definitions, not inferred from filing status. |

## Renta Construct Resource Map

| Construct | Primary authority | Secondary source/evidence | Dependency inputs |
|---|---|---|---|
| `renta-source-foundation` | BOE Modelo 100 order, LIRPF, RIRPF. | AEAT procedure, record designs, manuals, presentation help. | None; parent source ledger only. |
| `renta-personal-family` | LIRPF and RIRPF personal/family/minimum provisions. | AEAT Renta manual personal/family chapters, presentation help, fiscal-data observations. | 036/037 as factual evidence only. |
| `renta-work-income` | LIRPF work-income and reduction provisions, RIRPF retention provisions. | AEAT manual work-income chapters, presentation help, fiscal-data observations. | 111 and 190 direct dependencies. |
| `renta-real-estate-capital` | LIRPF real-estate income, imputation, rental reduction, and expense provisions. | AEAT manual real-estate chapters, declaration PDFs, fiscal-data observations. | 115 and 180 direct dependencies; 303/390/347 evidence where relevant. |
| `renta-movable-capital` | LIRPF movable-capital income and reduction provisions. | AEAT manual movable-capital chapters, fiscal-data observations. | 123 and 193 direct dependencies. |
| `renta-economic-activities` | LIRPF economic-activity provisions, RIRPF direct/objective-estimation rules, annual objective-estimation orders. | AEAT manual economic-activity chapters, IAE/activity evidence, invoice/category evidence. | 130 and 131 direct dependencies; 303/390/347/349/369/840/036/037 evidence. |
| `renta-amortization-inventory` | LIRPF economic-activity and real-estate provisions, applicable LIS/RIRPF references where incorporated by IRPF rules. | AEAT manual tables and activity/property evidence. | Economic-activity, real-estate, asset, and inventory ledgers. |
| `renta-special-regimes-imputations` | LIRPF special-regime and imputation provisions. | AEAT manual special-regime chapters and fiscal-data observations. | Evidence depends on regime; no external modelo may own legal treatment without a declared binding. |
| `renta-capital-gains-losses` | LIRPF gains/losses, exemptions, reinvestment, integration, and compensation provisions. | AEAT manual gains/losses chapters and fiscal-data observations. | 347/720 can be evidence only; legal treatment remains in Modelo 100. |
| `renta-bases-reductions` | LIRPF base, integration, compensation, and reduction provisions. | AEAT manual base/reduction chapters. | Inputs from all income/gain constructs. |
| `renta-tax-free-minimums-and-brackets` | LIRPF state/autonomous quota provisions and CCAA law for autonomous scales. | AEAT manual minimum/quota chapters and CCAA source corpus. | Personal/family and base constructs. |
| `renta-deductions-state` | LIRPF state deduction provisions and annual special rules. | AEAT manual deduction chapters. | Fiscal-data observations where relevant. |
| `renta-deductions-autonomous` | CCAA legal sources under the ceded IRPF competence framework. | AEAT autonomous-deductions manual part and CCAA source corpus. | Personal/family, residence, disability, expenditure, and CCAA facts. |
| `renta-payments-retentions` | LIRPF/RIRPF retentions and payments-on-account provisions. | AEAT manual final-result chapters and filed-data observations. | 111/190, 115/180, 123/193, 130, and 131 direct dependencies. |
| `renta-final-settlement` | LIRPF final settlement, payment/refund, and Modelo 100/102 order provisions. | AEAT presentation help, declaration PDF, submitted-file, justificante observations. | All complete constructs. |
| `renta-observation-parsing` | Live filing data capture ADR and remote-state guard. | Borrador, declaration, submitted-file, PDF, justificante, fiscal-data observations. | Read-only encrypted evidence only. |
| `renta-export-filing-linkage` | BOE Modelo 100 order and AEAT record designs. | XSD, dictionaries, presentation help, preview/review artefacts. | Complete validated Modelo 100 snapshot only. |

## Implementation Consequences

- `registry/aeat/modelos/100.toml` must be the only Modelo 100 filing-grade
  authority.
- Python modules may load, validate, calculate, parse, and reconcile; they must
  not own legal constants, casilla dependencies, source metadata, or revision
  selection.
- Every Renta construct must carry legal refs, source refs, casilla scope,
  formulas or algorithm bindings, parser bindings, observation bindings, and
  hard failure conditions.
- Missing official source coverage, contradictory legal/source evidence,
  unclassified dependencies, or unavailable required prior-period observations
  must fail before calculation output can be treated as filing-grade.
- Tests must exercise real registry loading, real source/legal catalogue
  verification, real local corpus files, and real relation validation. They
  must not compare against old implementation state.

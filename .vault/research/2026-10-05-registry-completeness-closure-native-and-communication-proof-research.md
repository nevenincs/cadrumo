---
tags:
  - '#research'
  - '#registry-completeness-closure'
date: '2026-10-05'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:14c4ebf2864b3405ccf1050f16c67d6da4ce18aed3a63e80ff12b2be2ba78deb'
related:
  - "[[2026-08-24-registry-completeness-closure-adr]]"
  - "[[2026-08-25-registry-completeness-closure-s33-two-channel-export-proof-adr]]"
  - "[[2026-10-04-authority-health-completion-audit]]"
---

# `registry-completeness-closure` research: `Production proof boundaries for communication and native XML export`

The current closure contract cannot represent two existing production export purposes faithfully. M145 is a local communication with its own canonical export service; M100 uses XML dictionary rendering with official dictionary/XSD evidence. The evidence favours extending the existing two-channel proof through closed purpose/transport variants rather than changing their domain periods or pretending that native XML has fixed-width positions. Acceptance, authorization and native provenance publication remain separate work.

## Findings

### M145 has a canonical communication exporter and no calculation approval to replay

The application expressly refuses filing-like surfaces and resolves the communication token through its own typed period: `src/cadrumo/application/modelo/m145_communication.py:88`. Its actual exporter is `src/cadrumo/application/modelo/m145_communication_records.py:926`; it reads the stored communication, performs current registry validation and uses the injected canonical fixed-width renderer. The communication states are created, delivered_to_payer and locally_completed (`m145_communication_records.py:122`). There is no approved filing draft or calculation revision in that workflow. The earlier research records the same local ownership: `2026-06-03-m145-reopen-tractability-research` and `2026-06-04-modelo-145-reopen-research`. Their referenced May foundation ADR was not returned by current bounded discovery; that historical coverage is unresolved, not silently treated as read.

The current proof contract requires a Period, an approved ModeloDraft and a calculation revision for secure replay; both receipt types hard-code the canonical writer to export_draft (`dev/registry/filing_export_proof_contracts.py:202`, `:270`, `:320`). The current public enrollment therefore refuses M145's exact comunicacion token (`authority-health-public-proof-inventory-20261005.json`). Wrapping it in an annual or quarterly Period would change the selected purpose.

### Native XML already uses export_draft; its proof provenance remains positional

The production export owner already dispatches XML_DICTIONARY to its actual dictionary renderer (`src/cadrumo/application/filing/export.py:650`). M100's declared layout is XML dictionary, with explicit official dictionary and XSD references plus the independently declared PH18 attribute override (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/export_layouts/0001-declarations.toml:1`). The current Aux/VERSION owner derives the token from the product package version and refuses non-release or over-width representations (`src/cadrumo/domain/filing/software_identity.py:28`); the older layout comment about an absent bundled literal does not establish a current token blocker.

The current public provenance verifier loads record-design intermediate, semantic map and render-profile geometry (`dev/registry/filing_export_generated_verification.py:48`), while proof probes require positioned literals on a first required non-repeating record (`dev/registry/filing_export_proof_authority.py:367`). M100 2022-2025 consequently has no admitted generated provenance in the current enrollment. A copied fixed-width manifest would misstate the native source contract. AEAT's current technical manual index and import instructions also identify the XML route: https://sede.agenciatributaria.gob.es/Sede/manuales-tecnicos.html and https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/renta-ayuda-tecnica/presentar-declaracion-mediante-fichero-generado-externo.html . These pages do not themselves supply a native proof receipt.

### An event selector needs a real covered coordinate rather than a wider Period type

Period intentionally refuses symbolic EVENT-N and administrative tokens while accepting numbered event scopes (`src/cadrumo/core/period.py:109`). Registry classification preserves declared selector coordinates (`dev/registry/maintenance_support.py:1072`); passing that symbolic token straight to a filing-period constructor produces the four M210 residues. The existing M210 round-trip scenarios declare annual coordinates (`dev/registry/edition_export_scenarios.py:383`), so they cannot be imported as accepted event proof. A prospective fix must select a concrete event admitted by the existing canonical selector, retain that actual snapshot reference and verify exact official rendering. Whether all M210 producer inputs support that coordinate has not been proven in this research.

### Proof capability and authorization must remain independent

The accepted two-channel decision requires both a repeatable public canonical writer proof and real source-owned replay under encrypted custody (`2026-08-25-registry-completeness-closure-s33-two-channel-export-proof-adr`). Neither a newly implemented transport branch nor a non-sensitive vector supplies private approval. The existing profile inventory is currently refused for session reason absent; current noninteractive authentication must use an enrolled API credential or native attended delegation. No source-owned record inventory, private values, payload digest or acceptance receipt is included here (`2026-10-04-authority-health-completion-audit`).

### Closed purpose and probe variants preserve the useful guarantees

Keep the current positional draft variant unchanged for ordinary fixed-width filing. Add a narrowly typed communication variant invoking M145's existing owner and binding its validated source-owned communication record; add native XML provenance/probes through the existing canonical compiler/publisher and dictionary/XSD validator. Both variants must retain source digests, exact selected layout/revision, stale/conflicting evidence refusal, actual canonical writer execution, current encrypted replay custody and a secret-free public receipt.

Broadening Period conflates a communication with a filing period and is rejected by the existing type contract. Excluding these filing-grade declarations or marking missing channels successful would weaken the accepted completeness decision. Adding a second writer, authority loader or hand-maintained eligibility list would violate its ownership contract. Simply retaining the present positional-only proof is coherent but leaves the observed release blocker unresolved.

## Sources

`2026-08-24-registry-completeness-closure-adr`; `2026-08-25-registry-completeness-closure-s33-two-channel-export-proof-adr`; `2026-10-04-authority-health-completion-audit`; `2026-06-03-m145-reopen-tractability-research`; `2026-06-04-modelo-145-reopen-research`; the code locators above; `var/storage/development/authority-health-public-proof-inventory-20261005.json`. Current AEAT pages were read through public browsing on 2026-10-05; they support the transport context only. Runtime custody access, native provenance implementation and full historical ADR reconciliation remain unverified.

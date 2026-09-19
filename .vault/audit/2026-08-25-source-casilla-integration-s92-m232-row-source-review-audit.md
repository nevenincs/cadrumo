---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:b9c3d4082fa6ed4056c5d1269ec5707fad5eac96b9ce838aaf11a998c5786606'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` audit: `S92 M232 row source review`

## Scope

Independent review of S92 in commit `94c7436d15`: the official reporting requirement, the M232 registry and row carriers, worksheet assembly, and source-mesh enrollment.

## Findings

### official-row-grain | low | verified with terminology correction

Article 3.1 of Orden HFP/816/2017 requires separate income and payment reporting, grouping by counterparty, operation type, and valuation method, while preserving relationship type. The domain `RelatedPartyOperationObservation` has neither direction nor relationship type and groups without either; it therefore cannot be an authority-complete resolver carrier. The separate CLI `Modelo232VinculadaRow` does carry `tipo_vinculacion`, so the research now names the deficient carrier precisely instead of implying that every M232 row carrier lacks the field. https://www.boe.es/buscar/doc.php?id=BOE-A-2017-10042

### source-ownership-and-deferral | low | verified

The worksheet assembler derives a synthetic source id from a row position and explicitly does not choose ownership or provenance. Exact source-mesh inspection keeps `RELATED_PARTY_OPERATION` in `DEFERRED_SOURCE_KINDS`; no production resolver or secure repository owner for this source kind is enrolled. S93, S94, and S95 remain unchecked, and no resolver implementation was introduced by the reviewed commit.

### canonical-research-linkage | low | corrected

The canonical CLI-created research record, the execution record scope, and the feature index agree on the feature-prefixed M232 research identifier. The checked S92 plan prose and a duplicate trailing execution-template block instead named an absent unprefixed identifier. This review corrects both links and removes the stale template residue.

## Recommendations

S93 must choose a single secure ingress authority that retains direction and relationship type before removing deferral. S94 must prove preservation and mutation refusal through the full row lifecycle; S95 remains the required formal-close gate.

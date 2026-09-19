---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:28eaa123f4b36bf0dab3b9503500acd4ba076bda64178c8defe3a6bab6ec1f03'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# `registry-completeness-closure` audit: `S23 independent Modelo 721 structured-message post-review`

## Scope

Independent post-review of commit `b54e2b39dc` and its Modelo 721
adjudication. The review rechecked the primary BOE orders, AEAT's active
web-service description, the loaded Modelo 721 revision and source catalogue,
the canonical export and proof paths, the existing export-policy decision, and
the S26/S27/S28 owner routing. A Vaultspec-RAG-led semantic discovery was
followed by whole-module reads and exact-symbol confirmation to check for a
parallel or redeclared filing implementation.

## Findings

### modelo-721-positional-only-policy | high | The existing export-availability predicate cannot represent the reviewed SOAP/XML authority

The S23 non-fileable conclusion is correct today. BOE-A-2023-17429 requires
computer messages and defers their format and design to AEAT; BOE-A-2024-27528
replaces the annex for exercise 2024. AEAT's official service description
specifies SOAP 1.1 document/literal over HTTPS, client-certificate
authentication, request and response messages, a WSDL, input XSDs
`Declaracion721.xsd` and `DeclaracionInformativa721.xsd`, and a response XSD.
None of those technical artifacts is presently source-catalogued and
hash-pinned, while the loaded revision remains applicability grade with seven
casillas, no bindings, and no export layout.

However, `modelo_publishes_a_record_design` treats `record_design` as the only
fileable authority and its documentation classifies Modelo 721's BOE annex as a
printable form. `ExportLayoutFormat` exposes only fixed-width and standalone
XML-dictionary shapes. This was a sound refusal for the old positional-record
question, but it cannot express a source-backed SOAP/XML declaration. In
particular, after technical sources are acquired, a Modelo 721 promotion still
cannot state what source shape authorises the SOAP wire contract; and while it
has no layout the same predicate suppresses the build-time missing-layout
refusal because it remains false. The runtime filing boundary still refuses the
empty layout, so the gap does not create a current false filing claim, but its
policy and tracking classification are stale and could obstruct or misstate the
only supported future route.

This is a distinct decision and implementation slice, not permission to add a
second writer. Vaultspec-RAG located the existing canonical `export_draft` and
the standalone XML-dictionary renderer; exact confirmation found no `m721.`
producer namespace, Modelo 721 map, render profile, generated fragment,
emitted-payload proof, SOAP client, or alternative filing path. The XML-dictionary
writer's dictionary-and-XSD document shape does not cover a SOAP envelope,
operation contract, response lifecycle, or client-certificate transport.

## Verification

The official-service claims were independently checked against AEAT's active
Modelo 721 web-service description and the two BOE orders. Registry inspection
confirmed the exact loaded applicability-only surface. The semantic discovery
and exact sweep confirmed one canonical export path and no Modelo 721 code
redeclaration. No production code was changed by S23 or this review.

## Verification limitation

`test_modelo_721_registry.py` passed all 20 focused tests. The eight focused
`test_export_exemption_declared.py` tests could not construct the shared
registry because concurrent deadline-window work leaves unrelated Modelo 184,
Modelo 303, and Modelo 322 registry-validation failures. This review does not
call that blocked global authority load a pass; the direct read of
`modelo_publishes_a_record_design`, the source catalogue, and the runtime
filing-capability boundary is the evidence for the reported policy finding.

## Recommendations

`W02.P04.S80` is enrolled for the finding. It must obtain an architecture
decision on the source taxonomy and registry wire-shape boundary for a locally
generated, source-hash-pinned Modelo 721 SOAP/XML request. It must then route
the criterion, grade gate, canonical exporter extension, and local
emitted-payload proof into the existing export plan, with mutation coverage that
keeps Modelo 136 terminal and keeps Modelo 721 refused until every new authority
and proof condition is real. It must not author remote submission, certificate
handling, a receipt simulation, or a parallel XML writer.

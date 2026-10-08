---
tags:
  - '#reference'
  - '#censo-regimen-adoption'
date: '2026-08-08'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:a017d172ba017d112005edeb77c2afebee4997ff8d8bb9621fccae772911d8f2'
related:
  - '[[2026-08-08-censo-regimen-adoption-adr]]'
---

# `censo-regimen-adoption` reference: `grounding`

## Summary

Codebase and legal grounding for the decision on whether the censo cotejo
adopts the Ley 49/2002 régimen axis from the Certificado de Situación Censal.

## The certificate record

The two obligation-bearing fields are declared `tuple[str, ...]` — free-form prose lines with no typed vocabulary.

The module docstring records that the PDF layout extraction is deliberately
unpinned until a real issued-certificate specimen exists, and that the inbound
adapter refuses every document today. It classifies `situacion_tributaria` and
`obligaciones_periodicas` as "display-only certificate evidence".

`censo_facts_from_certificado` in the same module projects the certificate onto
candidate profile facts. It projects `domicilio_fiscal` and every `actividad`;
it projects neither obligation-bearing field, and the excluded axes carry a
per-axis rationale — `condicion_residencia` and `representantes_nif` are
excluded because mapping certificate prose onto a typed profile enum needs the
specimen's exact vocabulary and auto-mapping would conflate axes.

## The discard is total, not display-only

A tree-wide search for `situacion_tributaria` and `obligaciones_periodicas`
across Python and Markdown returns only the domain record's own declaration and
its test fixture. There is no rendering surface, no CLI payload field and no
consumer of either value anywhere. The docstring's "display-only" description
is not true of the code: the fields are parsed and then dropped.

The only vocabulary for those fields in the tree is synthetic fixture prose in
`src/cadrumo/domain/censo/tests/test_certificado.py`, authored by a test author
rather than observed on an AEAT document.

## The régimen axis on the profile

## Legal grounding for the régimen itself

The bundled consolidated corpus carries Ley 49/2002 arts. 6, 7, 10 and 14 under
`src/cadrumo/_data/corpus/normatives/html/`. Art. 14.1 states that entities
"podrán acogerse al régimen fiscal especial … en el plazo y en la forma que
reglamentariamente se establezca", that once the option is exercised the entity
"quedará vinculada a este régimen de forma indefinida", and that it remains so
"mientras no se renuncie a su aplicación en la forma que reglamentariamente se
establezca".

So the régimen is an exercised election recorded through the censal
declaration, and AEAT holds the authoritative record. What no bundled source
establishes is whether the G313 certificate prints that election, or in what
words. AEAT's "¿Qué certifica?" enumeration for the procedure lists six fields
and none of them is a régimen field.

## The divergence primitive

Re-running the cotejo replaces the whole divergence namespace.

## Prior decisions bearing on the disagreement question

`2026-06-05-live-censo-calendar-reconciliation-adr` rules that the calendar
resolves each obligation from live censo-backed facts when present, falls back
to profile facts otherwise, and refuses rather than silently defaulting,
stamping the source on every emitted obligation.

`2026-07-23-profile-setup-flow-adr` establishes the G313 artefact ingest and
the phase-8 compare-select cotejo shape.

`2026-06-13-first-filer-attestation-adr` carries the censo-versus-
self-declaration question for the first-filer case.

---
tags:
  - '#reference'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:546a171a0d37c2d257b09610c72a406816f2e577b93b764caf224a5e6b6fd8d1'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` reference: adapted family normalization

## Summary

The live provider registry still contains temporary adapters for IVA rates, IVA recargo, category profiles, legal-holiday calendars, and treaty overrides. Only the IVA rate and recargo schedules are presently assigned to S30 and their subsequent physical deletion is assigned to S56. The plan must make those lanes concrete and add independent closure for the other adapters; modelo revision data, legal/source references, and ungrounded apoderamientos are not legacy value providers.

## Scope and method

This assessment compares the approved campaign plan, the live provider registration, the owned registry directories, and the retirement ledgers. A directory is not treated as legacy merely because it is outside `facts`: the deciding question is whether it is a temporary adapter duplicating an operative governed-fact authority, an intentionally retained source authority, or a separate ungrounded product vocabulary.

## Live ownership matrix

The authored provider owns `facts` and currently loads the sixty numbered fragments directly. The IVA registration owns `iva`, compiles `rates.toml` and `recargo-rates.toml` through `dev/registry/compiler/iva.py`, and emits the `iva-rate-schedule` and `iva-recargo-by-applied-rate` facts. The IVA retirement ledger expressly assigns both schedules to W04.P15.S30, then assigns their raw parser, cache, and files to W04.P17.S56. The runtime `rates.py` and `recargo_equivalencia.py` already project the installed authority, so an authored replacement can remove rather than wrap the adapter.

Categories, legal-holiday calendars, and treaty overrides are also raw-tree-to-generated-fact adapters. They are not assigned to the IVA ledger and cannot be silently left as permanent exceptions: their provider compilers must gain individually scoped normalization and deletion closure. Categories read `categories/profiles.toml`; holidays read the yearly `calendars/festivos-*.toml` records; and treaties read `treaties/*.toml` while the broader authority also compiles its convenio catalogue. Each has different structured payload and provenance requirements.

Modelo parameter projection remains intentionally distinct. Its parameter files are canonical revision data and the provider derives facts from already compiled modelo authority without rereading or relocating them. The legal catalogue remains the supporting legal and source-reference authority, not a duplicate tax-value provider. Apoderamientos remain classified non-governed vocabulary because the required temporal evidence is absent.

The remaining IVA structured tables, including catalogue, place-of-supply, territory, and country-name data, are outside the approved S30 transfer. Their removal stays conditional on a separate evidence-backed classification and a full provider replacement; moving or deleting them now would create unsupported legal behavior.

## Plan correction

S30 must name the IVA and recargo schedules and their exact authored destination instead of saying only adapted families. W04.P17.S56 must include the development compiler and its focused tests because that file owns the raw parser and cache. Separate steps are required for category, holiday, and treaty adapter retirement, plus a classification step for the other IVA structured tables. This makes the no-legacy objective verifiable without collapsing authoritative revision data or ungrounded vocabulary into the wrong schema.

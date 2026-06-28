---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-15'
step_id: 'S04'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# Prove tree-wide that the _formats currency encode/serialise/deserialise path has zero production consumers outside its own package and tests

## Scope

- `src/aeat/adapters/outbound/aeat/export/_formats/_serialise.py`

## Description

- Grep the whole `src/aeat` tree for importers of the
  `adapters.outbound.aeat.export._formats` package and its symbols
  (`encode_currency`, `RecordSpec`, `serialise`, `deserialise`), excluding the
  package itself and tests.
- Confirm the only external reference is a docstring cross-reference in
  `core.external_constants`; every registry modelo `application_links` TOML
  routes export through `aeat.application.filing.export_draft`, and the verify
  path decodes through the registry export-parse module — not the `_formats`
  deserialiser.

## Outcome

Confirmed: the `_formats` currency encode/serialise/deserialise stack has zero
production consumers outside its own package and tests. The wired
`_format_money` path is the live one.

## Notes

Verification only; no code change. The deletion of the dormant stack (Step S05)
is deliberately left unchecked: it is owner-gated per the ADR because `_formats`
is a roundtrip-tested encoder of the AEAT submission wire format and it is not
autonomously decidable whether it is superseded dead code or an
intended-canonical implementation mid-migration.

---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S04'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Prove tree-wide that the _formats currency encode/serialise/deserialise path has zero production consumers outside its own package and tests and ## Scope

- `src/aeat/adapters/outbound/aeat/export/_formats/_serialise.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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

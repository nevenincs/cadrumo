---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S01'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---


# `fichero-boe-export-layouts` `P01.S01`

Appended the Amendment (2026-05-21) section to the fichero-BOE export ADR
recording that export layouts are authored as registry TOML, not Python modules.

- Modified: `.vault/adr/2026-04-22-aeat-fichero-boe-export-adr.md`

## Description

The original ADR section 1 described per-modelo Python submodules as the
authoring surface for `_RECORD_SPECS` tuples. The `calculation-truth-registry`
ADR (accepted 2026-05-03) superseded that direction: export layouts are now
reviewed registry data authored directly in TOML inside the per-modelo registry
files, following the pattern already shipped for modelos 180, 202, and 232.

The amendment appended to the fichero-BOE export ADR records:

- The authoring direction change: `export_layouts` blocks in registry TOML
  replace per-modelo Python format modules.
- The retained runtime: the generic serialiser and deserialiser in
  `src/aeat/adapters/outbound/aeat/export/_formats/` remain as the execution
  layer consuming registry-authored layout data.
- The deletions sanctioned by the registry-truth ADR: `_generate.py`,
  `_ingest.py`, and the DR-spec JSON fixtures.
- The decision itself is unchanged: M130 and M303 fichero-BOE export support
  remains required; only the artefact form is corrected.

No production code was modified in this step.

## Tests

No test changes. The amendment is a documentation correction only.
Registry snapshot loads and round-trip tests are deferred to P02/P03.

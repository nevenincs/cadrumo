---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S09'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P03.S09`

Built the off-load-path manifest-derivation tool that runs record-design
extraction against the corpus Diseño workbooks and emits the per-modelo
expected `(segmento, number)` casilla set.

- Modified: `src/aeat/domain/calculations/registry/_record_design.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`

## Description

`derive_diseno_completeness_casillas(path, *, multi_segment)` was added
to the read-only record-design module. It runs `extract_record_design`
against an official AEAT Diseño de Registros source and collects the
five-digit casilla tags AEAT embeds in the field text. AEAT annotates
every casilla field of a Diseño workbook with its number in square
brackets (e.g. `Liquidación III - ... - Base imponible [00552]`); the
new `_CASILLA_TAG_RE` regex extracts those tags.

For a `multi_segment` modelo the workbook sheet name is carried as each
casilla's `segmento`, so a number reused across two record segments
yields two distinct `(segmento, number)` identity pairs — the exact M200
shape where casilla `00562` appears in both the `DP200014` Liquidación
segment and an ECPN segment. For a single-segment modelo `segmento` is
left unset and the bare number alone identifies the casilla, matching
the bare-number registry behaviour.

A frozen `DerivedManifestCasilla` dataclass carries one derived
`(segmento, number)` pair; the helper `_sheet_casilla_numbers` collects
the tags of one record-design sheet in field order. The tool is strictly
off-load-path: it parses the multi-megabyte Diseño corpus and is called
only by manifest-authoring scripts and the drift re-verification test,
never by the registry loader. Both public symbols are re-exported from
the registry package `__init__.py`.

## Tests

Smoke-verified against the M200 2024 corpus Diseño xlsx: multi-segment
derivation yields 5459 `(segmento, number)` pairs across 71 sheets, and
the `DP200014` Liquidación segment carries 55 casillas including the
cuota-chain numbers `00552` and `00562`. `ruff check` on both touched
files passes clean. Dedicated drift re-verification tests land in
`P03.S11`.

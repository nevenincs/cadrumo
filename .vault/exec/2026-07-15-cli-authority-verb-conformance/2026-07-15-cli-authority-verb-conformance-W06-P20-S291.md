---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S291'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S291 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Route the filing export-field overlap predicate onto the registry copy, the only admissible canonical home across that layer boundary and ## Scope

- `src/cadrumo/application/filing/_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Route the filing export-field overlap predicate onto the registry copy, the only admissible canonical home across that layer boundary

## Scope

- `src/cadrumo/application/filing/_export.py`

## Description

- Confirmed the private `_export_fields_overlap` in `application/filing/_export.py` was byte-identical to the registry's private `_export_fields_overlap` in `domain/calculations/registry/_export.py`: a fixed-width byte-range overlap test over two `ExportFieldDefinition` records.
- Chose the registry copy as canonical: `ExportFieldDefinition` is a registry schema type, and the consumer is the `application/filing` layer, so `application > domain` is the only admissible import direction (the registry cannot import the application layer).
- Promoted the registry copy to public `export_fields_overlap`, updated its internal caller, and re-exported it through the registry package facade (`registry/__init__.py` import block and `__all__`); the registry's own test now imports the public name.
- Deleted the application copy and routed the `filing/_export.py` overlapping-field grouping caller through `from ...domain.calculations.registry import export_fields_overlap`.

## Outcome

The fixed-width export-field overlap predicate now has one owner, `export_fields_overlap` in the registry package, consumed by the registry's own layout derivation and by the filing export layer through the registry public facade.

Canonical-home rationale (per the layered contract): the predicate operates on the registry `ExportFieldDefinition` schema and the only legal cross-layer direction is `application/filing -> domain/registry`, so the registry is the sole admissible home; homing it in the application layer would have forced the registry (the other consumer) to import upward, which the layered contract forbids.

Discovery basis: the mandated `vaultspec-rag` code index was measured untrustworthy (mid-rebuild, control probes missed), so a structural AST duplicate scan supplied the cluster and every claim was re-established by exact `rg` search and by reading both bodies.

Verification (HEAD `70a333bdcace23f25f67ae889991fc90fdc7056d`):

- `uv run --no-sync ruff check` / `ruff format --check` clean on all four touched files (import-sort auto-fix applied to the registry test after the rename).
- `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_export.py src/cadrumo/application/filing/tests/test_export.py src/cadrumo/application/filing/tests/test_export_layout_refusals.py -n0 -q` — 69 collected, `69 passed in 44.67s`.
- Mutation proof: inverting the surviving canonical (`return not (...)`) reddened both layers simultaneously — `8 failed, 61 passed`, with 3 registry overlap tests and 4 filing export tests failing — proving both genuinely consume the single registry function; restored to `69 passed`.

## Notes

The initial `sed` rename over the registry test also stripped the underscore inside the `test_export_fields_overlap_*` function names (`test_` + `_export_fields_overlap` collapsed to `testexport_fields_overlap`); caught immediately by reading the sed result and repaired with a targeted second `sed` restoring the `def test_export_fields_overlap` prefix, verified by grep and green collection. No production code was affected.

---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:6b2f895e128da873a77f299a24d998508666eff83904b1f51554ee089dbf97df'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `source-casilla-integration` audit: `s168 inventory projection review`

## Scope

Independent review of S168 inventory projection arithmetic, complete acquisition-cost authority, closing-authority composition, continuity and conflict provenance, deterministic ordering, and fail-closed result construction.

## Findings

### s168-inventory-projection-review | high | resolved projection provenance could be forged

Cross-field validation now binds the selected authority to its authoritative value and requires physical identity, value, fingerprint, and retained conflict state to agree with the projection and its canonical resolution. Divergent physical values require a conflict under either authority selection.

### s168-inventory-projection-review | high | resolved nonzero acquisition totals lacked proof identity

A nonzero complete acquisition total now requires at least one acquisition fingerprint, and fingerprints must be unique because movement identity is part of the canonical acquisition fingerprint. Empty and duplicate mutations refuse.

### s168-inventory-projection-review | medium | resolved incidental movement order changed provenance

Purchase totals and fingerprints now use the same canonical movement ordering as valuation. Reordered semantically identical ledgers produce identical acquisition provenance.

### s168-inventory-projection-review | high | resolved closing decision acquired a rival mutable value field

The accidental physical-value field was removed from `InventoryClosingAuthorityDecision`; physical values remain exclusively in the canonical observation, resolution, and projection provenance contracts.

### s168-inventory-projection-review | pass | final complete inventory projection is coherent

Final review reported zero critical, high, medium, or low findings. Fifty-two inventory-domain tests, Ruff, the type checker, and diff hygiene were clean.

## Recommendations

Proceed to the inventory resolver using this projection as the sole source of 0177, 0181, and 0182. Do not reconstruct acquisition, authority, continuity, or sign-split semantics in the registry layer.


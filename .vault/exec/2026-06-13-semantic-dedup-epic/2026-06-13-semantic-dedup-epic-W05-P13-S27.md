---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S27'
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
     The S27 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The C1-1b Sweep the inline hashlib.sha256().hexdigest() full-digest tail onto sha256_hex and ## Scope

- `src/aeat/core/hashing.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# C1-1b Sweep the inline hashlib.sha256().hexdigest() full-digest tail onto sha256_hex

## Scope

- `src/aeat/core/hashing.py`

## Description

- Enumerated the full inline tail with `rg` (RAG under-returns it): 79
  `hashlib.sha256(x).hexdigest()` one-shot full-digest sites across 60 modules
  spanning domain, application, adapters, core, and entrypoints.
- Wrote a one-shot AST-aware transformer (regex with one-level nested-paren
  handling) to replace each site with `sha256_hex(x)`, insert the correct
  relative `core.hashing` import per module (verified all targets carry
  `from __future__`), and drop `import hashlib` where no other hashlib use
  remained. Ran `ruff check --fix` (import order) and `ruff format` on the
  owned set only.
- Excluded by design: 8 truncated `[:n]` digests and the incremental
  `hashlib.sha256()` accumulators (different output / streaming shape).

## Outcome

Committed as `a2b8ff256`, tagged `relocation:sha256_hex` (60 files,
+173/-151). Full-tree `pytest --collect-only` clean (15,467 collected); ruff
clean on the owned set; ~920 digest/roundtrip/identity tests across every
touched package green.

## Notes

The broad test sweep caught a name collision: `corpus_manifest.build_corpus_manifest`
binds a local `sha256_hex` (from its own `_hash_file`), so the bulk-inserted
plain import shadowed the function and `sha256_hex(body)` raised
`TypeError: 'str' object is not callable`. Fixed by importing the canonical
aliased as `_sha256_hex` in that module and calling the alias at the two sites.
The `ruff --fix` pass ran over all working-tree-dirty files but only the owned
60 had fixable (import-order) findings; the commit used an explicit
owned-file pathspec so no peer WIP was staged. Scratch transformer removed.

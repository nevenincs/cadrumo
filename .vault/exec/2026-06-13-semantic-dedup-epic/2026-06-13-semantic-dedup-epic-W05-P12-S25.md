---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S25'
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
     The S25 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The C1-2 Delegate the five chunked-read SHA-256 loops to core.hashing.hash_file/sha256_file and ## Scope

- `src/aeat/core/hashing.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# C1-2 Delegate the five chunked-read SHA-256 loops to core.hashing.hash_file/sha256_file

## Scope

- `src/aeat/core/hashing.py`

## Description

- Re-verified the five candidate sites at HEAD and applied the substitutability
  pre-filter: three delegate cleanly, two were excluded as not substitutable.
- `inbound/pdf/_utils.sha256_file` delegates to `core.hashing.sha256_file`,
  wrapping `OSError` in `PdfModeloImportError`; removed the inline `hashlib`
  loop and the now-unused chunk-size constant.
- `registry/_sources._source_file_fingerprint` uses `hash_file` (kept the
  lru_cache key and the `(length, hex)` return order).
- `sanitizer/_pipeline._digest_source` delegates the `Path` branch to
  `hash_file` and the `bytes` branch to `sha256_hex`.

## Outcome

Committed as `c72f2e8fd`, tagged `relocation:hash_file`. Ruff clean; 466
pdf/sanitizer/registry tests green, including the source-path redaction-hygiene
test.

## Notes

A first pass raised the sanitizer error with `from exc`, which broke
`TestSourceParseErrorHygiene` (it asserts `__cause__` AND `__context__` are
None so the OSError's filesystem path never leaks). Restored the original
deferred-raise pattern (capture the error in the except, raise after the block)
so both slots stay clean. Two sites excluded with rationale: `manuals/_fetch`
hashes the httpx stream while writing (never re-reads the file) and
`attachment.put_file` interleaves the digest with byte accumulation under a
typed read error — neither is a clean `hash_file` delegation.

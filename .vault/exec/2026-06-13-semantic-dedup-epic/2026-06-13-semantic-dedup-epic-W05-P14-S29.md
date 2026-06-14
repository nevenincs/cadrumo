---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S29'
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
     The S29 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The C5-1 Extract a shared content-hash verify kernel and route the two storage backends through it and ## Scope

- `src/aeat/adapters/outbound/storage/_local.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# C5-1 Extract a shared content-hash verify kernel and route the two storage backends through it

## Scope

- `src/aeat/adapters/outbound/storage/_local.py`

## Description

- Re-read both verify sites (post C1-1b sweep, which had already moved them to
  `sha256_hex`) and confirmed the genuine gating divergence: local verifies any
  non-empty stored digest; Drive only a full 64-char digest.
- Created `outbound/storage/_integrity.py` with `strip_sha256_prefix` and
  `verify_content_hash(actual_hash, stored_hash, *, message, context,
  translated_message, require_full_digest=False)`.
- Routed both backends through it: local with `require_full_digest=False`
  (still computing `actual_hash` itself, reused to stamp the written sidecar),
  Drive with `require_full_digest=True`.
- Regenerated the API stub for the new module (`apidocs scaffold`).

## Outcome

Committed as the C5-1 commit, tagged `relocation:verify_content_hash` (5 files
incl. 2 doc stubs). Ruff clean; 69 outbound-storage tests green; apidocs
`scaffold --check` conformant.

## Notes

The kernel takes a precomputed `actual_hash` rather than the payload because
the local backend reuses the digest after the check (to build the
`content_hash` sidecar value); the `require_full_digest` flag preserves the two
backends' distinct verification policies exactly. The local mismatch message
was trimmed (the stored/actual values remain in `context`) to satisfy the
120-char line limit; no test asserts that message string.

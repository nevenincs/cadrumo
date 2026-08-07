---
tags:
  - '#exec'
  - '#declarations-register-pagination'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:d2b218e6cc362e7c8f121c5e760bbf30d0e24c6428005fe721c56b2f0788a396'
step_id: 'S01'
related:
  - "[[2026-08-07-declarations-register-pagination-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace declarations-register-pagination with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-08-07-declarations-register-pagination-plan placeholders are machine-filled by
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
     The Add a typed DeclaracionesRegisterPage carrying rendered rows, a parsed declared_total (int or None, None only when no pager label is present) and a derived truncated property to _parse_listbox, reusing a pager-label regex analogous to the pinning test's fixture-independent extraction. Gate: a new unit test asserts declared_total is parsed correctly off the existing synthetic paginated fixture and is None off the real single-row fixture and ## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_declarations_listbox.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a typed DeclaracionesRegisterPage carrying rendered rows, a parsed declared_total (int or None, None only when no pager label is present) and a derived truncated property to _parse_listbox, reusing a pager-label regex analogous to the pinning test's fixture-independent extraction. Gate: a new unit test asserts declared_total is parsed correctly off the existing synthetic paginated fixture and is None off the real single-row fixture

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_declarations_listbox.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

## Verification

<!-- Where the evidence is that something RAN, quote the instrument rather than
     summarising it: the invocation, then the runner's verbatim summary line.

         uv run --no-sync pytest <paths> -m integration -n 0
         15 passed in 10.35s

     The invocation shows the selection (marker expression and path scope); the
     summary line shows what that selection produced. A run that selected nothing
     exits zero and reads as green, so a paraphrase such as "the tests pass"
     discards exactly the part a reader needs. Quote, do not summarise. -->

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

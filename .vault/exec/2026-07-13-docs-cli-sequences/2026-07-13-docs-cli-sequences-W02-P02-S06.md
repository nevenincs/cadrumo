---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S06'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-cli-sequences with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Enforce the sequence-result contract at parse time, refusing a sequence with zero, multiple, or non-terminal @result frames and ## Scope

- `dev/docs/sequences/_parser.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Enforce the sequence-result contract at parse time, refusing a sequence with zero, multiple, or non-terminal @result frames

## Scope

- `dev/docs/sequences/_parser.py`

## Description

- Implement `parse_sequence` in `_parser.py` as the public entry that runs the line pass over the body and then enforces the structural contract before constructing the validated `ParsedSequence`.
- Enforce the sequence-result contract of ADR ruling D4: refuse a sequence with zero, multiple, or non-terminal `@result` frames, and refuse a `@result` frame that carries no `@expect` assertion.
- Require the `:verify:` directive option (a non-empty singular imperative sentence) and validate the sequence id and any `:seed:` name as kebab-case identifiers.
- Resolve `{name}` placeholders against captures produced by strictly-earlier frames only, and refuse duplicate `@capture` names, accumulating each violation.

## Outcome

A structurally invalid directive raises one `SequenceParseError` enumerating every fault at once. A capture cannot feed its own frame's argv, exactly one terminal asserted `@result` frame is guaranteed, and the required verification narration is present.

## Notes

Placeholder availability is intentionally exclusive of the owning frame: a capture is produced by that frame's output, so it can only thread into later frames.

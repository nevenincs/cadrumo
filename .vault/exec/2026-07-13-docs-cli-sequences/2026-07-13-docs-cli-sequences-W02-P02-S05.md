---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S05'
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
     The S05 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Implement the frame-line parser for the cli-sequence grammar (visible aeat frames, @setup, @result, @capture, @expect, and {name} interpolation) and ## Scope

- `dev/docs/sequences/_parser.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement the frame-line parser for the cli-sequence grammar (visible aeat frames, @setup, @result, @capture, @expect, and {name} interpolation)

## Scope

- `dev/docs/sequences/_parser.py`

## Description

- Add the typed sequence schema in `_schema.py`: a `FrameKind` StrEnum (command/setup/result), and strict-frozen pydantic models `CaptureBinding`, `ExpectAssertion`, `SequenceFrame`, and `ParsedSequence`, all under the central `STRICT_FROZEN_CONFIG`.
- Add `_errors.py` with a self-contained `SequenceEngineError` and an accumulating `SequenceParseError` that enumerates every problem under the sequence id.
- Implement the low-level `parse_frame_lines` pass in `_parser.py`: classify each non-blank body line, shell-decompose command frames into argv via `shlex`, and attach `@capture` and `@expect` annotations to the preceding frame.
- Decompose per-frame argv leading with the `aeat` executable, extract and validate `{name}` placeholder tokens, and parse `@expect` right-hand values as JSON literals typed by kind.

## Outcome

The frame grammar of ADR ruling D1 parses into typed, immutable frames. Every grammar violation is recorded as an instructive problem naming its source and line number rather than aborting the pass. The typed surface is exposed through the package facade for downstream phases.

## Notes

No incidents. The frame builder is a mutable dataclass during the pass, converted to the frozen `SequenceFrame` at finalisation.

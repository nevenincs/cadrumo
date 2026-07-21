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

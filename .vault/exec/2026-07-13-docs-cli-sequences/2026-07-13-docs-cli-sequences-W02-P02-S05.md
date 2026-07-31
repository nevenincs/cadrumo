---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:9a09a8dec1ae1e6b357235ab1f0bff3a410c43723b1da9655dacc874e37f9467'
step_id: 'S05'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

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

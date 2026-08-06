---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:1054b26337021789c70c7a36f05f3c650e077861b40bd15e86cced9a89bf401f'
step_id: 'S10'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Implement @capture value threading that parses a frame's JSON envelope, binds the json-path, and interpolates {name} into later frames

## Scope

- `dev/docs/sequences/_runner.py`

## Description

- Parse each executed frame's output as a JSON envelope document (verbatim, pre-mask) and record it on the frame's transcript row; non-JSON output records as a text frame with no envelope.
- Resolve every `@capture` binding by walking its dotted/bracketed json-path over the parsed envelope; bind the value into the run's capture map so strictly later frames can consume it.
- Interpolate bound captures into later frames' `{name}` placeholder argv tokens before execution, rendering strings verbatim, booleans as JSON `true`/`false`, and numbers via their canonical text.
- Refuse instructively, naming the frame's source and line: a capturing frame whose output is not JSON (with the `--format json` remedy and an output head), a json-path missing from the envelope (with the envelope's top-level keys), and a capture resolving to null or a non-scalar (which cannot interpolate into a command line).
- Record resolved captures per frame as typed `CapturedValue` rows and expose the whole-run view via `SequenceTranscript.captures`.

## Outcome

A real id produced at build time (a work-unit id, a calculation-revision id) threads from the frame that minted it into every later frame's command line, exactly as the ADR ruling D1 worked example authors it. Capture failures stop the run at the offending frame with an actionable message rather than cascading garbage into later frames.

## Notes

No incidents. Capture evaluation is scalar-only by design: an object or array capture has no faithful argv text, so the refusal is a contract, not a limitation to lift.

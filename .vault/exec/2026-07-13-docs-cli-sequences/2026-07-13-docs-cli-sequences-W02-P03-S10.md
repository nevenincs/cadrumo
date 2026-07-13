---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S10'
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
     The S10 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Implement @capture value threading that parses a frame's JSON envelope, binds the json-path, and interpolates {name} into later frames and ## Scope

- `dev/docs/sequences/_runner.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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

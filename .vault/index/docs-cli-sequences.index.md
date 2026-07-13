---
generated: true
tags:
  - '#index'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - '[[2026-07-13-docs-cli-sequences-W01-P01-S01]]'
  - '[[2026-07-13-docs-cli-sequences-W01-P01-S02]]'
  - '[[2026-07-13-docs-cli-sequences-W01-P01-S03]]'
  - '[[2026-07-13-docs-cli-sequences-W01-P01-S04]]'
  - '[[2026-07-13-docs-cli-sequences-W02-P02-S05]]'
  - '[[2026-07-13-docs-cli-sequences-W02-P02-S06]]'
  - '[[2026-07-13-docs-cli-sequences-W02-P02-S07]]'
  - '[[2026-07-13-docs-cli-sequences-W02-P02-S08]]'
  - '[[2026-07-13-docs-cli-sequences-W02-P03-S09]]'
  - '[[2026-07-13-docs-cli-sequences-W02-P03-S10]]'
  - '[[2026-07-13-docs-cli-sequences-W02-P03-S11]]'
  - '[[2026-07-13-docs-cli-sequences-W02-P04-S12]]'
  - '[[2026-07-13-docs-cli-sequences-W02-P04-S13]]'
  - '[[2026-07-13-docs-cli-sequences-W02-P04-S14]]'
  - '[[2026-07-13-docs-cli-sequences-W02-P04-S15]]'
  - '[[2026-07-13-docs-cli-sequences-W02-P05-S16]]'
  - '[[2026-07-13-docs-cli-sequences-W02-P05-S17]]'
  - '[[2026-07-13-docs-cli-sequences-W02-P05-S18]]'
  - '[[2026-07-13-docs-cli-sequences-W02-P05-S19]]'
  - '[[2026-07-13-docs-cli-sequences-W03-P06-S20]]'
  - '[[2026-07-13-docs-cli-sequences-W03-P06-S21]]'
  - '[[2026-07-13-docs-cli-sequences-W03-P07-S22]]'
  - '[[2026-07-13-docs-cli-sequences-W03-P07-S23]]'
  - '[[2026-07-13-docs-cli-sequences-W03-P07-S24]]'
  - '[[2026-07-13-docs-cli-sequences-W03-P07-S25]]'
  - '[[2026-07-13-docs-cli-sequences-adr]]'
  - '[[2026-07-13-docs-cli-sequences-plan]]'
  - '[[2026-07-13-docs-cli-sequences-research]]'
---

# `docs-cli-sequences` feature index

Auto-generated index of all documents tagged with `#docs-cli-sequences`.

## Documents

### adr

- `2026-07-13-docs-cli-sequences-adr` - `docs-cli-sequences` adr: `interactive executed CLI sequence docs` | (**status:** `accepted`)

### exec

- `2026-07-13-docs-cli-sequences-W01-P01-S01` - Re-anchor the invocation-token regex on the real aeat executable so documented aeat invocations are scanned again, fixing the rename-sweep vacuity
- `2026-07-13-docs-cli-sequences-W01-P01-S02` - Re-run the repaired conformance gate and capture the full inventory of latent verb-path and option-name defects it now surfaces
- `2026-07-13-docs-cli-sequences-W01-P01-S03` - Triage and fix every documented-command defect the repaired gate surfaces across the how-to, tutorial, explanation, and runbook doc pages
- `2026-07-13-docs-cli-sequences-W01-P01-S04` - Verify the full documented-command conformance gate passes green and pytest collect-only is clean
- `2026-07-13-docs-cli-sequences-W02-P02-S05` - Implement the frame-line parser for the cli-sequence grammar (visible aeat frames, @setup, @result, @capture, @expect, and {name} interpolation)
- `2026-07-13-docs-cli-sequences-W02-P02-S06` - Enforce the sequence-result contract at parse time, refusing a sequence with zero, multiple, or non-terminal @result frames
- `2026-07-13-docs-cli-sequences-W02-P02-S07` - Implement :seed: recipe inlining that prepends a shared @setup fragment from the named seed file before the sequence's own frames
- `2026-07-13-docs-cli-sequences-W02-P02-S08` - Write parser unit tests covering grammar acceptance, every refusal case, capture and expect binding, and seed inlining
- `2026-07-13-docs-cli-sequences-W02-P03-S09` - Implement the per-sequence sandbox runner (fresh isolated_profile_storage_root, frozen_clock, injected profile_id, English output, live tests off, invoke_cached_cli per frame)
- `2026-07-13-docs-cli-sequences-W02-P03-S10` - Implement @capture value threading that parses a frame's JSON envelope, binds the json-path, and interpolates {name} into later frames
- `2026-07-13-docs-cli-sequences-W02-P03-S11` - Write runner tests driving a real create-calculate-verify chain hermetically and asserting captured values thread through subsequent frames
- `2026-07-13-docs-cli-sequences-W02-P04-S12` - Implement the golden reader and writer for committed light per-sequence JSON (resolved argv, exit code, verbatim captured envelope or text, capture bindings)
- `2026-07-13-docs-cli-sequences-W02-P04-S13` - Implement JSON-frame comparison delegating to the observability primitives with exactly the central GOLDEN_MASK_FIELDS, refusing any per-sequence mask extension
- `2026-07-13-docs-cli-sequences-W02-P04-S14` - Implement text-frame exact comparison with declared narrow normalisation, per-frame exit-code assertion, and @expect semantic evaluation against live output
- `2026-07-13-docs-cli-sequences-W02-P04-S15` - Write comparison tests covering JSON match and mismatch diagnostics, text match, exit-code failure, and @expect pass and fail
- `2026-07-13-docs-cli-sequences-W02-P05-S16` - Implement the refresh CLI mode that re-executes sequences in the sandbox and rewrites the golden files, scoped by --page or --sequence
- `2026-07-13-docs-cli-sequences-W02-P05-S17` - Implement the check CLI mode that fails with the page, sequence id, frame index, argv, differing_paths or unified diff, and the exact refresh invocation
- `2026-07-13-docs-cli-sequences-W02-P05-S18` - Implement the executor-level anti-tautology proof that executes one representative sequence twice and asserts the pre-mask differing paths equal the central mask set exactly
- `2026-07-13-docs-cli-sequences-W02-P05-S19` - Verify the whole engine test suite (parser, runner, comparison, CLI, anti-tautology) passes green with no mocks or skips
- `2026-07-13-docs-cli-sequences-W03-P06-S20` - Implement the cli-tree.json projection generator reusing the English-pinned reference environment, lazy-import forcing, and per-option param extraction
- `2026-07-13-docs-cli-sequences-W03-P06-S21` - Write projection tests and make a documented command path absent from the projection a hard build failure
- `2026-07-13-docs-cli-sequences-W03-P07-S22` - Implement the Python tokeniser against the materialised Click tree, classifying executable, verb path, option, option value, positional value, and interpolated placeholder tokens with a command-path key on each verb token
- `2026-07-13-docs-cli-sequences-W03-P07-S23` - Register the backtick-fenced cli-sequence MyST directive rendering server-side static frames in document order plus one inline application/json payload per sequence
- `2026-07-13-docs-cli-sequences-W03-P07-S24` - Teach the conformance gate the sequence grammar (strip @setup and @result sigils, treat {name} as a positional placeholder) and add the enrolled-page no-plain-executable-fence tier
- `2026-07-13-docs-cli-sequences-W03-P07-S25` - Write directive and tokeniser tests asserting the payload shape, token classification, and no-JS static frame HTML

### plan

- `2026-07-13-docs-cli-sequences-plan` - `docs-cli-sequences` plan

### research

- `2026-07-13-docs-cli-sequences-research` - `docs-cli-sequences` research: `interactive executed CLI sequence docs`

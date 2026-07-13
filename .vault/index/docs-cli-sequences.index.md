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

### plan

- `2026-07-13-docs-cli-sequences-plan` - `docs-cli-sequences` plan

### research

- `2026-07-13-docs-cli-sequences-research` - `docs-cli-sequences` research: `interactive executed CLI sequence docs`

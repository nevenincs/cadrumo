---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S12'
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
     The S12 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Implement the golden reader and writer for committed light per-sequence JSON (resolved argv, exit code, verbatim captured envelope or text, capture bindings) and ## Scope

- `dev/docs/sequences/_golden_store.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement the golden reader and writer for committed light per-sequence JSON (resolved argv, exit code, verbatim captured envelope or text, capture bindings)

## Scope

- `dev/docs/sequences/_golden_store.py`

## Description

- Define the strict-frozen golden schema in `dev/docs/sequences/_golden_store.py`: `SequenceGolden` with a versioned envelope and per-frame `GoldenFrame` rows carrying kind, argv as executed, exit code, exactly one of a verbatim pre-mask JSON envelope or normalised text (model-validated exclusive-or), and the capture bindings.
- Implement `golden_path` addressing under the committed goldens tree (per-page docname directory, one JSON file per sequence id) with a validated traversal-safe page identifier, plus `default_goldens_root` anchored to the repository like the seeds and fixtures roots.
- Implement `write_golden` as the only sanctioned writer: canonical key-sorted two-space-indent UTF-8 JSON with a trailing newline, so review diffs are stable and minimal.
- Implement `read_golden` with instructive refusals: a missing golden names the exact refresh invocation that creates it; a schema-invalid golden names the never-hand-edited rule and the regeneration remedy.
- Implement the declared narrow text normalisation `normalise_text_output` (per-run sandbox paths to stable tokens in native and POSIX slash forms, centrally-masked surrogate-id values to the mask sentinel) and `masked_envelope_values`, which collects those id values from the transcript's own envelopes.

## Outcome

Goldens are light, review-diffable committed data per the Pagefind commit boundary: JSON envelopes stored raw pre-mask (mask applied only at compare, so the artifact never bakes the mask in), text stored normalised (the writer run's sandbox paths are unknowable to any later reader, so run-independence must be baked at write time — the one deliberate asymmetry from the JSON policy, documented in the module).

## Notes

No incidents. The `golden_schema_version` literal gives the format a forward version field for the compatibility-lifecycle rules without any legacy branch.

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

The `golden_schema_version` literal gives the format a forward version field for the compatibility-lifecycle rules without any legacy branch.

Review absorption (review-p03 MEDIUM, landed with this phase): the runner previously recorded only the combined output stream, dropping the split stderr; a refusal's error document — which shares the envelope spine per the CLI notices standard — was un-golden-able. The runner now records stdout and stderr separately, resolves the envelope stdout-first-then-stderr with a typed `envelope_source`, and the golden frame covers both streams (`text` for non-envelope stdout, `stderr_text` for non-envelope stderr, empty streams as null); the comparison asserts the envelope's carrying stream and diffs each non-envelope stream independently. Proven by a real stderr-error-document sequence in the runner and comparison test suites. The two review LOW findings also landed: the live-AEAT scan skips option-value tokens (no `--file pull-history.csv` false refusal), and the transient registry-race retry is skipped entirely under CI.

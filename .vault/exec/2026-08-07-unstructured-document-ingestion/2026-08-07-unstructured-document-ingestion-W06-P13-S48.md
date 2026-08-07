---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:cc56b3be2b271896602b96f809b511ab929f63d457baef3e30c76873537974dd'
step_id: 'S48'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Author the typed per-role model catalogue declaring runtime id, memory requirement, SPDX licence with an explicit commercial-use flag verified against publisher text, and measured-baseline reference, gated by catalogue validation tests

## Scope

- `src/cadrumo/core`

## Description

- Add `_model_catalogue.py` as the single home for the local-model deployment configuration.
- Declare the closed axes as StrEnums: model role, licence-verification provenance, deployment licence posture, and the selection-advisory reasons.
- Declare `ModelLicence` carrying an SPDX identifier, an explicit commercial-use flag, the verification kind, and the publisher URL and quote that were read.
- Declare `ModelCandidate` carrying runtime id, the roles it serves, the publisher-stated memory requirement, the context window, its licence, and an optional measured-baseline reference.
- Populate the catalogue with six candidates and declare the per-role defaults.
- Add a hardware-tier band and its classifier beside the existing accelerator axes.
- Promote every new symbol to the package facade in the same change.

## Outcome

The catalogue is the one place that answers what may be selected and under whose licence. Three declarations carry the weight.

The memory requirement is the publisher's stated weight size, so the figure a contention check compares is traceable to a published number rather than to an estimate. The context window is the capability floor and the reason selection is bounded from below: a model whose window cannot hold the configured request window is not a cheaper option but an unusable one, so it is excluded on capability rather than ranked below on quality.

The licence is the declaration that did not previously exist anywhere in the tree. The commercial-use flag is declared explicitly rather than derived from the identifier, because the derivation is the step that goes wrong: a reader who knows a permissive licence permits commercial use will assume a publisher-specific reference does too, and one catalogued licence says "FOR NON-COMMERCIAL PURPOSES ONLY". Every claim was read from publisher text at authoring, never from recall — permissive claims from the publishers' model-card licence fields, the restrictive one from the publisher's own licence file — and each entry ships the URL and the quote so the claim can be re-checked by opening one link.

The type refuses a commercial-use claim that no publisher text backs, so an unverified licence is a refusal input by construction rather than by convention, and the failure direction of a future hand-edit is a build error rather than a silent legal claim.

The measured-baseline reference is empty on every candidate. No corpus measurement exists anywhere in the tree yet, and an invented reference would have been worse than an absent one.

## Verification

Gate authored at `src/cadrumo/core/tests/test_model_catalogue.py`.

    uv run --no-sync pytest -p no:randomly -o addopts="-p no:cacheprovider" -m unit src/cadrumo/core/tests/test_model_catalogue.py src/cadrumo/application/tests/test_model_selection.py src/cadrumo/application/tests/test_provisioning_hardware_contention.py src/cadrumo/application/tests/test_provisioning.py src/cadrumo/llm/tests/test_local_text_reader_wiring.py -q
    87 passed in 31.75s

Two fixture anchors keep the gate from passing vacuously: one asserts the catalogue still describes a commercial-use-barred candidate, so the licence gate stays capable of failing, and one asserts a candidate is still excluded by the configured context window, so the capability floor stays an exercised filter rather than a dormant one.

## Notes

The catalogue deliberately retains both former defaults rather than deleting them. A retained candidate records why it stopped being the default, and lets a genuinely non-commercial deployment still name it.

One entry required care that generalises: most sizes of one model family are permissively licensed and exactly two are not, and the shipped default was one of the two. A family-level licence assumption would have been wrong for the specific weights in use, which is why the flag is per candidate and read per candidate.

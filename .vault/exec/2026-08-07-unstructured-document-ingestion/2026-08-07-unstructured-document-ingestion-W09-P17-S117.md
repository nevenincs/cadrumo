---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:87f2d1b624e58d829d305bd55b5b65a0e97532db8705ce8c99b358c5848a97c9'
step_id: 'S117'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Bring the transcriber identity shape under the provenance-stamp grammar

## Scope

- `src/cadrumo/application/ledger`

## Description

- Give the transcriber identity a required `transport` axis using the one canonical vocabulary.
- Return the vision reader's identity name to the model it names, and the text-layer identity to a stated on-host transport.
- Keep the transport in the transcription cache key, where it already was by way of the name.
- Extend the stamp-singularity gate to the identity shape, and strengthen the identity's own refusal case.
- Promote the text-layer identity helper to the package facade, since the gate consumes it.

## Outcome

The row offered two resolutions — the identity carries a real stamp, or the survey learns to read it — and neither was taken, deliberately. A stamp records how a VALUE was reached; an identity records who produced a TRANSCRIPTION and is folded into a cache key. Conflating them would have been a new duplication in the name of removing one. Teaching the survey a second grammar would have re-introduced upstairs exactly what the constructor row deleted from five producers. Recording the transport as data means nothing parses anything, which is strictly better than either.

The reason the transport was being recorded at all was right and is preserved verbatim in the code: a transcription produced off-host is a durable artefact a withdrawal must enumerate, and a model identifier names its vendor only to a reader who already knows the catalogue. Only the place was wrong, and it was wrong twice — the field is contracted to say which reader produced the text and explicitly not to carry a coarse label, and the resulting shape was a third grammar no parser knew.

The axis is required rather than defaulted, which is the sharper case of the rule the other axes already followed: a defaulted transport would let an off-host read claim it never left the machine, and that claim is what a withdrawal rests on. The requirement immediately surfaced fourteen construction sites across nine test modules, every one of which had to state where its read ran.

The cache key keeps the transport. That is preservation rather than a new decision — it was already folded in through the name — and it earns the place because the same model served off-host is a different trust context, not merely a different route.

## Verification

    uv run --no-sync pytest -n0 -p no:cacheprovider src/cadrumo/application/ledger src/cadrumo/llm src/cadrumo/entrypoints/cli/tests/test_evidence_extract_consent_verb.py -q -m ""
    1 failed, 1263 passed, 15 warnings in 524.20s (0:08:44)

The single failure is the live-network Anthropic round trip, which needs a credential and a network this run has neither of.

Two mutations, applied from a plugin outside the repository, both reddening the new gate and its behavioural counterpart:

    fold_the_transport_back_into_the_name   2 failed, 11 passed
    hardcode_the_transport_local            2 failed, 11 passed

The second is the one worth keeping. Folding the transport back into a name is the literal regression; hardcoding it on-host is the same defect wearing the shape of correct code, and it is the one a reviewer would pass over. The gate carries an explicit control refusing to run unless at least one identity under test is genuinely off-host, so a suite that quietly lost its cloud case would fail rather than pass over nothing.

    uv run --no-sync lint-imports
    Contracts: 5 kept, 1 broken.

The broken contract names two peer edges: a new `application.live._deudas` module reaching adapters, and a private-submodule import in a grounded-reading test.

## Notes

The identity gate asserts over CONSTRUCTED identities rather than over source text. A reader assembling the name from parts would satisfy any source-level pattern while storing the same smuggled shape, and what matters is the value that reaches storage.

One file was reported as contended and turned out not to be. The apply-cached drive was built for it and then reversed once a comparison against HEAD showed the working tree was identical — the earlier modified flag was transient. Reversing and taking the simple path was cheaper than carrying an index-only change, and the check that settled it was working-tree-versus-HEAD rather than the status flag.

The index carried a peer's staged vault document throughout, so no bare commit was available at any point; every commit used an explicit pathspec.

A dead constant left by the change was removed rather than left behind.

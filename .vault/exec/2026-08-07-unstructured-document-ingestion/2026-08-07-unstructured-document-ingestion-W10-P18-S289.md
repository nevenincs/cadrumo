---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:8241ce5a4840bea53d6f1ed26f9271841c589d834dc6e12d313c24fee92ce342'
step_id: 'S289'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Amend the release-asset-transport ADR to record that D4 no-callers premise is false for the download surface, since D3 in the same record preserves the operator locally-minted evidence release which has no backing run and stays a release download - and three live modules import download_release_assets, list_releases, resolve_gh, run_gh_with_retry, EvidenceLane and evidence_tag - so the record contradicts itself and a reader executing D4 literally deletes what D3 requires, which is what broke HEAD

## Scope

- `.vault/adr/2026-08-07-release-asset-transport-public-repo-artifact-return-adr.md`

## Description

- Record a dated amendment on the accepted transport ADR stating that D4's no-callers premise is false for the download surface, naming the three consumers that hold it.
- Cite D3 in the same record as the evidence, since it preserves the operator's locally-minted evidence release as a release download.
- Leave D4 itself unrewritten, because it was true when written for three of its four surfaces and its ruling on those stands.
- Record what the contradiction did rather than only that it existed: the collection break, and the seven unrelated failures it masked.
- Note the remedy that keeps both decisions true, and the property gate that now enforces D4's ruling on the collector by construction.

## Outcome

The amendment is narrow on purpose. A blanket correction of D4 would retire a ruling that is correct for seal, verify and manifest emission, and would weaken the one part of it that most needs to hold: the garbage collector was removed because it could delete releases, and that is not in question. Only the download surface is exempted from the no-callers claim.

The evidence for the exemption comes from inside the same record, which is what makes it adjudicable rather than a matter of preference. D3 keeps the operator's locally-minted evidence release unchanged on the stated ground that it has no backing run and therefore stays a release download. A release download requires a release-download transport, so the surface D4 describes as callerless had a caller at the moment the record was accepted, and three modules have held it throughout.

Two general lessons are recorded on the ADR rather than in this Step, because they outlive the feature. A ruling whose stated premise is contradicted by a sibling decision in the same document does not bind on the contradicted point — and that contradiction is invisible to any reader holding one decision at a time, which is how it survived review. And a decision that rules on code is not self-executing: the implementing rows must be opened in the same action as the decision, or the record reads as in force while the tree carries the shape the decision rejected. Here the ruling was executed for the workflow and the rename and never for the consumers, and the gap was not a slow drift but an outright collection failure.

## Verification

The amendment is a record change and carries no runtime gate of its own. What it asserts about the tree was measured on the code side and is quoted there: the three named consumers import the surface, the retired surfaces have no consumers, and the property gate refusing a release-deleting capability is green with its controls proven.

    uv run --no-sync pytest dev/ --collect-only -q -p no:cacheprovider
    1978/2697 tests collected (719 deselected), exit 0

## Notes

The amendment was appended to the accepted record rather than opened as a superseding ADR. Superseding would have retired a decision that is correct in almost all of its scope, and would have made the reader chase two documents to learn that one clause of one decision was wrong.

The claim that a reader executing D4 literally would delete what D3 requires is not hypothetical and is not offered as a risk. It is what happened, and the tree was in that state when this work started.

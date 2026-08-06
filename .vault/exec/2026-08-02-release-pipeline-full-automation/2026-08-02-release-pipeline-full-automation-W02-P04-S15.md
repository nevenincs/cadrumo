---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:587a2a449774e75fe8ae1975ddb8055930c40de37737ba22c6b20a9bbecbc696'
step_id: 'S15'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Publish the sealed candidate record through the existing evidence-release draft transport under a release-candidate tag keyed on the smoke run id, so the durable state lives outside every running job and outside the working tree exactly as the evidence rows already do, gate: uv run --no-sync pytest dev/release/tests/test_release_candidate.py -q passes over the writer and reader against injected release payloads, with live draft creation flagged non-local and CI-only

## Scope

- `dev/release/release_candidate.py`
- `dev/packaging/evidence_release.py`
- `dev/release/tests/test_release_candidate.py`

## Description

- Promote four shared gh primitives on the evidence transport to public names: `resolve_gh`, `run_gh_with_retry`, `list_releases`, and `download_release_assets`, updating every internal call site and adding them to the module's `__all__`.
- Add `publish_candidate`, which seals the record onto its own draft release, creating on first seal and clobbering its asset on a re-seal.
- Add `fetch_candidate`, which validates the tag namespace BEFORE downloading, and `list_sealed_candidate_tags`.
- Add four transport tests driving a real recording `gh` stub that captures argv.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_release_candidate.py -q` reports 16 passed, the full `dev/release/tests` suite 236 passed, and the two evidence-transport suites 71 passed, so the promotion broke no existing consumer.

Live draft creation against the real forge is CI-only and is not exercised here; what is exercised locally is the exact argv the transport builds, which is where its correctness actually lives.

## Notes

The promotion was a precondition rather than a follow-up. The gh primitives the candidate transport needs were private to the packaging module, and reaching into another package's private names is barred; the sanctioned alternatives are to promote a genuinely shared primitive or to build a narrower public API. These four are shared primitives by any reading - a gh subprocess boundary with retry, a paginated release lister, an asset downloader, an executable resolver - and the draft-release mechanism now carries both evidence rows and sealed candidates, so promoting keeps ONE gh boundary instead of a second copy in the release package. They were renamed to public names rather than aliased, since a re-export bridge would be the compatibility shim this project bars.

Two behaviours are worth naming because both are silent when wrong. `publish_candidate` checks for an existing draft and uploads with clobber rather than creating a second one: two drafts sharing a tag make which assets a later download resolves undefined, which is the hazard the evidence transport already refuses on, and a promoter reading the wrong draft would promote the wrong cohort. And `fetch_candidate` validates the tag namespace before it downloads anything, because a promoter that downloaded first would treat any draft's asset as a candidate.

The tests use a real recording stub that logs its argv, not a mock. The transport's correctness IS the argv it builds - draft, clobber, repository pin, asset name - so a substituted call would assert the substitution rather than the behaviour.

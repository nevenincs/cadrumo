---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:6d83506a25c7eca79c8ff9b9ced881a7c0179300b9a329cc6aca6052a3bb4779'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
---

# `aeat-export-fragment-generator-authority` audit: `S15 candidate mutation gate review`

## Scope

Reviewed the S15 candidate mutation gate against the accepted generator-authority
decision and execution scope. The review covered candidate validation, provenance
verification, atomic cutover ordering, and the real filesystem cases mutating
offset, length, source anchor, target revision, and generated-file bytes. It also
checked that the check and publication surfaces add no direct-revision or
single-file reader route.

## Findings

### mutation-gates | low | PASS — no findings

All five real-filesystem mutation cases fail before the publication journal,
rollback sibling, or live export can change. Offset and length drift fail on
loader-semantic equality; source-anchor drift fails on rendered field derivations;
target-revision drift fails against the current generation authorities; and a
generated-file byte mutation fails the output-file digest check. Each case leaves
the live export and non-export revision authority byte-identical, leaves the
candidate present for diagnosis, and creates no rollback sibling.

The publication path does not read, merge, copy, or fall back to an older export
tree. The check path imports no publication or direct-revision/single-file reader
surface, and its linked-ancestor guard refuses redirected candidate writes before
rendering. No legacy surface was reintroduced by S15.

Evidence: bounded code and ADR RAG searches completed; the focused mutation test
passed 5/5; the complete publication module passed 14/14; and the related check,
validation, and legacy-surface tests passed 5/5.

## Recommendations

Retain this gate as a required pre-cutover and release proof. Wave 4 must preserve
the structural no-legacy guards while deleting the superseded loader compatibility
surfaces; no S15 code correction is required.

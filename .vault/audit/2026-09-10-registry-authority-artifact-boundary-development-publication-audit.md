---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:6e7c92c81f6474c78cd12c1f154cf15361160424e7884b1d3c1159d65a60455b'
related: []
---



# `registry-authority-artifact-boundary` audit: `development publication`

## Scope

The W01.P02.S02 development publisher and its behavioral gate were audited before the artifact becomes a runtime dependency.

## Findings

### development-publication | high | Publisher is not connected to a development release workflow

The new publication function has no caller beyond its unit test. Existing pipeline commands continue to publish generated export-tree files without producing a signed authority artifact, so the intended development-to-runtime handoff is not reachable.

### development-publication | high | Publication receipt omits source-evidence stability

The publisher validates registry and source roots, but its post-validation identity comparison covers only the registry tree. A source-evidence change during validation can therefore escape the pre-replacement check. The publication receipt must bind all validation inputs before atomic replacement.

### development-publication | medium | Successful staged publication lacks a workflow gate

The current test proves a missing candidate preserves old artifact bytes but does not demonstrate a valid staged candidate publishing an authority which a trusted reader can consume.

### development-publication | medium | Artifact identity does not represent all validated inputs

The published identity is a registry-tree digest rather than a complete validation-input receipt, weakening its meaning as the identity of the candidate that was validated.

### development-publication | low | Concurrent publisher ownership is unspecified

Atomic replacement prevents torn output but does not define which candidate wins if two release publishers target one artifact simultaneously.

## Recommendations

- Wire artifact publication into one explicit development pipeline command with injected destination and signing key.
- Introduce and verify a complete post-validation candidate receipt spanning registry and source evidence.
- Exercise successful staged publication and source-change refusal through real publisher inputs.
- State or enforce a single-publisher precondition for a shared artifact destination.

### development-publication | medium | Source receipt has metadata-only evidence entries

The corrected receipt includes source evidence but its collector records path, size, and nanosecond timestamp rather than contents. A replacement preserving those metadata can evade the post-validation comparison, so the receipt does not yet prove the exact source candidate that was validated.

### development-publication | low | Mutation gates couple to error wording

The source and registry mutation tests assert exception message fragments in addition to refusal and previous-artifact preservation. The behavioral contract is the refusal and unchanged publication, not a specific implementation phrase.

- Digest source-evidence bytes in the publication receipt and prove same-size, restored-timestamp replacement is refused.
- Remove error-message matching from behavioral mutation gates.

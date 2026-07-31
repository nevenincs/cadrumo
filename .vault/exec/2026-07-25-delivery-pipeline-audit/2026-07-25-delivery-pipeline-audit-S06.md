---
tags:
  - '#exec'
  - '#delivery-pipeline-audit'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:9f891c94bca6dba6b6c690d6517dc4a99a95350ca589d98f87a72868091522c3'
step_id: 'S06'
related:
  - "[[2026-07-25-delivery-pipeline-audit-plan]]"
---

# D3 gate, assert the Development Status classifier is identical across the three pyprojects so the next posture change is a one-fact edit plus gate rather than a silent fork

## Scope

- `dev/packaging/tests/`

## Description

Verify the cross-distribution development-status conformance gate, and prove it discriminates.

- Confirm the gate is tracked and reads all three cohort pyprojects by parsing TOML, not by pattern-matching text.
- Confirm it collects and passes at HEAD with a non-zero collected count, since a bare path invocation that selects nothing exits green and is not a verification.
- Build a negative control from the genuine pre-change bytes and run the real gate source against it.

## Outcome

Complete at HEAD. The gate is `dev/packaging/tests/test_classifier_parity.py`, landed with the posture change in commit `ce792a1565` and reflowed by a later tree-wide formatting pass.

It parses each pyproject with `tomllib` and reads the classifier list as structured data rather than grepping the file, asserts each distribution declares exactly one development-status classifier, and asserts the set of values across the three collapses to one. Its failure message enumerates each distribution with its declared value.

Positive run at HEAD: one test collected, one passed.

Negative control: the three pyprojects as they stood immediately before the posture change were reconstructed into an isolated tree from committed history, giving the genuine divergent state of a Beta root against two Alpha companions. The gate source was copied unmodified into that tree at the same relative depth so its repo-root derivation resolved there, and run. It failed, naming both companions at Alpha against the root at Beta. The gate discriminates.

This matters because the ruling's whole value is that the next posture change is a one-fact edit plus a gate rather than a silent fork, and a gate that cannot fail delivers none of that.

## Notes

The negative control was run against real historical bytes and the unmodified gate source in a scratch tree, with no mock, no monkeypatch, and no edit to any tracked file. Reconstructing the divergence in place would have meant mutating a tracked pyproject in a worktree carrying live concurrent work, which was avoided.

The control was deliberately not skipped on the grounds that the assertion looks obviously correct by reading. This repository has shipped gates that were green while measuring nothing, so a passing assertion is not evidence that a gate has teeth.

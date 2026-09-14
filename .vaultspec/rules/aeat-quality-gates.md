---
name: aeat-quality-gates
---

# AEAT quality gates

## What a gate must prove

- A gate exercises the real authority path, parser, compiler, resolver, calculation, or serializer whose contract it names. Mocking the production behavior under test is not acceptance evidence.
- Test outcomes and invariants, not implementation trivia, frozen corpus counts, campaign milestones, or the mere presence of a string.
- Positive tests prove the supported path. Negative tests prove malformed, ambiguous, unsupported, stale, and incomplete inputs fail closed at the owning boundary.
- Round-trip tests compare canonical typed meaning, including absence, zero, precision, ordering, provenance, and revision identity; lossy equality is not sufficient.

## Detector teeth

A gate that protects a declaration or generated relationship must demonstrate that a representative defect is detected. Use an isolated fixture, temporary registry tree, or explicit test input; do not monkeypatch production modules globally or mutate the contributor's working tree. The defect proof and the normal path must both pass in the same test suite.

## Repository enumeration

### Rule

Never use Git commands, the Git index, tracked-file lists, commit history, or branch state as the authority for a quality, completeness, parity, or packaging gate. Derive the expected set in-process from the current source tree and its checked-in inclusion, exclusion, catalogue, or schema policy.

### Why

The `2026-09-14-evidence-corpus-registry-evidence-normalization-audit` exposed a wheel-parity gate whose answer changed with staging state: deleted source paths remained expected and new valid paths appeared unexpected. Version-control metadata describes a proposed commit, not the product contract, and makes an otherwise valid worktree fail for reasons unrelated to correctness.

### How

- Good: enumerate current files with `dev.source_tree.repository_files`, then project them through the packaging or corpus policy and compare that set with the built artifact.
- Good: use Git in an explicitly named release workflow to inspect or publish a commit, where commit identity itself is the subject—not as a test oracle.
- Bad: define expected wheel members, registry completeness, source coverage, or corpus parity with `git ls-files`, `git status`, or a commit diff.

## Layered validation

- Keep focused unit and contract tests near the owning boundary, integration tests at real handoffs, and end-to-end checks for user-visible flows.
- Overlapping gates are justified when they catch distinct failure modes. Remove duplicate tests that assert the same implementation detail without adding detection value.
- Generated-reference checks compare generated output with the committed artifact through the owning generator.
- A change is not complete while it introduces a new lint, type, test, schema, or Vaultspec failure. Pre-existing unrelated failures are reported separately with evidence.
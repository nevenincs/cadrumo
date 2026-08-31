# AEAT quality gates

## What a gate must prove

- A gate exercises the real authority path, parser, compiler, resolver, calculation, or serializer whose contract it names. Mocking the production behavior under test is not acceptance evidence.
- Test outcomes and invariants, not implementation trivia, frozen corpus counts, campaign milestones, or the mere presence of a string.
- Positive tests prove the supported path. Negative tests prove malformed, ambiguous, unsupported, stale, and incomplete inputs fail closed at the owning boundary.
- Round-trip tests compare canonical typed meaning, including absence, zero, precision, ordering, provenance, and revision identity; lossy equality is not sufficient.

## Detector teeth

A gate that protects a declaration or generated relationship must demonstrate that a representative defect is detected. Use an isolated fixture, temporary registry tree, or explicit test input; do not monkeypatch production modules globally or mutate the contributor's working tree. The defect proof and the normal path must both pass in the same test suite.

## Layered validation

- Keep focused unit and contract tests near the owning boundary, integration tests at real handoffs, and end-to-end checks for user-visible flows.
- Overlapping gates are justified when they catch distinct failure modes. Remove duplicate tests that assert the same implementation detail without adding detection value.
- Generated-reference checks compare generated output with the committed artifact through the owning generator.
- A change is not complete while it introduces a new lint, type, test, schema, or Vaultspec failure. Pre-existing unrelated failures are reported separately with evidence.

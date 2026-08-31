---
name: no-silent-under-declaration
trigger: always_on
---

# No silent under-declaration

## Preserve uncertainty

- Missing, unknown, unsupported, deferred, advisory, not applicable, and proven zero are distinct states. Do not collapse any of them to zero, empty text, false, or a complete total.
- A filing-grade result is complete only when every legally required input and dependency is present, validated, and covered by authority for the active filing context.
- Suspicious zeros or absences at filing-bound fields produce a structured advisory or refusal with modelo, revision, field, source family, and reason. Diagnostics must reach the user-facing handoff.
- A local calculation or prefill is not an official AEAT value. Label its origin and authority honestly.

## Coverage and suppression

- Compare independent sources where the product has both an external value and an engine-derived value. A disagreement remains visible until resolved; neither side silently wins.
- Suppression is explicit, narrowly keyed, classified, and reviewable. It must state why the condition is safe or non-applicable and must not use a broad model, prefix, or count-based exemption.
- New declarations are covered by semantic gates that detect unclassified filing-bound gaps. Frozen corpus counts and baseline-only ratchets do not prove completeness.
- Advisory capability cannot be promoted to filing grade by a UI, exporter, or downstream consumer.

## Tests

Exercise genuine zero, missing input, unsupported authority, deferred source, mismatch, valid suppression, invalid suppression, and end-to-end diagnostic propagation through the real registry and calculation paths.

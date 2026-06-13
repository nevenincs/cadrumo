---
name: no-tautological-calculation-tests
trigger: always_on
---

# No tautological calculation tests

Treat tautological calculation tests as forbidden. Do not assert registry runtime output against numbers hand-computed from the same registry formula under test.

Use external authority for expected calculation values. Prefer AEAT workbooks, BOE or AEAT worked examples, registry-authoritative fixtures, or live AEAT oracle replay.

When no external numeric authority exists, test graph wiring, validation errors, provenance, schema shape, or primitive evaluator contracts. Do not manufacture Decimal expectations from synthetic inputs.

Before accepting a calculation test, ask whether the test would fail if the registry formula were wrong against AEAT. If not, remove or rewrite it.

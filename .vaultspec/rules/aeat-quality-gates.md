---
name: aeat-quality-gates
trigger: always_on
---

# AEAT quality gates

Write real-behavior tests. Do not use fakes, mocks, stubs, monkeypatches, skipped tests, xfail markers, or tautological assertions to make gates pass.

For calculation tests, derive expected values from AEAT workbooks, BOE or AEAT examples, registry-authoritative fixtures, or live oracle replay. Do not hand-compute the same formula that the registry declares.

Test structure, graph wiring, validation errors, and provenance when no external numeric oracle exists. Do not assert arbitrary Decimal outputs produced only by the test author.

Reject duplicated symbols, shadowed responsibilities, misplaced code, import cycles, dead code, and cross-package private imports. Run structural audits at milestone and cluster gates.

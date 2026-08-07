# No tautological calculation tests

Treat tautological calculation tests as forbidden. Do not assert registry runtime
output against numbers hand-computed from the same registry formula under test.

Use external authority for expected values: AEAT workbooks, BOE or AEAT worked
examples, registry-authoritative fixtures, or live AEAT oracle replay.

When no external numeric authority exists, test graph wiring, validation errors,
provenance, schema shape, or primitive evaluator contracts. Do not manufacture
`Decimal` expectations from synthetic inputs.

**Before accepting a calculation test, ask whether it would fail if the registry
formula were wrong against AEAT.** If not, remove or rewrite it.

Two adjacent traps: deriving an expected value dynamically from the code under
test is still tautological, whether the literal is typed in or fetched at
runtime; and a test that encodes a current defect as the contract is worse than
no test — correct it rather than working around it.

Companions: `verification-grounding-needs-oracle-evidence`, `aeat-quality-gates`.

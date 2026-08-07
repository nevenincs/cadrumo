---
name: aeat-quality-gates
trigger: always_on
---

# AEAT quality gates, roundtrips and fixtures

## Real behaviour, external authority

Write real-behavior tests. Do not use fakes, mocks, stubs, monkeypatches, skipped
tests, xfail markers, or tautological assertions to make gates pass.

**No tautological calculation tests.** Do not assert registry runtime output
against numbers hand-computed from the same registry formula under test. Use
external authority: AEAT workbooks, BOE or AEAT worked examples,
registry-authoritative fixtures, or live oracle replay. When no external numeric
authority exists, test graph wiring, validation errors, provenance, schema shape
or primitive evaluator contracts — do not manufacture `Decimal` expectations from
synthetic inputs.

**Before accepting a calculation test, ask whether it would fail if the registry
formula were wrong against AEAT.** If not, remove or rewrite it. Deriving the
expected value dynamically from the code under test is still tautological,
whether the literal is typed in or fetched at runtime. And a test that encodes a
current defect as the contract is worse than no test — correct it rather than
working around it.

Reject duplicated symbols, shadowed responsibilities, misplaced code, import
cycles, dead code and cross-package private imports. Run structural audits at
milestone and cluster gates.

## Roundtrip every persistence boundary

Write strict roundtrip tests for every **persistence boundary**, not just every
pydantic model: encrypted SQL via `SecureObjectRepository`, TOML manifests, JSON
envelopes, fichero-BOE bytes, worksheet export and pull, and any CLI emit path
that flows over the wire.

**Use real adapters, not mocks** — real key provider, real SQLite engine, real
serializer. A mock returning what the test expects is the canonical
false-positive signal.

**Assert strict pydantic equality across the boundary.** Build a populated model,
push it through the real cycle, load on the other side, assert `model_a ==
model_b`. Partial-field comparison and string-shape checks are insufficient.

**Populate every defaultable field with a non-default value** — a
save-drops-field / load-re-defaults-field regression is invisible when the fixture
uses the default.

**Provide an anti-tautology proof for each boundary class.** Save a record, mutate
the on-disk payload to delete a field, reload, and assert either a
`ValidationError` is raised or strict inequality is surfaced. If this ever passes
with the boundary broken, every roundtrip in the suite is tautological.

**Never use xfail, skip or stub**, and never wrap a roundtrip in try/except to
hide failures. **Carry every roundtrip in the production test path** — tests in
scratch are ephemeral.

## A gate is unproven until it bites

Break the production code on purpose, confirm the gate reds, restore. Prefer a
runtime monkeypatch from **outside** the repo over an edit to a tracked file:
nothing under `src` changes, so a peer's sweep cannot commit the mutation and a
crashed run leaves no residue. The edit form is only unavoidable when the fix is
not yet in the code; announce before opening that window.

An anti-tautology proof over synthetic input is necessary but not sufficient — it
cannot catch a detector correct on synthetic input that never reaches the real
site.

**Allowlists are where the judgement moves**, so require every entry to state its
reason and make stale entries fail. Key exemptions by `(path, enclosing
function)`, never by line number. For any gate pinning registry ids, add a
fixture-anchor test asserting those ids still carry the property they are named
for, or a rename makes the module pass vacuously.

**Never hardcode an exact count as a pass condition.** Gate on the property, not
the tally: a module count or import-site ceiling encodes a moment, trains
everyone to update the constant, and then detects nothing.

**This repo's gates overlap**, so satisfying one can violate another. Verify a fix
against both before committing. The tell is oscillation — if fix A reds gate B
and fix B reds gate A, neither is right and a third shape is needed. Never
resolve it by hiding the construct from one gate's matcher.

## Fixture provenance is declared, never allowlisted

Every test-fixture PDF under a modelo subdirectory MUST declare its provenance
(`real_corpus` or `synthetic_generated`) in its `.json` sidecar. Provenance gates
MUST read that declaration and cross-check it against physical evidence — the PDF
`/Producer` DocInfo — and MUST NOT hardcode per-fixture exception allowlists in
test source.

A gate inferring provenance from a single proxy assumes every fixture in a modelo
directory shares one provenance. That is false: a real sanitised AEAT anchor can
live alongside synthetic specimens for the same modelo. Patching the resulting red
gate with an allowlist re-introduces the honor-system list the gate exists to
remove. A mis-stamped sidecar still reds the gate via the cross-check, so honesty
survives without an allowlist.

## How

- **Good:** a real corpus anchor in an otherwise-synthetic pool stamps
  `provenance = real_corpus`; the gate reads it and confirms the PDF carries no
  generator signature. No test source changes.
- **Bad:** exempting a fixture by adding `(modelo_id, filename)` to an allowlist
  constant; or shipping a gated fixture with no `provenance` field.

Source: ADR `2026-06-01-verification-fixture-roles-adr`. Companions:
`no-silent-under-declaration`, `aeat-worktree-safety` (triaging a red tree-wide
gate).

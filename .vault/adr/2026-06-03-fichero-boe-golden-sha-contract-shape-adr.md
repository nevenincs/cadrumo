---
tags:
  - '#adr'
  - '#fichero-boe-golden-sha-contract-shape'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-synthetic-fixture-primitive-encoding-discipline-adr]]"
  - "[[2026-06-03-m303-synthetic-generator-primitive-spec-adr]]"
  - '[[2026-06-04-fichero-boe-golden-sha-contract-shape-research]]'
---

# `fichero-boe-golden-sha-contract-shape` adr: golden SHA stays as the byte-identity lock; DR303 conformance is a sibling assertion | (**status:** `accepted`)

## Authoring note

Authored via Write tool. Adjudicates #149 P07.S25 architectural
question: is `_M303_GOLDEN_SHA256` the right contract for the
fichero-BOE roundtrip test, or should the test re-shape to verify
byte-shape conformance against the AEAT Diseño de Registros DR303
directly?

## Problem statement

`test_fichero_boe_roundtrip.py` asserts the M303 BOE-fichero export
SHA256 equals a hardcoded constant `_M303_GOLDEN_SHA256`. The plan
step #149 P07.S25 question is whether to recompute the constant
against the current registry state (the simple coder task that coder1-2
silently dropped this session) OR to re-shape the test so it verifies
byte-shape conformance against AEAT's Diseño de Registros DR303
directly (Orden EHA/3786/2008, 2024 revision), decoupling the test
from a single layout hash.

The two options optimise for different contracts:

- **Golden SHA**: byte-identity lock. Any change to the 303.toml export
  layout — offset, length, encoding, sign flag, padding — flips the
  hash and forces the developer to consciously re-ground against
  DR303 and update the constant.
- **DR303 byte-shape conformance**: structural lock. The test parses
  the produced bytes against the published DR303 record layout
  (record types DP30300, DP30301, ..., field offsets, lengths,
  data types) and asserts each field is positioned and shaped
  per AEAT spec.

## Forces in tension

- **AEAT changes the spec periodically.** Orden EHA/3786/2008 has been
  modificada by Orden HAC/819/2024 and earlier; the 2024 revision
  (updated 2024-11-29) is the current binding. A DR303-conformance
  test against the current spec passes today; when AEAT next
  publishes a modification, the test passes against the new spec
  before the code adapts to it, masking the drift.
- **Layout regressions are silent.** A byte-offset typo in 303.toml
  that shifts a field by one position is structurally still
  "field-shaped" — DR303 conformance via cursory inspection passes,
  but the offset is wrong. Byte-identity (golden SHA) catches this.
- **Anti-tautology.** A test that derives its expected bytes from the
  same registry that produces them is a tautology — the test
  consumes its own output. A test whose expectation is anchored in
  an external authority (AEAT DR303, BOE-published) is non-tautological.
- **Maintenance cost.** Golden SHA: one constant per modelo per revision;
  flips whenever the layout intentionally changes; requires re-grounding
  the developer at flip time. DR303 conformance: one parser per record
  layout, kept in sync with the AEAT-published DR; requires maintaining
  the parser as DR evolves.
- **Audit trail.** Golden SHA: each flip is one commit ("re-ground
  against DR303 2024 revision; new SHA = XYZ"). DR303 conformance:
  each AEAT revision is one commit on the conformance parser.

## Decision: Golden SHA stays; add DR303 conformance as a sibling assertion

The right contract is **both**, not either:

### 1. `_M303_GOLDEN_SHA256` stays as the byte-identity lock

The constant remains in `test_fichero_boe_roundtrip.py`. Any change
to `303.toml` that alters offset, length, encoding, padding, sign
flag, or character set flips the hash. The test failure message
already directs the developer to re-ground against DR303 before
updating the constant. That re-grounding step IS the anti-tautology
discipline — the developer must read the AEAT-published DR before
flipping the hash.

Recompute the constant against the current registry state per the
#149 P07.S25 plan step. The recompute is the simple coder task
that was originally dispatched; it does not change the contract
shape.

### 2. DR303 byte-shape conformance becomes a sibling assertion

In the same test (or a sibling test in the same module), add
DR303-grounded structural assertions on the produced bytes:

- Assert `payload[0:11]` decodes as the DP30300 declarante-NIF field
  (positions 1-11 in DR303, 1-indexed).
- Assert `payload[12:15]` decodes as `"303"` (modelo code, positions
  13-15 in DR303).
- Assert `payload[15:19]` decodes as the ejercicio (positions
  16-19).
- Assert each subsequent record starts at the cumulative offset
  matching DR303 record lengths (DP30300 = 328, DP30301 = 1581,
  DP30302 = 1706, etc — the comment block in the test already
  enumerates these).
- Assert the file ends with the expected trailer record at the
  expected offset.

These structural assertions catch the "field-shaped but wrong
offset" failure mode that golden SHA also catches, but they fail
with a *diagnostic* message ("DP30301 expected at offset 328, found
at 327") rather than the SHA's opaque "hash mismatch" message.

### 3. The two assertions serve different roles

- **Golden SHA** is the *change-control gate*: it forces a conscious
  re-grounding step whenever the layout changes. The developer
  cannot accidentally land a layout change; the test reds and the
  failure message points at DR303.

- **DR303 conformance** is the *diagnostic surface*: when the SHA
  flips, the conformance assertions tell the developer *which* field
  drifted and where. Without conformance, the SHA flip is a
  guess-and-check exercise.

Both gates together produce: "the bytes are AEAT-conformant AND match
the registry's intentional layout decision". Either gate alone is
weaker.

## Why not re-shape away from golden SHA entirely

The original P07.S25 framing posed "decouple SHA from layout" as the
better contract. Rejected because:

1. **Decoupling loses the change-control gate.** Without the SHA, an
   accidental byte-padding change that still validates against DR303
   (because the padding character happens to fall within the allowed
   character set) ships silently. The byte-identity lock is the
   gate that catches "structurally valid but unintended" drift.

2. **The "DR303 conformance only" approach drifts when AEAT changes
   the spec.** A conformance parser pinned to the 2024 revision
   passes against a 2026 revision that adds a new optional field
   — the bytes-with-new-field conform to the new spec, the parser
   updates to match, and no gate ever flagged the spec change.
   Golden SHA forces the developer to consciously re-ground at
   spec-change time.

3. **DR303 conformance is not strictly stronger than SHA.** A bytes
   stream that produces the correct hash necessarily conforms to
   DR303 if the registry's previous SHA was DR303-conformant. The
   SHA implicitly carries the DR303 contract; the conformance
   assertions make that contract explicit and diagnosable.

## Why not "golden SHA only" status quo

The status quo (golden SHA, no conformance assertions) has two
weaknesses:

1. **Opaque failures.** When the SHA flips, the developer has no
   diagnostic — they must manually compare bytes to DR303 to find
   the drift.

2. **No DR303-anchored contract in the test source.** A reader who
   inspects the test cannot tell *which* DR303 fields the bytes
   are supposed to satisfy. The contract lives implicitly in the
   registry; the test only locks bytes-as-produced.

Adding conformance assertions makes the contract self-documenting
and self-diagnosing at the test-source layer.

## Consequences

- #149 P07.S25 splits into two work items:
  1. Recompute `_M303_GOLDEN_SHA256` against the current registry
     state (the original coder task; ~5 minutes, single commit).
  2. Add DR303 conformance assertions as a sibling test (separate
     commit; ~50-100 LOC; grounded by reading DR303 2024 revision
     PDF and writing one assertion per record-type start offset
     plus key field positions).
- The pattern generalises to other modelos with BOE-fichero exports:
  M111, M115, M123, M130, M180, M193, M210, M232, M349, M390, M714,
  M720, M840 each get the same "golden SHA + DR conformance"
  treatment. Per-modelo authoring happens on the same cadence as the
  modelo's verification-chain hardening.
- The `aeat-roundtrip-discipline` rule's "Provide an anti-tautology
  proof test for each boundary class" obligation is satisfied for the
  fichero-BOE boundary by the conformance-assertion sibling — it is
  the non-tautological lock that survives a fixture-regeneration of
  the SHA-bearing payload.

## Out of scope

- Implementation of the DR303 conformance parser (deferred to the
  follow-up coder task; spec landed here).
- Cross-modelo rollout (covered by the per-modelo verification-
  chain hardening cadence).
- Real-AEAT-server roundtrip (forbidden by
  `aeat-safety-legal-gates` rule; the conformance test stays
  byte-level only).

## Status

Accepted. P07.S25 is reshaped into the two-commit sequence above.
The original coder dispatch (recompute the constant) remains valid
and can land first; the conformance sibling lands as a follow-up
that closes the diagnostic gap.

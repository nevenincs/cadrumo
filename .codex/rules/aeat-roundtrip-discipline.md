---
name: aeat-roundtrip-discipline
trigger: always_on
---

# AEAT roundtrip discipline

Write strict roundtrip tests for every **persistence boundary**, not just every
pydantic model. Each of these gets its own dedicated roundtrip test: encrypted
SQL via `SecureObjectRepository`, TOML manifests, JSON envelopes, fichero-BOE
bytes, worksheet export and pull, and any CLI emit path that flows over the wire.

**Use real adapters, not mocks** — real key provider, real SQLite engine, real
serializer. A mock returning what the test expects is the canonical
false-positive signal.

**Assert strict pydantic equality across the boundary.** Build a populated model
on one side, push it through the real cycle, load on the other, assert
`model_a == model_b`. Partial-field comparison and string-shape checks are
insufficient.

**Populate every defaultable field with a non-default value.** A
save-drops-field / load-re-defaults-field regression is invisible when the
fixture uses the default. Set a non-default lifecycle stage, populate optional
metadata triples, fill empty containers with real entries, and rely on typed
model validators that reject partial defaults.

**Provide an anti-tautology proof for each boundary class.** Save a record,
mutate the on-disk payload to delete a field, reload, and assert either a
`ValidationError` is raised or strict inequality is surfaced. If this test ever
passes with the boundary broken, every roundtrip in the suite is tautological.

**Never use xfail, skip, or stub.** A test documented as expected-to-fail is a
process leak. Write tests that fail loudly today when the structural work is
incomplete and pass cleanly when it lands, and never wrap a roundtrip in
try/except to hide failures.

**Carry every roundtrip in the production test path.** Tests in scratch are
ephemeral; tests under `src/cadrumo/.../test_*.py` participate in the CI gate.
Move ad-hoc verification scripts into the durable test surface as soon as they
prove a contract worth defending.

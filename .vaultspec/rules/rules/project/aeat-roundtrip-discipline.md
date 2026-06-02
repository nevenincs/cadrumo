---
name: aeat-roundtrip-discipline
---

# AEAT roundtrip discipline

Write strict roundtrip tests for every persistence boundary, not just every pydantic model. Give each of these its own dedicated roundtrip test: encrypted SQL via SecureObjectRepository, TOML manifests, JSON envelopes, fichero-BOE bytes, worksheet export/pull, and any CLI emit path that flows over the wire.

Use real adapters, not mocks. Real EphemeralMasterKeyProvider, real SQLite engine, real serializer/deserializer. A mock that returns what the test expects is the canonical false-positive signal.

Assert strict pydantic equality across the boundary. Build a populated model on one side, push through the real cycle, load on the other side, assert model_a == model_b. Mocks, partial-field comparison, and string-shape checks are insufficient.

Populate every defaultable field with a non-default value in roundtrip fixtures. A save-drops-field / load-re-defaults-field regression is invisible when the test fixture uses the default. Set state to a non-default lifecycle stage, populate optional metadata triples, fill empty containers with real entries. Rely on typed model_validators that reject partial defaults to lock the boundary.

Provide an anti-tautology proof test for each boundary class. Save a record, mutate the on-disk payload to delete a field, reload, and assert either ValidationError raised or strict inequality surfaced. If this test ever passes with the boundary broken, every roundtrip in the suite is tautological.

Never use xfail, skip, or stub. A test that passes today but is documented as expected-to-fail is a process leak. Write tests that fail loudly today when the structural work is incomplete, and pass cleanly when it lands. Do not wrap roundtrips in try/except to hide failures.

Carry every roundtrip in the production test path. Tests in scratch/ are ephemeral; tests under src/aeat/.../test_*.py participate in the CI gate. Move ad-hoc verification scripts into the durable test surface as soon as they prove a contract worth defending.
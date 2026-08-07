---
name: fixture-provenance-declared-in-sidecar
trigger: always_on
---

# Fixture provenance is declared in the sidecar, never allowlisted

Every test-fixture PDF under a modelo subdirectory MUST declare its provenance
(`real_corpus` or `synthetic_generated`) in its `.json` sidecar. Provenance gates
MUST read that declaration and cross-check it against physical evidence — the PDF
`/Producer` DocInfo — and MUST NOT hardcode per-fixture exception allowlists in
test source.

A gate that infers provenance from a single proxy assumes every fixture in a
modelo directory shares one provenance. That is false: a real sanitised AEAT
parser-fidelity anchor can live alongside synthetic formula-verification
specimens for the same modelo. Patching the resulting red gate with a hardcoded
allowlist re-introduces the honor-system list the gate exists to remove.

Provenance is data the sidecar already half-encoded — real specimens carry
redaction metadata, synthetic ones carry formula ground truth — so the fixture
declares it and the gate validates the declaration. A mis-stamped sidecar still
reds the gate via the cross-check, so honesty survives without an allowlist.

## How

- **Good:** a real corpus anchor in an otherwise-synthetic pool stamps
  `provenance = real_corpus`; the gate reads it and confirms the PDF carries no
  generator signature. No test source changes.
- **Good:** a mis-stamp reds the gate via the `/Producer` cross-check — the
  sidecar is trusted but verified.
- **Bad:** exempting a fixture by adding `(modelo_id, filename)` to an allowlist
  constant; or shipping a gated fixture with no `provenance` field.

Source: ADR `2026-06-01-verification-fixture-roles-adr`.

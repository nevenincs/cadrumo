---
name: fixture-provenance-declared-in-sidecar
trigger: always_on
---

# Fixture provenance is declared in the sidecar, never allowlisted

## Rule

Every test-fixture PDF under a modelo subdirectory MUST declare its provenance
(`real_corpus` | `synthetic_generated`) in its `.json` sidecar. Provenance gates
MUST read that declaration and cross-check it against physical evidence (the PDF
`/Producer` DocInfo), and MUST NOT hardcode per-fixture exception allowlists in
test source.

## Why

The verification-source honesty gate inferred fixture provenance from a single
proxy (`/Producer`) and assumed every fixture in a modelo directory shared one
provenance. Modelo 390 broke that: a real sanitised AEAT parser-fidelity anchor
(`2021-0A`) lives alongside synthetic formula-verification specimens
(`2022-0A`, `2023-0A`). Campaign step `W06.P16.S37` patched the red gate with a
hardcoded allowlist (`_REAL_CORPUS_ANCHORS_IN_SYNTHETIC_POOLS`) — re-introducing
the honor-system per-fixture list the gate exists to remove. The
`2026-06-01-verification-fixture-roles-adr` decided the durable fix: provenance
is data the sidecar already half-encoded (real specimens carry redaction
metadata, synthetic carry formula ground truth), so the fixture declares it
explicitly and the gate validates the declaration against `/Producer`. A
mis-stamped sidecar still reds the gate via the cross-check, so honesty is
preserved without an allowlist.

## How

- **Good:** a real parser-corpus anchor added to an otherwise-synthetic pool
  stamps `provenance = real_corpus` in its sidecar. The gate reads it and
  confirms the PDF carries no `aeat-test-fixture-generator` signature. No test
  source changes.
- **Good:** the synthetic fixture generator stamps
  `provenance = synthetic_generated`; the gate confirms the generator signature
  is present.
- **Good:** a mis-stamp (claiming `synthetic_generated` on a real PDF) reds the
  gate via the `/Producer` cross-check — the sidecar is trusted but verified.
- **Bad:** a fixture whose provenance differs from its pool's per-modelo tag is
  exempted by adding `(modelo_id, filename)` to an allowlist constant in the
  test module. This is the smell this rule forbids; declare provenance in the
  sidecar instead.
- **Bad:** a gated fixture ships without a `provenance` field in its sidecar.
  The gate fails it: every gated fixture must self-declare.

## Source

ADR `2026-06-01-verification-fixture-roles-adr` (accepted); research
`2026-06-01-verification-fixture-roles-research`; origin campaign step
`W06.P16.S37` of `2026-06-01-semantic-cluster-hardening-plan`.

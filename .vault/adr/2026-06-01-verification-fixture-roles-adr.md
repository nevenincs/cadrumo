---
tags:
  - '#adr'
  - '#verification-fixture-roles'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-06-01-verification-fixture-roles-research]]"
  - "[[2026-06-01-semantic-cluster-hardening-plan]]"
---

# `verification-fixture-roles` adr: `role-aware verification fixtures via sidecar provenance` | (**status:** `accepted`)

## Problem Statement

The verification-source honesty gate asserts that an extraction profile's
per-modelo `verification_source` tag matches the physical provenance of every
fixture PDF under that modelo's fixture directory, inferring provenance from a
single proxy — the `/Producer` DocInfo field. The gate assumes a modelo's
fixtures share one provenance. Modelo 390 violates that: it deliberately hosts a
real sanitised AEAT parser-fidelity anchor (`2021-0A`) alongside two synthetic
formula-verification specimens (`2022-0A`, `2023-0A`). Campaign step
`W06.P16.S37` unblocked the gate with a hardcoded per-fixture allowlist,
`_REAL_CORPUS_ANCHORS_IN_SYNTHETIC_POOLS` — re-introducing the honor-system
per-fixture list the gate exists to eliminate. A parallel hardcoded list,
`_PERIOD_EQUALS_EJERCICIO`, already tracks the same class of per-fixture fact in
the corpus-sidecar roundtrip test. This ADR decides a durable model that makes
fixture provenance explicit data so neither gate needs an allowlist.

## Considerations

- Two orthogonal axes are collapsed onto one per-modelo tag: **provenance**
  (real sanitised AEAT PDF vs `_generate.py`-produced synthetic) and **role**
  (parser-fidelity anchor vs formula-verification specimen). A modelo may host
  both.
- The `.json` sidecar shipped with every fixture already distinguishes the two
  first-hand: real specimens carry redaction provenance (`source_sha256`,
  `real_sha256`, `source_size_bytes`); synthetic specimens carry only
  formula-derived ground truth. The `/Producer` check is a proxy for a fact the
  sidecar already holds.
- Scope today is one mixed modelo (M390); every other modelo is uniformly real
  or uniformly synthetic. The cost of the change is therefore bounded, but the
  honesty guarantee is what is at stake, not breadth.
- Architecture boundary: the registry authority must not learn about the test
  fixture tree, ruling out declaring fixture filenames on
  `ExtractionProfileDefinition`.

## Constraints

- No frontier risk; this is a local schema-and-test change over committed
  fixtures and an existing pydantic sidecar model.
- Depends on the existing fixture-generator and sidecar-writer
  (`_generate.py` / `_write_sidecar`) and the strict registry-load surface; both
  are stable. A sidecar field addition requires a one-time backfill of the
  committed sidecars and must keep the generator deterministic
  (`invariant=True`) so re-generation is a no-op for unchanged fixtures.
- The change must preserve the gate's anti-honor-system property: a sidecar
  claim is only trustworthy if still cross-checked against physical evidence.

## Implementation

A fixture's `.json` sidecar gains an explicit, required `provenance` field with
two values — `real_corpus` and `synthetic_generated` — and a `role` field —
`parser_anchor` and `formula_verification`. `provenance` is the axis the gate
acts on; `role` is descriptive and enables future role-specific assertions
without another schema change.

The verification-source gate stops globbing for a uniform per-modelo provenance.
For each fixture it reads the sidecar's declared `provenance` and asserts it
agrees with the physical `/Producer` evidence: `synthetic_generated` must carry
the generator signature, `real_corpus` must not. The per-modelo
`verification_source` tag remains a profile-level description of the modelo's
formula-verification evidence, but the gate no longer forces every fixture in
the directory to match it, and `_REAL_CORPUS_ANCHORS_IN_SYNTHETIC_POOLS` is
deleted. The sidecar is the single source of truth; `/Producer` is the
defence-in-depth cross-check that keeps the sidecar honest.

The synthetic fixture writer stamps `provenance = synthetic_generated` and the
appropriate `role` automatically; real sanitised specimens are stamped
`real_corpus` / `parser_anchor` at sanitisation time. Existing committed
sidecars are backfilled once. The corpus-sidecar roundtrip test's
`_PERIOD_EQUALS_EJERCICIO` list is left in place as a tracked follow-up: it
encodes a layout fact (absent period label), not provenance, and migrating it
onto sidecar-declared layout metadata is a separable second step.

## Rationale

Option A puts the provenance fact where the data already lives (the sidecar),
removes the new allowlist, and retains the physical-evidence honesty check that
justifies the gate's existence. The research rejected the alternatives: a
role-based directory split relocates the fixture tree and rewrites every
consumer path for one mixed modelo (high churn, no honesty gain); declaring
fixture filenames on the profile couples the registry authority to the test
fixture tree (architecture-boundary violation); and keeping the S37 allowlist
re-introduces the honor-system per-fixture list and leaves the parallel
`_PERIOD_EQUALS_EJERCICIO` list unaddressed.

## Consequences

- The gate becomes per-fixture and provenance-honest without an allowlist; a
  future real anchor in a synthetic pool (or vice versa) is handled by stamping
  its sidecar, not by editing test source.
- One-time cost: a sidecar schema field, a generator/sanitiser stamp, and a
  backfill of committed sidecars. The roundtrip test continues to consume the
  real M390 anchor unchanged.
- Mild risk: the sidecar becomes load-bearing for an honesty gate, so the
  backfill must be audited (a mis-stamped sidecar would pass a mis-tag). The
  `/Producer` cross-check bounds this: a sidecar claiming `synthetic_generated`
  on a real PDF (no signature) still reds the gate.
- Opens a clean path to retire `_PERIOD_EQUALS_EJERCICIO` by moving layout facts
  into the same sidecar, collapsing both per-fixture allowlists onto one model.

## Codification candidates

- **Rule slug:** `fixture-provenance-declared-in-sidecar`.
  **Rule:** Every test-fixture PDF must declare its provenance
  (`real_corpus` | `synthetic_generated`) in its `.json` sidecar; provenance
  gates must read the sidecar and cross-check it against physical evidence,
  never hardcode per-fixture exception allowlists in test source.

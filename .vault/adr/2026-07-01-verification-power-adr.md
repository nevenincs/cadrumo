---
tags:
  - '#adr'
  - '#verification-power'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:04b0c107b0baaccda1ea2ad495e5878e50b308172b4bbf3b1681585c0f4deeab'
related:
  - '[[2026-07-01-verification-power-research]]'
  - '[[2026-07-01-verification-reconcile-when-present-adr]]'
  - '[[2026-07-01-verification-contract-coverage-audit]]'
---

# `verification-power` adr: `verification grounding tier transparency` | (**status:** `accepted`)

## Problem Statement

The modelo verify surface reconciles every enrolled casilla's filed value against
the engine's computed value, but `VerificationVerdict` exposes only `status`,
`discrepancies`, and `coverage` (a presence fraction — did the filing print the
casilla). It cannot distinguish the ~1% of casillas whose engine value is
checked against an independent AEAT-authoritative oracle from the ~99%
reconciled only against the app's own engine (research finding VP2/VP3). A
VERIFIED status therefore reads as uniformly trustworthy when the actual
independent-grounding depth is thin and uneven. This is roadmap item R1: make the
grounding tier a first-class, honest signal on the verdict.

## Considerations

A verification expectation already carries two casilla axes on
`VerificationExpectationDefinition` — `computed_casilla_ids` (coverage-gated) and
`reconcile_when_present_casilla_ids` (value-checked when present, excluded from
coverage). Grounding tier is a third, orthogonal axis: of the casillas a filing
reconciles, WHICH have an independent oracle expected value. Today that signal
exists only implicitly, computed at CI-test time by globbing and JSON-parsing the
Renta WEB Open replay corpus (`test_external_oracle_grounding_enrolled.py`) — an
ad-hoc file read that `aeat-registry-authority-flow` forbids on any production
path. The verdict models are frozen/strict pydantic; any addition must be
additive with safe defaults and must not perturb `status`/`coverage`.

## Considered options

- **A. Loader-time corpus ingestion.** Scan the replay corpus during registry
  load and merge the grounded set into the snapshot. Rejected: couples the
  general loader to one modelo's oracle-corpus format/filenames, does not
  generalise to the R2 (manual worked-examples) or R3 (live-capture) corpora
  without repeated loader edits, and would widen the registry-tree fingerprint's
  cache-invalidation scope for a narrow purpose.
- **B. Runtime corpus read in the verify path.** Have the verify path glob/parse
  the corpus JSON per call. Rejected: a direct `aeat-registry-authority-flow`
  violation (bypasses the loader→snapshot authority), adds filesystem I/O and
  corpus-format coupling to a hot path, and cannot be build-time validated.
- **C (chosen). Declarative registry field.** Add
  `externally_grounded_casilla_ids` to `VerificationExpectationDefinition`,
  mirroring the `reconcile_when_present_casilla_ids` pattern exactly: build-time
  validated (unique + subset of the reconciled axes + unknown-casilla check),
  folded into `RegistryVerificationPolicy`, consumed as pure in-memory set
  membership in the verify path. A CI-only symmetric honesty gate cross-checks the
  declaration against the bundled corpus so the declared signal cannot drift from
  evidence, but never runs in production.
- **D. Per-casilla enum on `ClassifiedDiscrepancy`.** Rejected as the primary
  surface: a discrepancy only exists for casillas that DIVERGED, so a
  per-discrepancy tier would silently omit the common case of a grounded casilla
  that matched. Grounding tier must be knowable for every reconciled casilla,
  hence a verdict-level tuple.

## Constraints

Landing is gated on a clean-validating `ValidatedRegistryAuthority` build: the new
build-time validators must be proven not to trip on unrelated peer TOML, and the
registry is currently peer-broken (modelo 231 / M180 source-ref and workbook-parity
WIP). Per `full-tree-gate-must-distinguish-owner`, that peer red does not block
authoring this decision, but it blocks the field-landing commit until green. The
grounding claim is evidentiary (an oracle supplies the expected value), not
regulatory, so no new `legal_refs` citation is required — the enrolled casillas
reuse their revision's existing grounding.

## Implementation

Add `externally_grounded_casilla_ids: tuple[CasillaId, ...] = ()` to
`VerificationExpectationDefinition` with a uniqueness field-validator and a
model-validator asserting it is a SUBSET of
`computed_casilla_ids ∪ reconcile_when_present_casilla_ids` (a grounded casilla is
still one or the other — subset, not disjoint). Extend the reference and surface
validators with the third unknown-casilla check, and fold the field into
`RegistryVerificationPolicy.externally_grounded_casilla_ids` as a union frozenset —
the projection the verify path consumes with zero file I/O. The verify path, after
`status`/`coverage` are finalised, computes
`externally_grounded_casilla_ids = policy.externally_grounded_casilla_ids ∩ reconciled_casilla_ids`
and `independently_grounded_fraction = |that| / |reconciled_casilla_ids|`, and
carries both as new additive `VerificationVerdict` fields
(`externally_grounded_casilla_ids: tuple`, `independently_grounded_fraction: float`
in `[0,1]`, defaults `()`/`0.0`). Per-casilla tier is then set membership against
the tuple; the filing-level fraction is the honest R1 metric. Enrollment seeds
M100 2025's four oracle casillas into `externally_grounded_casilla_ids` on the
existing expectation fragment. The CI honesty gate
(`test_external_oracle_grounding_enrolled.py`) gains the symmetric direction: every
registry-declared grounded casilla must appear in a bundled oracle payload's
`expected_by_casilla_id` for its filing year. This is primary structured result
data (a grounding projection the verify command exists to produce), not an
incidental advisory, so it rides on the verdict, not the `Notice` channel.

## Rationale

Option C makes grounding tier declared, auditable registry data validated at
build time — consistent with `aeat-schema-central-config` (the authority carries
the declared signal; feature code reads it) and `aeat-registry-authority-flow`
(runtime consumes the snapshot projection, never a corpus scan). It reuses the
proven reconcile-when-present mechanism end-to-end, so R2/R3 grounding gains
become a mechanical enrollment (add ids to the field) with no further schema or
verdict work. The verdict change is non-regressive by construction: the new
fields have safe defaults, are computed strictly after the verdict-determining
logic, and never feed back into `status`/`coverage`.

## Consequences

Good: VERIFIED gains an honest, greppable confidence signal; the R2/R3 roadmap
gets an immediate, low-friction enrollment path; zero change to existing verdict
semantics or serialization for any consumer that ignores the two new fields. Cost:
the registry authoring surface grows a third casilla-axis per expectation (the
axis-conflation risk the reconcile-when-present ADR flagged), mitigated by the
subset-validator making the relationship structurally explicit; the CI honesty
gate must be kept in sync when a new oracle-corpus format is added. Pitfall to
flag downstream: a low `independently_grounded_fraction` must be surfaced as
coverage-of-independent-checking, never a correctness score — a CLI-locale prose
concern for whoever authors the operator-facing notice, out of this ADR's schema
scope.

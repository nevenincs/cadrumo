---
tags:
  - '#adr'
  - '#arch-remediation-registry-format'
date: '2026-07-02'
modified: '2026-07-08'
related:
  - "[[2026-07-02-aeat-architecture-review-audit]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - '[[2026-07-06-arch-remediation-registry-format-research]]'
---
# `arch-remediation-registry-format` adr: `registry revision format convergence: fragmented layout as the single authoring format` | (**status:** `accepted`)

## Problem Statement

The architecture review (finding dual-registry-format-standing, register D6)
confirmed the registry authoring tree carries two on-disk revision formats
indefinitely: at least ten revisions declare bindings, formulas, and
verification expectations inline in `revision.toml` (modelos 117, 126, 128,
187, 188, 194, 231, 361, both 369 schemas, and the M303 2009 revision) while
35 modelos use fragmented subdirectories. The loader normalises both into one
strict schema, and the standing discovery rule warns assessors - a rule that
exists because the split already produced two wrong "parse-only" verdicts on
real under-declaration defects. The mitigation is a discipline rule aimed at
humans; every future audit sweep, coverage script, and tooling pass must
implement both formats forever, or the registry converges and the hazard
class is deleted. No decision existed; this ADR is it.

## Considerations

- The compiled output is format-independent: `ModeloDefinition` /
  `ModeloRevision` are identical regardless of on-disk shape, so convergence
  is a pure authoring-surface move with a mechanical equality proof.
- The fragmented layout is the majority format (35 modelos), the shape every
  recent campaign authored in, and the one the per-family module extraction
  mirrors; converging toward inline would move against all momentum.
- The two largest inline revisions (M303 2009-y-siguientes, M369) are
  calc-grade filing surfaces; their moves need the strongest equality gates.
- The loader's inline-parsing branches and the discovery rule's
  inline-vs-fragmented caveat are deletable only at zero inline revisions.

## Considered options

- **Option A: freeze inline as a permanent second format.** Pro: zero
  migration. Con: permanent dual surface, permanent discovery-rule caveat,
  permanent double implementation in every future tool; rejected.
- **Option B: migrate-on-touch (opportunistic).** Pro: no dedicated
  campaign. Con: the same failure mode boundary-audit D4 just demonstrated -
  opportunistic migrations do not finish; an indefinite tail keeps the dual
  tolerance alive; rejected.
- **Option C (chosen): planned migration of all inline revisions to the
  fragmented layout, then delete inline support.** One atomic commit per
  revision; compiled-schema equality as the per-revision gate; loader
  inline-parsing branches deleted at zero.

## Constraints

- Byte-level authoring moves, zero semantic drift: for each migrated
  revision the loaded `ModeloRevision` (bindings, formulas, casillas,
  constructs, verification expectations, legal_refs) must compare EQUAL
  before and after; the registry validator and the full registry-load suite
  stay green per commit.
- Registry-authority-flow invariants hold throughout: deterministic merge
  order, ambiguous-scalar rejection, and complete cache-invalidation
  fingerprints must cover the new fragment files from the first commit.
- The M303 2009 revision migration must not collide with in-flight M303
  campaigns; schedule per board state (it validates against the whole
  revision, so it genuinely waits on any dirty peer WIP in that tree).
- Deleting inline support is no-legacy compliant only at zero inline
  revisions; until then the loader tolerance stays untouched.
- Follow-up codification: on completion, the
  `registry-revision-content-inline-or-fragmented` rule is edited at its
  vaultspec source to record the convergence (the dual-format caveat becomes
  history; the read-the-loaded-snapshot guidance survives).

## Implementation

A short L2 plan: one phase for the mechanical majority (the eight small
informativa/retencion revisions), one phase for the two large calc-grade
surfaces (M303 2009, M369 schemas) with per-revision equality tests, one
closing phase that deletes the loader's inline-parsing branches, adds a
loader refusal (an inline `bindings`/`formulas` table in `revision.toml`
becomes a loud load error naming the fragmented layout), and updates the
discovery rule at source. The equality gate is a test that loads each
revision at the pre-migration shape and the post-migration shape and
asserts model equality - authored once, parameterised per revision, deleted
with the closing phase.

## Rationale

Between freezing and converging, converging is cheaper over any horizon
longer than one campaign: the loader carries one format, tooling authors
against one format, and the discovery-rule caveat - a rule that exists only
because this split hid two real defects - retires. Migrate-all over
migrate-on-touch is the direct lesson of boundary-audit D4, measured this
same week.

## Consequences

- Every future structural tool reads one format; the two-format blind-spot
  class is deleted rather than mitigated.
- Roughly ten mechanical commits plus two careful ones; the equality gate
  makes each provably safe.
- The registry tree fingerprint changes per migration (more files) - cache
  invalidation handles this by design, but any tooling that memoised file
  paths must be re-checked.
- Until the closing phase lands, the codebase briefly carries three states
  (inline, fragmented, migrating) - bounded by the plan's single-campaign
  scope.

---
tags:
  - '#adr'
  - '#semantic-cluster-hardening'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-06-01-semantic-cluster-hardening-research]]"
  - "[[2026-05-31-core-authority-adr]]"
---



# `semantic-cluster-hardening` adr: `RAG-driven re-audit: Axis 7 + canonical enrollment waves` | (**status:** `accepted`)

## Problem Statement

The codebase is in a standardisation-and-hardening phase. ~1736 Python
modules under `src/aeat` must be cross-referenced against the accepted ADRs
(master spine: the core-authority ADR) to guarantee that every module
enrols into the same canonical base definitions, the centralised pydantic
config, the typed-constant enums, and the central exception hierarchy; that
it is free of shims, re-exports, and duplication; and — crucially — that
domain packages do not contain functionality *redefinitions* of capability
that already lives elsewhere.

Two structural problems block a reliable pass:

1. **Text search cannot find semantic duplication.** Two modules that both
   quantise a `Decimal` to euro cents, or both validate a tax identifier,
   are lexically different and never co-occur in a grep result. The existing
   six-axis swarm-audit cadence has no axis that discovers *functionally*
   equivalent code across vocabulary mismatches.

2. **The audit baseline is stale and untrustworthy.** Since the 2026-05-19
   sweep, 408 Python modules were added and 1305 modified under `src/aeat`.
   The added modules are entirely unaudited and may bypass the canonical
   conventions. Prior research/audits were largely manual and the cadence
   self-reports a ~30% structural-incompleteness rate per pass, so their
   conclusions cannot be inherited as settled.

## Considerations

- A resident `vaultspec-rag` service (port 8766, CUDA, freshly rebuilt index)
  is now available and provides hybrid dense/sparse semantic search over the
  code and vault. Calibration (in the research) shows it reliably clusters
  *functional concepts* (scores 0.95-0.97) while being weak on domain jargon
  and noisy with locale/test rows — it is a clustering instrument, not a
  symbol locator.
- The swarm-audit cadence is convention-only (a documented rule plus 70+
  manual audit docs; no dispatch harness). It already mandates a
  substitutability pre-filter created after the `PROMOTE-001` pass observed a
  96% false-positive rate from naive "X where canonical Y exists" flags.
- The core-authority ADR already defines the canonical homes: `AeatError` /
  `CoreError` exception roots in `core/errors`; `STRICT_FROZEN_CONFIG` in
  `core/_models`; typed-constant `StrEnum`s and identity aliases in `core`;
  and an enforcement-test suite in `diagnostics`. This ADR consumes those as
  the audit's reference truth, it does not redefine them.
- The work is audit-AND-remediate in waves, user-sequenced: duplication ->
  enrollment -> exceptions -> domain redefinition/taxonomy.

## Constraints

- **Shared worktree, live concurrent epics.** Every remediation Step must
  `git diff -- <file>` before its first edit and abort on non-authored WIP;
  commits are explicit-path only; destructive git (stash/reset/checkout/
  clean/rebase) is categorically forbidden. Read-only audit Steps are
  collision-safe.
- **Atomic-relocation discipline.** One symbol/cluster = one atomic commit,
  with a clean `pytest --collect-only -q` immediately before commit, tagged
  `relocation:<symbol>` on any canonical-site move. No re-export bridges.
- **Real gates only.** No mocks/skips/xfail/tautologies; consolidation lands
  with a behaviour/roundtrip test that fails before and passes after.
- **Calculation grounding.** Any consolidation touching tax arithmetic
  preserves legal/source refs and is oracle-grounded, never hand-computed.

## Implementation

### Decision 1 -- Axis 7 added to the swarm-audit cadence

Add a seventh axis to the cadence rule: **"semantic functionality-cluster
overlap & canonical-definition enrollment."** For a target functional
concept it surfaces every implementing site by semantic search, classifies
the set as a true duplication cluster or a constraint-shape-divergent set,
and — where a canonical implementation exists — confirms consumers import it
rather than re-deriving it; where none exists but two or more substitutable
sites do, it nominates a canonical home. It is a depth axis (Sonnet-class)
because each cluster needs substitutability judgement, and it reuses the
existing mandatory substitutability pre-filter.

### Decision 2 -- RAG method contract (binding on every Axis-7 brief)

Query by functional concept, never domain jargon; always `--port 8766`;
`--max-results 20`; score floor approximately 0.50; RAG for discovery, then
`rg` for verification of the exact sites; filter `locales/*.yml` and
test-docstring rows; treat the same string across four locales as one
signal. Pair every semantic sweep with a targeted `rg` pass for known
canonical symbols so single-site authorities are not misread as "no cluster."
RAG is the central re-audit instrument and is itself under evaluation as a
newly adopted tool.

### Decision 3 -- Re-audit stance: trust nothing prior; delta first

Prior research and audit documents are unverified leads, never inherited as
settled. The added/modified-file delta since the 2026-05-19 baseline (408
added, 1305 modified) is the priority surface and is audited first; prior
leads are re-confirmed per wave with the tooling, not assumed.

### Decision 4 -- Wave structure (delta-audit gate feeds all waves)

A delta-audit gate enumerates the changed modules and runs the Axis-7 sweep
over them ahead of the wider tree. Waves then proceed in user order:

- **W1 Duplication clusters.** RAG-discover -> substitutability-verify ->
  consolidate to canonical home -> behaviour/roundtrip test -> atomic commit.
  Seed (re-verified live): decimal-to-cents rounding triplicated in
  `domain/fincas/_rounding.py`, `domain/profile/inventory`, and
  `domain/profile/assets`.
- **W2 Base-definition & pydantic enrollment RE-VERIFICATION.** Re-prove (do
  not trust) the claimed `STRICT_FROZEN_CONFIG`/typed-alias/enum enrollment
  completeness against the current tree, with the added modules as prime
  suspects; close every straggler the delta introduced.
- **W3 Exception consolidation.** Fill the blank exception-restructure ADR;
  apply Decision 6; normalise error-module naming (Decision 7); re-verify all
  23 package error bases still root at `AeatError`.
- **W4 Domain redefinition & taxonomy.** Re-confirm prior duplication-sweep
  conceptual leads against current state; apply Decisions 5 and 8.

### Decision 5 -- `tax_domain` becomes a closed typed-constant

`tax_domain` (today a free-form `str` on `ModeloDefinition`) is promoted to a
closed `StrEnum` typed-constant owned by `core`, with registry hydration at
the boundary: the TOML authoring tree stays free-form per registry-authority
flow, and the loader hydrates the typed enum on load. This enrols
`tax_domain` into the same convention every other closed axis already follows.

### Decision 6 -- `DomainError` is deleted as dead code

`DomainError` in `domain/_errors.py` is defined but used by none of the 23
domain subpackages (all root directly at `AeatError`). It is deleted.
Safeguard: surrounding/related work is committed first, then `DomainError` is
removed in its own clearly-messaged commit so any loss is git-traceable.

### Decision 7 -- Error-module naming normalised to `_errors.py`

The four packages using `errors.py` (`renta`, `iva`, `normatives`,
`manuals`) are renamed to the dominant `_errors.py` convention (19 packages),
each a `relocation:`-tagged atomic commit with consumer updates.

### Decision 8 -- `Subdomain` renamed to remove domain conflation

The `StrEnum` in `domain/portals` named `Subdomain` enumerates AEAT website
hostnames (`SEDE`, `WWW1`, `CLAVE_GOB`) and has nothing to do with the
business-domain layer. It is renamed (e.g. to a portal-host concept) to
remove the vocabulary collision with `aeat.domain.*` and `tax_domain`.

### Open-question resolutions (signed off 2026-06-01)

- **9 -- canonical home for shared numeric primitives:** a new dedicated
  `core` money/Decimal primitive module (not an existing grab-bag util), so
  the cents-rounding consolidation and future numeric helpers have a single
  typed home consistent with the centralisation mandate.
- **10 -- Axis 7 lifecycle:** a *standing* seventh cadence axis (the resident
  RAG service makes it cheap to re-run), not a one-off campaign axis.
- **11 -- delta-audit anchor:** the single 2026-05-19 commit as the campaign
  baseline, with per-subpackage refinement allowed where a later area-audit
  doc gives a tighter boundary.

## Rationale

Semantic search closes the exact gap text search leaves open, and the
research calibration proves it clusters functional concepts reliably enough to
drive discovery when paired with `rg` verification and the substitutability
pre-filter. Extending the existing cadence (rather than building a committed
tool) respects source-hygiene and reuses proven machinery. The re-audit
stance is forced by the measured reality — a 408/1305 delta and a self-
reported ~30% incompleteness rate make "reconcile prior status" unsafe; only
fresh re-confirmation is defensible. The locked decisions (typed `tax_domain`,
deleted `DomainError`, normalised naming, renamed `Subdomain`) all push toward
the same end state the core-authority ADR mandates: strong typing, single
canonical homes, no dead code, no vocabulary collisions.

## Alternatives Considered

- **Build a committed semantic-audit CLI under `src/aeat` or `scripts/`.**
  Rejected: audit machinery in production source violates source-hygiene; the
  cadence already provides the dispatch convention and output contract.
- **Trust the prior research and only reconcile open items.** Rejected: the
  delta size and the documented incompleteness rate make inherited
  conclusions unsafe.
- **Keep `tax_domain` free-form `str`.** Rejected by the strong-typing /
  centralisation mandate; free-form leaves typos indistinguishable from valid
  values and provides no canonical registry.
- **Adopt `DomainError` as a mandated mid-layer base.** Rejected: adds a layer
  no code uses; dead infrastructure is itself drift. Delete is cleaner.

## Consequences

### MERGE actions (consolidate substitutable duplicates)

- Decimal-to-cents rounding -> single `core` numeric primitive (W1 seed).
- Further W1 clusters as the Axis-7 delta sweep surfaces and verifies them.

### DELETE actions

- `DomainError` (`domain/_errors.py`), safeguarded per Decision 6 (W3).

### RENAME actions

- `Subdomain` (`domain/portals`) -> portal-host concept (W4, Decision 8).
- `errors.py` -> `_errors.py` in `renta`, `iva`, `normatives`, `manuals`
  (W3, Decision 7).

### Typed-constant promotion

- `tax_domain` -> closed `core` `StrEnum` with loader hydration (W4,
  Decision 5).

### Documentation

- The blank exception-restructure ADR is authored as part of W3.
- The cadence rule gains Axis 7 (a `.vaultspec` rule edit synced via
  `vaultspec-core`, not a hand-edit of generated provider dirs).

### Risks / future considerations

- RAG blind spots on domain jargon: mitigated by the mandatory paired `rg`
  pass.
- False positives: mitigated by the substitutability pre-filter (96%-FP
  lesson).
- Collision with concurrent epics: mitigated by `git diff` pre-edit checks,
  explicit-path atomic commits, and the destructive-git prohibition.
- The full wave set is large; it runs as a rolling audit -> fix -> review
  cadence, with each wave gated by the campaign-close honesty review before
  being declared structurally complete.

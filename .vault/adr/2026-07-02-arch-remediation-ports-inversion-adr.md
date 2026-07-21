---
tags:
  - '#adr'
  - '#arch-remediation-ports-inversion'
date: '2026-07-02'
modified: '2026-07-17'
related:
  - "[[2026-07-02-aeat-architecture-review-audit]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-06-01-domain-boundary-audit-adr]]"
  - "[[2026-05-31-core-authority-adr]]"
  - '[[2026-07-06-arch-remediation-ports-inversion-research]]'
---
# `arch-remediation-ports-inversion` adr: `domain persistence ports inversion: fincas template as standard` | (**status:** `accepted`)

## Problem Statement

The domain-boundary-audit ADR's ratified D4 ruling accepted the existing
domain-co-located encrypted repositories as managed debt to be "migrated
opportunistically". One month on, the architecture review measured the
result: exactly one domain (fincas) migrated, while ~11 domains across ~40
files still bind to `adapters.persistence.storage` (buckets, submission,
invoices, six modelos repositories, transactions, filing, usage_ratios, the
participation index), the layered gate blanket-waives the whole seam, and
the submission verifier relocation sits as a comment-only deferral. The
operator has directed that deferrals are regression scope. Meanwhile the
fincas migration proved the target pattern in-tree: the domain declares
`_repository_ports.py`, the concrete class lives under
`adapters.persistence.profile`, and the domain package no longer imports the
substrate. This ADR changes D4's migration mode from opportunistic to
planned, ratifies the fincas layout as the mandatory template, and makes the
`.importlinter` pinned-edge burn-down the enforcement instrument.

## Considerations

- This ADR REFINES boundary-audit D4; it does not reopen it. D4's two
  standing sub-rulings survive intact: new repositories are born behind
  ports in adapters, and repositories import secure-storage primitives only
  from the storage package's public top-level surface (the 2026-06-03
  operator refinement). What changes is only the disposition of the
  EXISTING co-located repositories: "opportunistic" becomes a tracked,
  planned campaign.
- The core-authority ADR already constrains application→adapters to
  explicit Protocol ports; the program ADR's Wave 0 (wildcard → pinned
  edges) restores measurement on that seam, and this ADR's burn-down is the
  domain-side counterpart.
- The audit's lazy-import finding (≈815 function-local imports, ~100 on
  this seam alone per the boundary audit) is causally linked: deferred
  imports were D4's cheap fix for the RUNTIME inversion, and they are why
  the static graph under-reports this seam. Completing the port migration
  deletes the need for them domain-side.
- The per-domain roundtrip and anti-tautology suites (real adapters,
  encrypted SQLite) are the behavioural safety net for each migration; they
  already exist for every affected domain.
- `SecureBoundRepository` stays in adapters: its base is SQL/crypto-coupled
  and cannot move to core — ratified previously and unchanged here.

## Considered options

- **Option A: keep D4's opportunistic mode.** Pro: zero scheduling cost.
  Con: measured throughput is one domain per month; the operator directive
  (deferrals are regression scope) forecloses it; rejected.
- **Option B: one big-bang migration of all ~40 files.** Pro: single
  campaign. Con: D4 rejected the 16-file big-bang for shared-worktree churn
  and the reasoning stands — the domains are actively edited by concurrent
  campaigns; rejected.
- **Option C (chosen): planned per-domain campaign on the fincas template.**
  One plan phase per domain; one atomic relocation commit per domain; the
  pinned-edge set in the gate ledger is the countdown; the submission
  verifier relocation (the comment-only deferral) is enrolled as one phase.

## Constraints

- Atomic relocation rule per domain: ports declaration, concrete-class move,
  every consumer update, `__all__` updates, gate-ledger entry deletion, and
  the domain's roundtrip suite — one explicit-path commit tagged
  `relocation:<domain>-repository`; no re-export bridges (no-legacy).
- The single-writer contracts must not change: cross-store primitives
  (profile rename, lifecycle-span delete) keep their atomicity and
  lifecycle-event emission through the move
  (composition-service-no-parallel-write-path).
- Encrypted-boundary equality: each domain's save→load→equality roundtrip
  and anti-tautology proof must pass unmodified against the relocated
  implementation — the tests move homes only if the test-topology rule
  requires it, never weaken.
- Consumers keep importing through package top-level re-exports
  (service-imports-via-top-level-reexports); the ports migration must not
  become an excuse for new private-submodule imports.
- Parent stability: depends only on the accepted D4 ruling, the shipped
  fincas layout, and the Wave 0 gate repair (program ADR) for enforcement —
  all stable; no frontier risk.

## Implementation

The fincas template, applied per domain. The domain package declares its
repository port as a Protocol module (the seven pre-existing `_protocols.py`
ports are reused where they exist); the concrete repository class relocates
to a per-domain module under `adapters.persistence.profile` (or the
storage-adjacent home the fincas precedent uses), importing substrate
primitives from the storage package's public surface; the application layer
(already permitted to import adapters) constructs the concrete and passes it
where domain logic needs it, exactly as the dependency-injection seams in
the repositories' constructors already anticipate. Each domain's migration
deletes its function-local substrate imports, deletes its pinned
domain→adapters entries from the gate ledger in the same commit, and runs
the domain's roundtrip suite as the commit gate. The submission verifier
concrete class relocates behind its existing protocol as one phase of the
same plan. Completion is structural: zero production domain→adapters pinned
entries remain, at which point the domain-not-application contract's sibling
(domain-not-adapters) can be declared exhaustively rather than by exception
list. Order of domains is chosen by contention (quiet domains first:
fincas-adjacent profile stores, submission, buckets; the six modelos
repositories last, coordinated with the modelo-surface campaign).

## Rationale

The decision is mode, not direction: direction was decided by D4 and
re-confirmed by the audit's finding that the hexagon's strongest invariant
carries its largest waiver set. The evidence for abandoning opportunistic
mode is empirical (one domain migrated in a month; eleven remain), and the
evidence that planned mode is cheap is equally empirical (fincas shipped;
the ports files already exist in seven domains; the roundtrip suites already
guard every move). Making the gate-ledger burn-down the tracking instrument
follows the program ADR's ratchet policy: progress is a decreasing count in
a file CI reads, not a claim in a status report.

## Consequences

- Domain packages become testable without the persistence adapter tree, and
  the ~100 deferred-import edges on this seam become deletable rather than
  tracked.
- Roughly 11 small campaigns, parallelizable across agents subject to
  domain contention; the modelos repositories interact with the
  modelo-surface campaign and are sequenced last.
- The gate ledger shrinks materially (every domain→adapters pinned entry
  and its test-file siblings), compounding the Wave 0 hygiene gains.
- Risk: a migration collides with in-flight feature work in the same
  domain package; mitigation is the quiet-domains-first order and the
  standing WIP-abort discipline before first edit.
- Opens the endgame for `exhaustive` layer contracts: with this seam at
  zero, the two remaining deliberate deviations (application→adapters
  wiring, core resource loaders) are the only sanctioned holes, each
  ADR-documented.

## Post-close honesty review (2026-07-03)

The campaign-close honesty review (an independent pass complementary to the
filing-close audit of the same date) returned PASS: the deliverable — zero
production `domain → adapters.persistence` static import coupling — is sound and
sealed (`test_zero_production_domain_to_adapters_edges`, the `domain-not-adapters`
forbidden contract, and the grimp runtime graph all confirm zero). Two scope
precisions are recorded so the claim is not overstated:

- The "zero domain→adapters" framing is scoped to STATIC import edges. The seal
  reads the import-linter / grimp graph, which cannot see dynamic string-target
  imports. One sanctioned dynamic `domain → adapters.inbound` edge remains, out
  of this seam's scope by design: the registry extraction-parser validation
  (`domain.calculations.registry._validate_extraction_profiles`) dynamically
  imports the `adapters.inbound.{borrador,declaracion}` parser modules by
  public-facade string target to confirm registry `parser =` dotted paths
  resolve — sanctioned per `dynamic-import-targets-the-public-facade`, and
  targeting `adapters.inbound` rather than the `adapters.persistence` D2 seam.
  This was subsequently INVERTED to true zero: the domain validator
  (`validate_dotted_callable`) now performs STRUCTURAL-shape validation only and
  names no adapter module, even by string; the allowed-authority prefix +
  importability + callability resolution moved to the adapter-legal CI gate
  `adapters/inbound/tests/test_extraction_parser_paths_resolve.py` (which scans
  every bundled-registry `parser =` path and is anti-tautological). The registry
  is bundled shipped data, so a CI gate is the authoritative resolution check.
- F2 (deferred, peer-owned): the shared `test_importlinter_ledger.py`
  application→adapters ratchet is red at HEAD from an unrelated `#407` commit
  that added an `application.diagnostics_run_health → cadrumo.adapters.**` wildcard
  ignore without bumping the baseline. Out of ports-inversion scope per
  `full-tree-gate-must-distinguish-owner`; handed to the `#407` owner to
  de-wildcard the pin and bump the baseline.

With the `SecureObjectWrite` relocation (the last static TYPE_CHECKING edge) and
the extraction-parser inversion (the last dynamic edge) both landed, grimp
production `domain → adapters` edges are now zero of EVERY kind — static and
dynamic. The domain tree is fully independent of the adapter tree.

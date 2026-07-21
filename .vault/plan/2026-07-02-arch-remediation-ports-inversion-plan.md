---
tags:
  - '#plan'
  - '#arch-remediation-ports-inversion'
date: '2026-07-02'
modified: '2026-07-08'
tier: L3
related:
  - '[[2026-07-02-aeat-architecture-review-audit]]'
  - '[[2026-07-02-arch-remediation-program-adr]]'
  - '[[2026-07-02-arch-remediation-ports-inversion-adr]]'
  - '[[2026-07-06-arch-remediation-ports-inversion-research]]'
---
# `arch-remediation-ports-inversion` plan

## Wave `W01` - quiet domains

Migrate the least-contended domains first on the fincas template: usage_ratios, submission (repository, engine, and the deferred verifier relocation), and buckets. Establishes the per-domain relocation rhythm before the higher-contention domains follow.

### Phase `W01.P01` - usage_ratios repository inversion

Relocate the usage_ratios service persistence behind a domain repository port with the concrete class under adapters.persistence.

- [x] `W01.P01.S01` - Relocate the usage_ratios service persistence in one atomic commit: declare the repository port in domain, move the concrete class under adapters.persistence importing substrate only from the storage package public surface, sweep consumers, update __all__, and delete the usage_ratios pinned domain-to-adapters entries; `src/aeat/domain/usage_ratios/_service.py`.

### Phase `W01.P02` - submission repository, engine, and verifier inversion

Relocate the submission repository and engine persistence behind ports and move the deferred submission verifier concrete class to adapters behind its existing protocol.

- [x] `W01.P02.S02` - Relocate the submission repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries; `src/aeat/domain/submission/_repository.py`.
- [x] `W01.P02.S03` - Relocate the submission engine persistence behind a port in one atomic commit, deleting its pinned domain-to-adapters errors entry; `src/aeat/domain/submission/_engine.py`.
- [x] `W01.P02.S04` - Move the submission verifier concrete class to adapters behind the existing protocol in one atomic commit and delete the deferral comment, discharging register item D3; `src/aeat/domain/submission/_protocols.py`.

### Phase `W01.P03` - buckets event-repository inversion

Relocate the buckets event repository behind a domain port with the concrete class under adapters.persistence.

- [x] `W01.P03.S05` - Relocate the buckets event repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries; `src/aeat/domain/buckets/_event_repository.py`.

## Wave `W02` - independent domains

Migrate the remaining independent single-repository domains: invoices, justificante, attachments, and transactions. Each is one atomic relocation and shares no hard dependency with the others, so the phases parallelize subject to shared-worktree WIP discipline.

### Phase `W02.P04` - invoices repository inversion

Relocate the invoices repository behind a domain port.

- [x] `W02.P04.S06` - Relocate the invoices repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries; `src/aeat/domain/invoices/_repository.py`.

### Phase `W02.P05` - justificante repository inversion

Relocate the justificante repository behind a domain port.

- [x] `W02.P05.S07` - Relocate the justificante repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries; `src/aeat/domain/justificante/_repository.py`.

### Phase `W02.P06` - attachments repository inversion

Verify the attachments domain inventory and relocate its repository behind a port if a production domain-to-adapters edge exists.

- [x] `W02.P06.S08` - Verify the attachments domain pinned inventory at execution time and relocate its repository behind a port if a production domain-to-adapters edge exists, otherwise confirm the domain is already ports-compliant and remove any stale test-edge entries; `src/aeat/domain/attachments`.

### Phase `W02.P07` - transactions repository inversion

Relocate the transactions repository behind a domain port.

- [x] `W02.P07.S09` - Relocate the transactions repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries; `src/aeat/domain/transactions/_repository.py`.

## Wave `W03` - filing repositories

Migrate the three filing repositories (repository, complementaria repository, runtime repository) behind ports. Grouped as one wave because they share the filing domain package and its __all__ surface.

### Phase `W03.P08` - filing repositories inversion

Relocate the three filing repositories behind domain ports in the shared filing package.

- [x] `W03.P08.S10` - Relocate the filing repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries; `src/aeat/domain/filing/_repository.py`.
- [x] `W03.P08.S11` - Relocate the filing complementaria repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries; `src/aeat/domain/filing/_complementaria_repository.py`.
- [x] `W03.P08.S12` - Relocate the filing runtime repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters runtime_repository entry; `src/aeat/domain/filing/_runtime_repository.py`.

## Wave `W04` - modelos repositories and closeout

Migrate the six modelos repositories and the participation index last, coordinated with the modelo-surface campaign that touches the same domain, then close the seam by asserting zero production domain-to-adapters pinned entries remain.

### Phase `W04.P09` - modelos repositories inversion

Relocate the six modelos repositories and the participation index behind domain ports, coordinated with the modelo-surface campaign.

- [x] `W04.P09.S13` - Relocate the modelos repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries; `src/aeat/domain/modelos/_repository.py`.
- [x] `W04.P09.S14` - Relocate the modelos filing repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries; `src/aeat/domain/modelos/_filing_repository.py`.
- [x] `W04.P09.S15` - Relocate the modelos calculation repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries; `src/aeat/domain/modelos/_calculation_repository.py`.
- [x] `W04.P09.S16` - Relocate the modelos verification repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries; `src/aeat/domain/modelos/_verification_repository.py`.
- [x] `W04.P09.S17` - Relocate the modelos runtime repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters runtime_repository entry; `src/aeat/domain/modelos/_runtime_repository.py`.
- [x] `W04.P09.S18` - Relocate the modelos participation index behind a port in one atomic commit after verifying its pinned edge inventory at execution time, preserving the derived-and-rebuildable invariant; `src/aeat/domain/modelos/_participation_index.py`.

### Phase `W04.P10` - seam closeout

Assert zero production domain-to-adapters pinned entries remain and declare the domain-not-adapters contract exhaustively.

- [x] `W04.P10.S19` - Assert zero production domain-to-adapters pinned entries remain in the ledger via the count-ratchet gate landed by the gates-ratchet campaign; `.importlinter`.
- [x] `W04.P10.S20` - Declare the domain-not-adapters layer contract exhaustively rather than by exception list now that the seam is at zero; `.importlinter`.

## Description

This plan executes the domain persistence ports inversion decided by the
ports-inversion ADR, which refines the domain-boundary-audit D4 ruling from
opportunistic to planned migration. The architecture review measured the result
of a month of opportunistic mode: exactly one domain (fincas) migrated while ~11
domains across ~40 files still bind to `adapters.persistence.storage`, and the
layered gate blanket-waives the whole seam. The fincas migration proved the
target pattern in-tree, so each remaining domain follows that template: the
domain package declares its repository port as a Protocol module (reusing the
seven pre-existing `_protocols.py` ports where they exist), the concrete
repository class relocates to a per-domain module under
`adapters.persistence.profile` importing substrate primitives only from the
storage package's public surface, and the application layer constructs the
concrete and injects it.

Each domain migration is one atomic explicit-path relocation commit tagged
`relocation:<domain>-repository`: ports declaration, concrete-class move,
consumer sweep, `__all__` updates, gate-ledger entry deletion, and the domain's
roundtrip suite as the commit gate. No re-export bridges are introduced
(no-legacy). Waves group domains by contention per the ADR's quiet-domains-first
ordering: W01 the quiet domains (usage_ratios, submission including the deferred
verifier relocation of register item D3, buckets), W02 the independent
single-repository domains (invoices, justificante, attachments, transactions),
W03 the three filing repositories, W04 the six modelos repositories and the
participation index (last, coordinated with the modelo-surface campaign) plus
the seam closeout. Completion is structural: zero production domain-to-adapters
pinned entries remain, at which point the domain-not-adapters contract can be
declared exhaustively.

The inventory in this plan is drawn from the current `.importlinter` pinned
domain-to-adapters entries; every phase re-verifies its domain's actual edges
via grep and the ledger at execution time, because the attachments and
participation-index edges are not clearly present in the current pinned set and
peers may have moved them.

## Steps

## Parallelization

Waves are sequenced by contention, quiet domains first, per the ADR. Within a
wave, the phases are independent domain migrations that parallelize across
agents subject to the standing shared-worktree WIP-abort discipline (each agent
runs `git diff` on its domain package before the first edit and aborts on
non-authored WIP). W02's four single-repository domains are the most naturally
parallel. W03's three filing repositories share the filing package `__all__`
surface, so they are serialized under one owner to avoid `__all__` merge
collisions. W04's modelos phase is single-owner and must be coordinated with the
modelo-surface campaign, which edits the same domain; it is scheduled after that
campaign's hub-file work rather than concurrently. The seam-closeout phase
(W04.P10) runs strictly last because it asserts the aggregate zero-entry
condition every prior phase contributes to. Each relocation is one atomic commit,
so no phase leaves the domain half-migrated across a checkpoint.

## Verification

- Per domain migrated: the domain's save-to-load-to-equality roundtrip suite and
  its anti-tautology proof pass unmodified against the relocated implementation,
  and the domain's pinned domain-to-adapters entry count in `.importlinter`
  strictly decreases (the count-ratchet gate from the gates-ratchet campaign).
- The submission verifier deferral comment in `domain/submission/_protocols.py`
  is deleted and no submission module appears in the domain-to-adapters pinned
  set (W01.P02.S04, discharging D3).
- No new private-submodule import is introduced; consumers keep importing through
  package top-level re-exports.
- Seam closeout: zero production domain-to-adapters pinned entries remain
  (W04.P10.S19) and the domain-not-adapters contract is declared exhaustively
  rather than by exception list (W04.P10.S20).
- The plan is complete when every Step is closed and each Step carries an exec
  record per the plan-closure discipline.

---
tags:
  - '#adr'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
related:
  - "[[2026-07-02-aeat-architecture-review-audit]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
  - "[[2026-06-30-convenio-doble-imposicion-adr]]"
  - '[[2026-07-06-arch-remediation-modelo-surface-research]]'
---
# `arch-remediation-modelo-surface` adr: `per-modelo extension surface for the calculation engine and orchestrators` | (**status:** `accepted`)

## Problem Statement

The architecture review found per-modelo special cases accreting inside
generic layers with no declared extension surface: the domain formula runtime
hard-codes M210 IRNR sentinel rate values (reserved negative Decimals the
application layer must recognise and rewrite post-engine via
`_rewrite_m210_sentinels`) and an `_M100_IMPUTATION_YEAR_DAYS` constant; the
registry validator carries the M303 iva-wallet slot carve-out; the calculate
orchestrator strips the M303 compensation binding with a function-local
import; and generic application modules embed dozens of per-modelo tokens
(`_projection.py` 34, `_calculation_actions.py` 25,
`_verification_cross_period.py` 11) while dedicated per-modelo homes
(`_m303_m349_reconcile.py`, `_m036_lifecycle.py`, `_iva_wallet_gate.py`)
prove the codebase already knows the right shape. The precedence ladder that
governs every calculation exists only as ordered guard code plus ADR-citing
comments. Each carve-out is individually ADR-grounded; the aggregate is that
hardening a modelo requires editing the two most contended generic files,
and the M210 sentinel channel is an implicit cross-layer contract carried by
convention rather than by a type.

## Considerations

- The aggregation-taxonomy ADR already declared the precedence ladder
  (profile < mesh backend < borrador < caller, with lock-vs-carry override
  semantics) and the iva-wallet exclusive-owner carve-out in prose; this ADR
  changes their representation, not their semantics.
- The convenio-doble-imposicion ADR already replaced one sentinel
  (`DOMESTIC_TARIFF`) with a typed override kind — the typed-outcome pattern
  this ADR generalises has an accepted precedent on the same surface.
- The declared-data pattern is proven in-tree three times: binding ownership
  (`owned_sources`), the source-kind enrollment tiers
  (ENROLLED/DEFERRED/RESERVED), and the storage namespace registry.
- Modelo-KEYED DATA (applicability rules, censo modelo sets, query
  projections) is legitimate and out of scope; only modelo-BRANCHED LOGIC in
  generic evaluators and orchestrators is the debt.
- The engine's Decimal-only value channels are a load-bearing invariant; any
  typed outcome must ride beside them, not widen them.

## Considered options

- **Option A: status quo** — each carve-out individually ADR-grounded. Pro:
  zero migration. Con: the audit measured the aggregate erosion; the hub
  files keep thickening (three new rulings landed there in one month);
  rejected.
- **Option B: per-modelo plugin classes** (a strategy registry the engine
  dispatches into). Pro: maximal extensibility. Con: over-general for the
  actual inventory — most carve-outs are values and sets, not behaviour; a
  plugin seam in a regulated engine invites logic to escape registry
  grounding; rejected.
- **Option C (chosen): typed outcomes + registry-declared data + named
  per-modelo modules + a ratchet gate.** Sentinels become typed engine
  outcomes; per-modelo constants and exclusion sets become registry/core
  declared data; genuinely imperative per-modelo behaviour lands in named
  `_m<id>_*` application modules; an AST gate ratchets per-modelo tokens in
  generic modules down.

## Constraints

- Semantics frozen: the aggregation-taxonomy rulings (exclusive mesh
  ownership, iva-wallet ownership of the M303 compensation binding, the
  lock/carry override split) must survive the representation change
  unchanged; the M210 continuity and convenio suites are the behavioural
  gate.
- `CasillaObservation` provenance (legal_refs, source_refs, formula_id)
  must ride through the typed outcome exactly as it rides through values
  today.
- No-legacy: the sentinel constants and their rewrite shim are deleted
  outright in the same atomic change that lands the typed outcome — no
  tolerance window in which both channels exist.
- Registry-authority-flow: relocated constants land in the registry
  authoring tree (or `core` for closed sets) and ride the loader/compiler;
  no new side-channel configuration surface.
- The two hub files are contended in the shared worktree: implementation is
  a single-owner campaign, scheduled per the program ADR's Wave 2/3
  boundary.

## Implementation

Four moves, each independently landable. First, the engine result gains a
typed unresolved-outcome channel: `calculate_registry_snapshot` reports an
unresolvable M210 rate as a typed member on the result (casilla id, reason,
grounding context) instead of a reserved negative Decimal;
`_rewrite_m210_sentinels` and the sentinel constants are deleted, and the
verification layer consumes the typed member to emit its BLOCKING finding.
Second, per-modelo values move to declared data: the M100 imputation-days
constant becomes a registry parameter on the M100 revisions; the iva-wallet
owned-binding set and the previous-filing exclusion binding id become one
registry/core declaration consumed by both the validator and the mesh
(deleting the function-local import in the orchestrator). Third, the
precedence ladder is declared as ordered tier data (tier name, owned
sources, override disposition) in the aggregation package, with the guard
code driven by — and a conformance test bound to — that declaration, the
same way binding ownership is already data. Fourth, a structural gate
inventories per-modelo tokens (`Modelo.M*`, `_M<digits>_*`) across a named
list of generic modules and ratchets the count down; new per-modelo
behaviour is steered to named `_m<id>_*` modules or registry data, and the
gate makes a new branch in a generic module a CI failure unless the
allowlist is consciously extended.

## Rationale

The audit's sharpest finding on this surface is that the M210 channel is an
implicit cross-layer contract: a domain engine emitting reserved magnitudes
that exactly one application site knows to rewrite. Typing the outcome makes
the contract checkable and deletes the only in-band signalling in the value
channels. Declared data over plugins follows from what the carve-outs
actually are (values and sets, not algorithms) and from three in-tree
precedents where the same move ended an erosion pattern. The ratchet gate is
what makes the decision durable across the agent fleet — without it, the
next modelo campaign re-accretes branches faster than reviews remove them.

## Consequences

- Unblocks Wave 3 fan-out: modelo campaigns extend declared surfaces instead
  of queueing on two contended files; the hub files shrink rather than
  thicken.
- The engine result model changes shape (new outcome channel): every
  consumer of the calculation result must be swept in the same change — a
  bounded blast radius, but it is the program's riskiest single edit and
  gets the full M210/M100/M303 continuity suites as its gate.
- The precedence-ladder declaration is initially redundant with the guard
  code it mirrors; the conformance test is what keeps the two from
  diverging, and the declaration becomes the single place a future tier
  lands.
- One more inventory gate joins an already-large enforcement ecosystem —
  accepted; it replaces per-review vigilance on the most-edited files.
- The M100 registry-parameter relocation touches filing-grade data: the
  existing grounded calculation tests must confirm identical computed
  values before and after (a pure representation move; zero numeric drift
  tolerated).

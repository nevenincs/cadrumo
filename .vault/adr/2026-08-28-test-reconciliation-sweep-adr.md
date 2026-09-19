---
tags:
  - '#adr'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:51180d529e0875cdb3299c1531920bb06a8862202ad8b237a8310e095506eff3'
related: []
---

# `test-reconciliation-sweep` adr: `test reconciliation sweep` | (**status:** `accepted`)

## Problem Statement

A verb-rename campaign closed while several of its consequences were still
carried as prose notes rather than code. Three of those consequences were not
defects in the ordinary sense: each was a conflict between two things the
repository asserts, and each had a convenient resolution that would have made a
gate green while losing something real. A decision record is needed because the
convenient resolution is the one a later reader would otherwise assume was
taken.

## Considerations

- A coverage predicate that enumerates a vocabulary silently narrows when the
  vocabulary is split; the gate stays green while its denominator shrinks.
- Package namespaces are inert by architectural rule, so a gate demanding a
  package re-export cannot be satisfied without violating that rule.
- An error surface that loses its free-text remedy is only a regression where a
  mechanical remedy actually exists; where none does, a typed
  `operator_decision` outcome is the honest record.

## Considered options

- **Delete the stale governance row alone.** Gate-green in one line. Rejected:
  it accepts that a remote writer which was governed under its previous name is
  no longer governed at all.
- **Widen the governance predicate and govern every leaf it newly selects.**
  Chosen. Costs sixteen catalogue rows, several for peer-owned verbs.
- **Mark the profile field globally required to satisfy the per-modelo walk.**
  Rejected: the required flag also drives completeness and presentation, so it
  would demand an attestation from taxpayers with no such obligation.
- **Repoint every stale error assertion at the typed action projection.**
  Rejected as a blanket rule: correct where no mechanical remedy exists, wrong
  where one does, because it would encode the guidance loss as the contract.

## Constraints

- The governance catalogue must derive secure-object metadata from the central
  namespace registry, so a row cannot be hand-written for a namespace whose
  ownership has not been traced.
- Per-modelo requiredness does not exist in the profile schema; the preflight
  walk can only select a field that is globally required, so the modelo-scoped
  requirement currently lives as a branch in code.
- Work lands in a shared tree where a peer's broad commit can absorb part of a
  change and revert the rest, so every repair must be re-verified after peer
  activity rather than trusted from an earlier green.

## Implementation

Transport governance is keyed on the post-split vocabulary rather than the
pre-split one, and every leaf the widened predicate selects carries a catalogue
row naming its command family, owner domain, and — where ownership is traced —
its registered namespace policy. A leaf that acquires a local artefact rather
than namespace-owned data carries family and owner and deliberately claims no
namespace policy.

Gate-versus-rule conflicts resolve in favour of the architectural rule: a gate
clause demanding a package-namespace re-export is removed and the equivalent
assertion is made against the defining modules, which already carry the intent.

Operator guidance that a typed channel cannot express is carried in the
localised message instead, following the precedent already set for another
modelo, with the interpolation travelling in the refusal context.

## Rationale

Each chosen option is the one that preserves a property the repository already
claims, at the cost of more work. The widened predicate wins on a knockout
criterion: the alternative silently degrades a safety surface for a verb that
writes persisted records, and the rename that caused it was made by this
campaign. The message-carried guidance wins because the remedy it names is real
and reachable, so a typed no-recovery outcome would have been factually wrong.

## Consequences

Governance now tracks the transport vocabulary rather than lagging it, and the
catalogue is larger and includes rows for verbs this campaign does not own — it
is an inventory, not a claim of authorship.

The profile schema's missing per-modelo requiredness is documented rather than
worked around silently; the branch in code remains until that capability is
authored, and this record is where a future reader learns the naive fix
over-demands.

A gate whose identity check compares interned short strings cannot detect a
same-literal shadow; the companion structural check carries that coverage, and
that limitation is now recorded rather than assumed.

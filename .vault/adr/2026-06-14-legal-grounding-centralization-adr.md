---
tags:
  - '#adr'
  - '#legal-grounding-centralization'
date: '2026-06-14'
modified: '2026-06-15'
related:
  - '[[2026-06-14-legal-grounding-centralization-research]]'
  - "[[2026-06-14-legal-grounding-centralization-audit]]"
---



# `legal-grounding-centralization` adr: `Cross-Domain Regulatory-Value Centralization — Remediation Decisions` | (**status:** `accepted`)

## Problem Statement

The cross-domain centralization audit (a five-agent RAG swarm) inventoried inline /
hardcoded / ungrounded regulatory values and definitions that bypass the central
authority across IRPF, IVA, recargo, deductible-expense, and IVA-calculation
surfaces, in violation of `aeat-schema-central-config` and
`registry-calculation-legal-grounding`. The decision the existing rules do NOT make
on their own — and which this ADR records — is the per-finding remediation mechanism
(registry parameter vs `external_constants` leaf vs `Settings`) and, for the two
dormant subsystems the swarm found, the bind-versus-delete choice. This is a
remediation campaign, not a novel architecture; the decisions are mechanism and
sequencing, grounded in the rules already in force.

## Considerations

Three remediation mechanisms exist, in declining grounding strength: (1) a registry
parameter with `legal_refs`→`corpus_ref`, guarded by the
`registry-calculation-legal-grounding` corpus-text gate — strongest, but heaviest to
author; (2) a curated `core.external_constants` leaf constant with a binding-provision
docstring — the rule explicitly sanctions this for "the small set of leaf constants
that are easier to consume by-name than via the registry"; (3) `Settings` — only for
deployment/operational values, not regulatory ones. Two findings (F2 prorrata, F4
casilla_59/60) concern subsystems that are built, tested, and exported but have ZERO
production callers — `no-legacy-compatibility` and `no-dormant-source-resolvers`
forbid leaving live-but-unrouted capacity, forcing a bind-or-delete decision.

## Constraints

No released data, so no migration concerns (`no-legacy-compatibility`). The one
genuine risk surface is F1 (the art. 23.2 tier reducción wiring): the reducción rate
is the deductible percentage applied to real rental income on a live filing path, so
its remediation must prove value-parity against the existing tier oracle tests before
landing — unlike the value-unchanged P01 centralizations, which carry near-zero
regression risk because the literal moves home without changing.

## Implementation

Per-finding mechanism: F6 (art. 58/59 family thresholds), F5 (DT12 40 %, SAL 10 % +
2× factor), and the F2-interim prorrata thresholds promote to `external_constants`
leaf constants with binding-provision docstrings — value-identical moves that land
first (phase P01). F1 wires the live dispatch (`resolve_reduccion`) to the dormant
registry reader (`_resolve_tier_reduccion_rate`) so the registry parameter becomes
causal and the inline constant degrades to a documented fallback, mirroring the
in-repo `_amortization_ledger.py` gold standard, with a parity proof against the tier
oracle tests (phase P02). F3 resolves the M303/M390 compensación casilla numbers
through the registry snapshot casilla definitions. For the dormant subsystems (F2
prorrata, F4 casilla_59/60), the default decision is BIND through the registry
(author the `prorrata` source / `ledger_iva_aggregation` bindings and enroll the
resolver); delete only if binding proves the capacity is genuinely unreachable and
unwanted (phase P03). Where a corpus text already exists for a value, prefer
mechanism (1) over (2) so the grounding gate guards it.

## Rationale

The mechanism ladder follows the rules already in force: regulatory values belong in
the registry (`aeat-schema-central-config`), grounded against their binding provision
(`registry-calculation-legal-grounding`), with `external_constants` as the sanctioned
leaf shortcut. The bind-default for dormant subsystems follows
`no-dormant-source-resolvers` (a resolver is enrolled or deleted, never dormant) and
`one-aggregation-path-pull-equals-calculate`. Sequencing safe-before-risky lets the
campaign demonstrate motion and lock the easy wins before the one live-path change.

## Consequences

Gains: every remediated value gains a single typed home and (where corpus-grounded) a
gate that catches drift — directly preventing a recurrence of the pass-1 reserva
50%-vs-2× error. The dormant-subsystem decisions remove live-but-unrouted capacity
that misleads readers into thinking a calculation is wired when it is not. Honest
difficulty: F1's wiring changes a live filing amount's provenance (not its value), so
it needs the parity proof; and binding the prorrata subsystem is non-trivial registry
authoring — if a clean binding proves out of scope this pass, deletion is the
rule-compliant fallback rather than leaving it dormant. The broader goal (grounding
ALL Spanish-tax concepts) is larger than this inventory and continues in subsequent
passes (IS brackets, IRPF escalas, módulos, informativa thresholds).

## Codification candidates



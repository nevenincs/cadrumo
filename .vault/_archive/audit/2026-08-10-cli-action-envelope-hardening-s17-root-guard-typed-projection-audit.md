---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:2ffa4ad590cbb981274f02c41435ae529f38affb7faf2692654147c0c47be0ae'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# `cli-action-envelope-hardening` audit: `S17 root guard typed projection`

## Scope

Independent Terra xhigh review of the expanded `W03.P05.S17` denominator: 17
profile, taxpayer, session, and former-product refusal scenarios plus the two
S16 storage-policy outcomes. The review checked application ownership of
precondition meaning, requested live-leaf preservation, exact catalogue and
live-schema bindings, typed boundary attachment, absence of executable
recovery prose, real-root behavior, sequential invocation isolation, and the
S18 ownership boundary.

## Findings

### refusal-context-typing | high | Policy context initially lost its invariant value type

Status: closed. The generalized policy-refusal context originally relied on an
inferred dictionary type that could not safely accept heterogeneous factual
evidence. It now builds an explicit `dict[str, object]` and admits only
`*_setting` evidence into the compatibility presentation context. Configured
type analysis reports no S16 or S17 diagnostics.

### real-root-attachment | medium | Initial tests did not execute the real root callback

Status: closed. The integration coverage now calls the real Click/Typer root
with `standalone_mode=False` under the production error seam. It proves typed
attachment for root fallback, explicit database, no active profile, unresolved
profile selection, absent session, and missing taxpayer identity. The root
typed-projection module passed all 11 tests.

### requested-leaf-lifetime | medium | Root leaf identity required invocation-scoped retention

Status: closed. A root-bound `ContextVar` retains the canonical requested leaf
for shared guards that cannot receive the Click context directly, and a root
close callback resets it. A sequential-invocation test proves no leaf leaks
into the next command.

### exhaustive-session-typing | low | Exhaustive enum control flow briefly tripped strict typing

Status: closed. Session refusal reasons are classified through an exhaustive
typed match without a redundant unreachable fallback. The single requested
leaf context definition also carries its complete `ContextVar` type. Targeted
type analysis passes with zero errors.

No additional defects remain. The canonical negative session test correctly
asserts the structured action identity is not `operator.profile.login` and
that no legacy `suggestion` field or executable command prose is present.

## Recommendations

- `refusal-context-typing` (closed): retain the explicit invariant dictionary
  and factual setting-name filter.
- `real-root-attachment` (closed): keep the real-root tests as the regression
  authority for the typed handoff.
- `requested-leaf-lifetime` (closed): keep cleanup registered on the owning
  root context whenever invocation-scoped state is introduced.
- `exhaustive-session-typing` (closed): keep session reason classification
  exhaustive as the core enum evolves.

The broader producer integration lane passed 56 tests. Three failures are
peer-owned: one legacy custody assertion still expects serialized
`suggestion`, and two root-guard census assertions do not yet classify newly
introduced ledger counterparty and evidence leaves. They do not invalidate the
S17 owner proofs.

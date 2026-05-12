---
tags:
  - '#adr'
  - '#aeat-cli-config-vs-setup-namespace'
date: '2026-05-12'
related:
  - "[[2026-05-08-aeat-cli-gap-closure-plan]]"
---

# `aeat-cli-config-vs-setup-namespace` adr: `aeat config vs setup namespace boundary` (**status:** `accepted`)

## Problem Statement

W2 of the aeat-cli-gap-closure rollout shipped IVA / IRPF / modelo enrolment / SII / Verifactu / ROI profile keys behind `aeat setup profile set <key> <value>`. UX-016 asks for a peer `aeat config list / get / set / unset` family. Choice: alias the new family to the existing profile backend, or carve out a separate config store.

## Considerations

- Single source of truth (the WorkflowState.profiles mapping) is easier to reason about, easier to back up, easier to migrate.
- Operators in some shells already type `setup profile`; some auditors expect `config`. Both surfaces sharing one backend lets each muscle memory work without divergence.
- Settings keys (`format`, `language`, `verbosity`) are not profile fields; they belong to the env-var-driven Settings module.
- Named multi-config support (`aeat config configurations *`) presupposes a global selector or context switch that the deadline engine, the filing pipeline, and the workflow state machine do not yet have.

## Constraints

- The W2 PROFILE_KEYS registry is authoritative for profile validation.
- The structured-error emitter and the `_normalise_key` normaliser must be reused, not duplicated.
- Settings keys must continue to flow through env vars; the project's settings module does not yet expose a mutation surface.

## Implementation

Alias mode. `aeat config` is a thin wrapper that routes keyed operations through the same `aeat.application.profile._actions` backend that powers `aeat setup profile set`. One source of truth (the WorkflowState.profiles mapping); two co-equal CLI presentations.

Concrete contract:

- `aeat config list` reads every registered PROFILE_KEYS row plus the operator settings (format, language, verbosity) and renders one row per key with the current value (or `<unset>`).
- `aeat config get KEY` resolves through the same code path `aeat setup profile get` uses.
- `aeat config set KEY VALUE` writes through `set_profile_values` for profile keys; for the operator settings keys it returns the read-only-via-env explanation.
- `aeat config unset KEY` mirrors `aeat setup profile unset`.

The `aeat config configurations` family is deferred. No concrete use case requires multi-config switching today.

## Rationale

Aliasing keeps the W2 PROFILE_KEYS schema authoritative, avoids divergence between two key stores, and leaves the door open to promote `aeat config` to a parallel namespace later (the alias contract does not foreclose it).

## Consequences

- Both `aeat setup profile` and `aeat config` remain available; deprecating one later is mechanical because the backend is shared.
- Settings keys are read-only through `aeat config get` for this slice; `aeat config set format json` will emit a refusal pointing at the env-var route.
- The parallel-mode option remains a future possibility — promoting `aeat config` to a parallel namespace would only require adding a separate config store and dispatching on key prefix.

---
tags:
  - '#research'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-05'
modified: '2026-07-17'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-adr]]"
---

# `binding-vocabulary-cli-cohesion` research: `closure grounding inventory`

This research note records the grounding inventory for the already-closed `binding-vocabulary-cli-cohesion` campaign. The original ADR consumed the broader bindings architecture audit and research, but this feature did not carry a same-feature research document, which left the feature gate with an ADR-without-research diagnostic.

The scope here is inventory and traceability only. It does not reopen the ADR, add a new plan, or introduce new implementation scope.

## Findings

### Grounding Documents

The vocabulary and CLI cohesion ADR is grounded in the bindings architecture unification audit and research that surfaced the naming and operator-verb drift: homonymous binding row and observation names, overloaded resolver/provider terminology, false-friend registry binding filenames, and the three-verb source-pull surface.

The same ADR also depends on the source-kind taxonomy unification ADR and the CLI pull/file standard ADR. Those documents provide the two closure boundaries the campaign enforced: one canonical source-kind vocabulary for binding and resolver surfaces, and one operator-facing source-pull verb story that does not hide compute under a transport verb.

### Closure Evidence

The plan is complete at 27 of 27 steps with no missing exec records. The close-honesty audits record that the campaign landed the vocabulary, CLI, schema typing, and documentation/locale sweeps, while explicitly tracking remaining non-blocking follow-ups instead of treating them as hidden completion.

### Residuals

The residuals named by the ADR acceptance note remain follow-ups, not blockers to this campaign's closure: explicit-union member publication for ledger and retenciones selector families, and the CasillaId-migration collection repair. This research note adds no new residual.

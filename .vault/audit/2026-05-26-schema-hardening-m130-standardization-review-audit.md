---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-26-schema-hardening-m130-standardization-plan]]'
  - '[[2026-05-26-schema-hardening-m130-standardization-inventory-audit]]'
---

# `schema-hardening-m130-standardization` Code Review

M130STD-001 | MEDIUM | Application draft construction dropped bound casilla-only bindings

The M130 split preserved registry semantics, but the broader application/export
gate exposed a generic draft-construction gap. `build_draft` forwarded bindings
referenced by formulas, but did not also forward bindings attached directly to
bound casillas. That meant a bound casilla such as M130 casilla 15 could be
calculated in registry tests that supplied explicit `binding_values`, while
application-level draft construction still behaved as if the value was manual
input.

Resolution: fixed generically. `build_draft` now includes bound-casilla binding
ids in the calculation binding set and materializes calculated bound casilla
values as inherited registry-binding values. No M130-specific condition or
loader/schema special case was added.

M130STD-002 | LOW | Downstream tests retained stale single-file and manual-input assumptions

Several tests still assumed `modelos/130.toml` existed or that previous-period
negative result casillas could be supplied as manual casilla input. Those
assumptions are stale under the current registry contract: bound casillas must
receive their values through bindings, and M130 now uses directory fragments.

Resolution: fixed the affected registry, filing, and BOE export tests to build
from committed fragments and provide bound carry-forward values through
bindings. The tests continue to exercise real registry loading and application
behavior rather than fakes, mocks, or monkeypatches.

M130STD-003 | INFO | M130 split remained on the generic fragment substrate

No per-modelo loader behavior, schema override, or ad hoc application branch was
introduced. M130 now discovers as one fragment-directory revision. `130.toml`
has been removed, and the largest M130 fragment is 721 lines.

M130STD-004 | INFO | External code-review dispatch could not start a fresh agent

The mandatory review pass was attempted through a `vaultspec-code-reviewer`
agent, but the shared session had already reached the active agent limit. The
closeout therefore records a local review pass plus the focused regression gate.
Residual risk is limited to the path-scoped surface covered here; no full-suite
claim is made.

M130STD-005 | INFO | Next standardization edge

After M130, the largest remaining single-file modelos are M190, M115, M720, and
M390. The next rollout slice should normalize M190 first unless a broader
line-size gate or revision-fragment policy identifies a higher-risk candidate.

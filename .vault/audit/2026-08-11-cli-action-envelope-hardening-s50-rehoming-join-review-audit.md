---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:450b41b9d5d04720dc1a69f58c51e2a282a815aad695b96042f5563249d02a3f'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# `cli-action-envelope-hardening` audit: `S50 rehoming join review`

## Scope

Independent review of the S50 structural rehoming ledger, immutable preimage join, current-source scanner, ownership join, TOML boundary, generic imported-domain proof, migration convergence, and direct validation contract. Final verdict: PASS. The plan step remains open for lifecycle handling outside this audit.

## Findings

### structural-ordinal-stability | high | Non-identical sites perturbed structural identities

Originally, `SourceFingerprint.structural_group` omitted `normalized_ast_sha256`, allowing a semantically distinct preceding site to renumber an otherwise unchanged identity. Remediated: the structural group now includes the normalized hash and the direct ordinal regression proves a non-identical insertion preserves prior identities while identical multiplicity receives distinct ordinals.

### dynamic-import-resolution | high | Target routes through importlib were silently omitted

Originally, direct and aliased `importlib.import_module` routes could evade observation or refusal. Remediated: direct, module-alias, function-alias, and nonliteral dynamic forms are identified and fail closed unless they satisfy a separately proved closed shape; the direct route regressions pass.

### lazy-facade-whitelist | high | Static facade recognition exempted unrelated or unproven imports

Originally, a broad lazy-facade exception could exempt side imports or shadowed bindings. Remediated: the scanner carries the exact verified PEP-562 return-call identity, proves its unshadowed module or local import binding, and exempts only that call. Regressions cover side imports, shadows, control-flow taint, local aliases, and rebinding.

### non-target-import-closure | high | A purported non-target dynamic import escaped through nested capture

Originally, a nested closure could capture a dynamically imported module while local-use analysis treated the route as closed. Remediated: nested function, lambda, and comprehension references invalidate the closed non-target proof; the nested-capture regression passes.

### registered-lazy-loader | high | A source-derived CLI dynamic loader lacked a supported proof shape

Originally, the scanner admitted only literal module names and rejected the source-constrained registration loader. Remediated: the generic finite-domain proof derives a bounded domain without path or identifier exceptions. Across-module admission requires one unaliased, unrebound direct import from one in-repository module that declares one non-empty literal string tuple. Regressions reject mutable, computed, aliased, star, multiple, missing, external, cyclic, and rebound provenance.

### accessor-target-erasure | high | Zero-argument accessors could erase a target dynamic import

Originally, a static accessor could suppress a target-relevant module or symbol import. Remediated: a closed zero-argument literal accessor resolves and records target results, while nonclosed, parameterized, branched, or nonliteral accessor shapes fail closed. The target and non-target accessor regressions pass.

### guarded-capture-rebinding | high | A static membership guard could be invalidated after closure creation

Originally, an enclosing parameter could be rebound after an inner loader captured it. Remediated: every enclosing lexical scope is checked for parameter bindings before a membership-guarded import is admitted, and the post-closure target-rebinding regression passes.

### migration-replay-convergence | high | A locator-only concurrent source shift briefly broke the required second-run no-op

During this review, the no-write replay returned `E_REHOMING_MIGRATION_CHECK_CONTENT` while preserving the ledger file. The delta was bounded to two locator records for `ModeloProfileReadinessError` constructors in `src/cadrumo/application/modelo/_m303_filing_evidence.py`; there were zero structural additions, removals, owner changes, or disposition changes. The S50 owner refreshed exactly those locators. Independent final replay now returns `E_REHOMING_MIGRATION_CHECKED:238` with identical before and after hash, and final rendered-versus-disk comparison reports zero locator delta. This finding is remediated and retained for lifecycle history.

## Recommendations

Preserve the current generic, fail-closed resolver and its rejection matrix; do not add path, filename, or capability-specific exceptions. Keep locator metadata non-gating, but require every bounded ledger refresh to finish with a same-input no-write replay and direct validator before review closure. Retain immutable preimage identities, exact structural owner joins, and exclusive open-step ownership as the regression boundary.

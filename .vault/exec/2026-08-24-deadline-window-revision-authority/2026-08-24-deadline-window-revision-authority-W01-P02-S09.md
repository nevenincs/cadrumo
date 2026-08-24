---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e8c26e9a23df294450766a31b91255b9ee23c3da438d864c4736752f3ca4e793'
step_id: 'S09'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Prove deadline validation under cold construction and fingerprint-backed warm-load verdict paths with planted mutations

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Locate the canonical warm-load verdict path and its governing decisions with
  Vaultspec RAG, then confirm exact symbols with targeted search.
- Audit existing fingerprint and validation authorities before considering code;
  reuse `loader_code_fingerprint` in the experiment and create no cache,
  validator, resolver, or coordinate declaration.
- Plant the validation-code fingerprint into the existing writable and shipped
  verdict keys and run the real cold/warm focused suite.
- Restore the experiment after it proved that enabling the stronger key before
  corpus repair makes the default authority correctly refuse known invalid
  deadline rows.

## Outcome

Deferred. The experiment found a real same-version warm-verdict gap: the current
key binds registry identity, source evidence, and package version, but not the
validator implementation. An older green verdict can therefore skip a newly
added invariant when the authored tree is unchanged.

The canonical repair is to add the already-existing
`loader_code_fingerprint` to the existing verdict key. No new declaration is
needed. That repair cannot safely land at this point in the ordered plan: once
enabled, the focused run passed 21 tests and failed five because cold validation
correctly reached the known, not-yet-repaired M210, M303, M322, and M353 corpus
defects and deliberately synthetic trees certified by old test keys. Default
authority and CLI construction would be unavailable until W02 repairs those
rows.

S09 remains unchecked. Retry the same canonical key extension after W02 corpus
repair, then add completeness assertions once S08's shared supported-year
authority is available.

## Notes

- Vaultspec RAG's top production hit was `_verdict_cache.py`; `_authority.py`
  owns the only production verdict consultation, and `_compiled_cache.py`
  already owns the registry-package source fingerprint. Exact search found no
  second deadline validator cache or alternate source fingerprint to reuse.
- Focused experimental command: validation verdict location, mutable-tree
  invalidation, parameter-authority invalidation, validation verdict cache, and
  bundled verdict stamp tests. Result before restoration: 21 passed, 5 failed.
- A concurrent unrelated commit captured the experimental production diff from
  the shared worktree. This record accompanies the narrow restoration so that
  the default authority is not left unusable.
- Periodic completeness was intentionally not asserted because S08 remains
  blocked on shared temporal coverage.

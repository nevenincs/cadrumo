---
tags:
  - '#audit'
  - '#test-harness-sanity'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:588f0d6a57ff1d6aba97753ca40265c128360cb42cb5a0e1b868e93ed9462c68'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---
# `test-harness-sanity` audit: the one monkeypatch the no-monkeypatch gate cannot absorb

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_read_parameter_authority_invalidation.py`
- `src/cadrumo/tests/test_monkeypatch_inventory.py`
- `.vault/plan/2026-08-14-test-harness-sanity-plan.md`

## Summary

The harness-sanity plan's Verification section requires that the no-monkeypatch
inventory and its discriminating controls pass **with no allowlist, suppression
or renamed equivalent**. It does not pass. One live site violates it, and this
record exists so the failure is deferred with a reference rather than carried as
a checked row.

The site is not old debt. It landed **during** this campaign, on 2026-08-14, in
commit `6d80634e6b` from the registry lane.

## Findings

### Registry read-parameter invalidation test monkeypatches the bundled path

`src/cadrumo/domain/calculations/registry/tests/test_read_parameter_authority_invalidation.py:115,138`

The fixture `redirected_bundled_registry_root` replaces
`core.resources.bundled_path` so that `bundled_path("registry", "aeat")` returns
a caller-chosen temp tree, leaving every other lookup real.

`test_no_monkeypatch_fixture_or_context_usage` reports four sites from it:
the `pytest.MonkeyPatch` parameter, the `monkeypatch` argument, the
`monkeypatch.setattr` call and its name reference.

## Why it cannot simply be rewritten

The obvious remedy is to drop the redirection and drive the same proof through
`read_parameter`'s explicit-root argument, which takes a caller-supplied tree.
That was checked and **it is not equivalent**, for a reason worth recording
because it is invisible from the test:

`read_parameter` computes
`root = bundled_path("registry", "aeat") if registry_root is None else registry_root`
and both branches then call the identical
`ValidatedRegistryAuthority.load(root, source_root=source_root)`. Reading only
that function, the branches look interchangeable and the redirection looks
gratuitous.

They diverge one layer down. `_loader.py:1224` reads

```
use_disk_cache = registry_disk_cache_enabled(is_bundled=is_bundled_registry_root(resolved))
```

so the fingerprint-keyed on-disk compile cache is enabled **only for the bundled
root**. An explicit temp root does not take it. Since the test's whole subject is
whether a warm cache can serve an authority that predates a registry edit, a
proof that skips the cache under test proves nothing about the branch production
takes. The redirection is load-bearing.

There is also no settings seam to use instead: `bundled_path` resolves package
data through `importlib.resources` with no override, and `_bundled_registry_root`
is an `lru_cache` over it.

## Recommendations

Both are the registry lane's call, not this campaign's:

1. **A production override for the bundled registry root.** This removes the
   monkeypatch, and it puts a real root-redirection capability into production on
   a test's authority. That trade belongs to the owner of the registry
   boundary.
2. **Run the test in a subprocess against a PYTHONPATH-shadowed package** whose
   own `_data/registry/aeat` is the temp tree. No production change and no
   patching: `bundled_path` resolves naturally and `is_bundled_registry_root`
   is genuinely true, so the disk cache is exercised. The cost is a subprocess
   test and a package copy, which is a poor trade in a campaign whose subject is
   suite runtime.

## What was NOT done, and why

The gate carries no allowlist at all. Adding one would turn this red into a
green in minutes, and the plan's criterion forbids exactly that: "with no
allowlist, suppression, or renamed equivalent". A first allowlist entry
introduced to clear a criterion that names allowlists as the thing to avoid is
the gate being switched off, so the gate stays red and this record carries the
reason.

Note the asymmetry with a sibling gate touched in the same campaign. The mock
inventory's real-boundary exemption WAS extended, because that list already
existed, its entries state why each class is real, and a liveness check fails
stale ones. An allowlist that records a judgement and an allowlist that launders
a failure are different instruments; the criterion rules out the second, and the
first is not available here because there is no list to record a judgement in.

## Status

Open. The plan is otherwise complete: every other criterion is satisfied, and
the ownership-manifest criterion that stood beside this one was closed by
removing the five substitutable duplicate groups blocking generation.

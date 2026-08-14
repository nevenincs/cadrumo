---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:6cafe8ea20ccd557b0ac1d132e7947be9efe45bca5c04eadc43b957eea3b0ac3'
step_id: 'S07'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Measure whether the loader fingerprint caches, the TTL windows and the two unbounded cache sites honour complete-tree invalidation, closing the open staleness question, and fix any cache that can serve stale compiled output

## Scope

- `src/cadrumo/domain/calculations/registry/_loader_cache.py`
- `src/cadrumo/domain/calculations/registry/_loader_fingerprints.py`
- `src/cadrumo/domain/calculations/registry/_compiled_cache.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Measure each cache tier by adversarial construction rather than by reading:
  build a synthetic registry, load it, mutate a source file, reload, and observe
  which compiled output is served.
- Measure the mutable-authoring-tree fingerprint window, the bundled-tree
  window, and both bare unbounded caches, in the production regime with the
  compiled disk pickle and verdict directories redirected to throwaway
  locations.
- Restrict the registry-tree fingerprint cache to the tree whose freshness check
  can speak for the whole of what its entry asserts, so a mutable authoring tree
  is fingerprinted afresh on every call.
- Correct the two prose passages in the loader cache policy module that
  described the superseded mutable-tree window.
- Add the regression module pinning the invariant structurally, under a warm
  regime with a persisted validation verdict and a warm compiled cache, and in
  the production disk-cache regime through a child interpreter.
- Replace the positional callable alias for the live fingerprint lookup with a
  protocol that declares its keyword-only parameters.
- Register the child-interpreter lint exemption for the new module beside its
  sibling exemptions, with its reason stated.

## Outcome

Four cache tiers were measured; two serve compiled output that predates a live
edit and two do not.

The mutable-authoring-tree window was a real defect and is fixed. The
fingerprint cache entry holds the complete tree fingerprint -- one
`(path, size, mtime_ns, content_digest)` row per directory and per TOML file --
and that tuple is what keys the compiled-registry cache, the compiled disk
pickle and the persisted validation verdict. Its freshness check compared only
the directory rows. Writing to an existing file moves no parent-directory stat,
so a plain rewrite of a modelo TOML -- different size, different modification
time, the easiest possible edit for a cache to notice -- left the check
satisfied and the pre-edit key was served. Measured directly: a load issued
immediately after the rewrite returned the pre-edit casilla value, and only a
load past the window returned the edited one. The cache is now restricted to the
package-bundled tree, whose rows carry an empty content digest by construction
and whose window is a declared bound on how often the tree walk is redone rather
than a claim about file content. A mutable tree recomputes its complete
fingerprint on every call; the compiled result is still reused through the
fingerprint-keyed caches above, so what is paid back is the per-file walk that
was never safe to skip. The same construction after the fix returns the edited
value on the immediate reload.

The bundled-tree window also serves stale output, deliberately and as
documented. Its cache hit short-circuits before the directory walk, so a content
edit and a layout change -- a newly added modelo file -- were both invisible for
the full window and both appeared once it expired. This is the behaviour the
policy module's own commentary reasons about and accepts, so it was measured and
reported rather than changed: removing it would delete the production hot path's
principal saving, which is a decision above this row. It does bear on the
authorizing decision record, whose gate-placement argument states that data
invariants may ride the validation verdict because the verdict is keyed on the
complete tree fingerprint and the data cannot change without changing it. As
measured that premise now holds unconditionally for a mutable tree and holds for
the bundled tree only up to its declared window; the record's wording should say
so rather than claim the key cannot go stale.

The memoised loader-source fingerprint is sound. Its value recomputes identically
within a process, which is the correct answer: it hashes source files this
interpreter has already imported, so it agrees with the code actually running.

The memoised default parameter-reading authority is a second real defect, and it
is outside this row's scope paths. It is keyed on its two path arguments alone
and caches a fully constructed validated authority for the life of the process.
Measured: after the tree's complete fingerprint had demonstrably changed, a
second call returned the identical object and never re-consulted the tree. The
sanctioned load entry point re-collects the fingerprints on every call and keys
its own cache on them, so this site bypasses the only invalidation the authority
has. It is the path-only cache above the loader that the authority-flow rule
names. Reported to the campaign lead for enrolment rather than fixed here.

Regression coverage lands as three tests. The first is structural and cannot
regress quietly: a mutable tree deposits no cache entry at all, asserted
alongside the bundled tree still depositing one so it cannot pass by the cache
being inert. The second is the warm-regime proof, built rather than assumed: a
real green validation verdict is persisted on disk for the pre-edit fingerprint
key, the compiled cache is confirmed to still hold the pre-edit payload under
the pre-edit key, and the pre-edit fingerprint entry is planted with a live
stamp so it is maximally fresh by construction -- no sleep, no window, no
machine-speed dependence. The load must still return the edited value, and the
persisted verdict must no longer certify the tree. The third runs the same
construction in a child interpreter with the pytest markers removed, the
production regime where the cross-process compiled pickle is live, and asserts a
pickle was written for the pre-edit tree before the edit so the warm artefact is
confirmed present rather than presumed.

The bite proof was taken from outside the repository: a plugin on the
interpreter path reinstates the superseded directory-only freshness check
without modifying any tracked file. Under it the structural test and the
warm-regime test both fail, the latter reporting the pre-edit casilla value
where the edited one is required. The production-regime test is unaffected by an
in-process plugin; its bite is the pre-fix measurement itself, which returned
the pre-edit value in that exact regime.

Type diagnostics for the fingerprints module and for its two binding sites in
the loader went to zero. The live-lookup alias declared positional parameters
for a callable that takes keyword-only ones, so every call site was reported by
all three checkers; a protocol declaring the real signature removes the whole
family. No new diagnostic was introduced anywhere.

The suite delta is zero regressions. Because the tree was moving under several
concurrent executors, the pre-change arm was reconstructed on the identical
working tree by reverting the fix at runtime through the same external plugin,
so the comparison isolates this change from every peer edit. Both arms ran
sequentially over every registry test module that touches the loader, the
fingerprint cache, the compiled cache, the authority or the validation verdict.
Eleven failures are common to both arms and therefore untouched by this change;
two failures appear only in the pre-change arm, and those are this step's own
two gates, which is the bite proof. No failure appears only in the post-change
arm.

The eleven common failures were classified rather than waved through. Ten are one
class: synthetic fixtures declaring a legal review status whose vocabulary has
since been tightened, so they fail during fixture construction. The eleventh is
a fragment-size ratchet on the campaign-owned Modelo 303 tree. None is
cache-related in mechanism, and none is this step's to fix.

That classification carries a finding worth recording. Two of those failing
tests are precisely the pre-existing coverage for this row's subject -- one
names fingerprint-backed process caching and invalidation, the other names
authority cache invalidation when a fragmented revision changes. Both have been
failing at fixture construction, before reaching any invalidation assertion. The
invalidation property they are named for has therefore been unproven on this
tree, which is part of why the defect measured here could persist unnoticed.

This step consumes no entry from the plan's deletion inventory. It is
measurement plus a correctness fix, and nothing was deleted.

## Notes

The clean form of the fix leaves the mutable window constant and the parameter
that carries it unreferenced by any logic. Removing them touches the loader
module, which a concurrent executor held modified throughout this work, so the
parameter is retained at the boundary and its removal is handed to the campaign
lead as a coordinated follow-up together with the exact call sites. A dead
wrapper for the same collector, with no caller anywhere, was found in the same
module and reported for the same reason.

The registry suite could not be collected at the start of this work: an
unrelated in-flight rename in the persistence key package broke an import chain
the registry test configuration pulls in, so no test ran. It cleared while the
fix was being written. The pre-change failure set was therefore reconstructed by
running the suite against the same tree with the fix reverted at runtime through
the same external plugin, which isolates this change from every peer edit landing
concurrently.

The unbounded parameter-authority cache and the bundled window are both reported
upward as findings rather than actioned here, in keeping with the one-row scope.

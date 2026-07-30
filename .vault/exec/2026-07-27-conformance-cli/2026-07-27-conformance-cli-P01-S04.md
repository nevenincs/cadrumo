---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S04'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# add governance-stamp loader tests covering roundtrip, fail-closed default on absence, refusal of incoherent stamp combinations, and an anti-tautology mutation proof

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_governance_stamp.py`

## Description

- Add a governance-stamp test module driving the real directory loader over real on-disk TOML, with no test double anywhere.
- Cover the fail-closed default on absence, the full-stamp roundtrip, both incoherent combinations, an unknown status token, a misspelled key, and the fragment-placement refusal for every governance field.
- Build two anti-tautology proofs into the module: a full-stamp rewrite that must flip every previously passing assertion, and a one-line deletion that turns the same loading tree into a refusal.
- Pair the placement refusal with a differential proof that byte-identical stamp text is accepted from the manifest and refused from a fragment.
- Verify the module's teeth by mutating production code three ways and confirming exactly the expected assertions fail.
- Enroll the new core enum in the compiled-cache embedded-symbol list, a gap this Step's verification uncovered.

## Outcome

The governance stamp now has gates that fail when the behaviour is removed, which
was verified by removing it rather than assumed.

Files: `src/cadrumo/domain/calculations/registry/tests/test_governance_stamp.py`
(new, 18 tests) and `src/cadrumo/domain/calculations/registry/_compiled_cache.py`
(absorbed fix, described below).

Anti-tautology. The Step asks for a mutation proof, and a proof that merely kills
a fixture would be weaker than one that flips an assertion, so both were done. Two
proofs live inside the module and therefore run on every future execution. The
first asserts a fully populated stamp, rewrites all four scalars on disk, reloads,
and asserts strict inequality against each previously passing expectation; a
schema default could never satisfy it because the values must move with the bytes.
The second deletes a single reviewer line from a tree that has just loaded
successfully and asserts the reload refuses. The mutable-tree fingerprint is
content-sensitive, so a rewrite genuinely re-keys the loader cache rather than
being served a stale compile, and the inequality assertions would themselves catch
it if it were not.

Beyond the in-module proofs, the production code was mutated three separate ways
and the suite re-run each time, restoring between passes. Neutering the fragment
placement gate failed exactly the four per-field placement tests and the
differential placement test, five in total, with the other thirteen still passing.
Short-circuiting the coherence validator failed exactly the six coherence tests,
covering both refusal directions plus the deletion proof. Flipping the schema
default away from the pending member failed the absence test, the implicit-pending
refusal, and the bundled-tree invariant test, which incidentally proves the
bundled-tree test is not vacuous. After each mutation the production files were
restored and confirmed byte-identical to their committed state.

The bundled-tree test asserts the invariant rather than today's all-pending
distribution. Asserting the distribution would lock in a fact the stamping campaign
this feature enables is meant to change, so the test instead asserts that a
reviewed revision names its reviewer and date while a pending one names neither,
and refuses an empty revision set so it cannot pass on a tree that failed to load.

Absorbed in-scope fix. Verifying this Step surfaced a real gap created by the
schema change two Steps earlier. The compiled registry cache keys on a hash of
every registry-package source plus an explicit list of core types embedded in the
pickled compiled objects, and the module's own comment asks that a newly embedded
core type be enrolled. Adding the review status made the new enum exactly such a
type: every revision now pickles a member of it, while the enum is defined outside
the registry package. A probe confirmed both halves of the gap, that the enum
appears in the pickled payload and that its defining file was not among the files
folded into the key, so adding a member or changing a value would have altered
compiled semantics while the key stood still and a stale cache was served.
Enrolling it closed the gap, measured by mutating the enum's defining file and
watching the fingerprint move, then restoring and watching it return to its
original value.

Verification. `ruff format --check` reported the module already formatted and
`ruff check` reported `All checks passed!`. `pyright` reported
`0 errors, 2 warnings, 0 informations`; both warnings are the shared-support
private-import pattern that the sibling loader-fragment module already carries in
the same form, so this is the established convention rather than a new violation.
The module runs green under the repository's default marker selector, which
matters because that selector silently collects nothing from integration-marked
modules and would report a meaningless pass: `18 passed in 3.20s` with no marker
override, and `18 passed in 9.42s` with an explicit empty selector. The cache
fingerprint suites returned `10 passed in 49.14s` after the absorbed fix and the
race-sensitive cache isolation module returned `11 passed in 41.71s`. The wider
P01 scoped run across the governance, schema, schema hygiene, both loader
modules, cache isolation, compiled cache, disk-cache fingerprint, authority,
registry schema parts one and two, orden aplicabilidad, and TOML parity modules
returned `292 passed` alongside the two race failures discussed below.

## Notes

Semantic discovery ran under an explicit operator waiver, with `rg` concept sweeps
and whole-file reads standing in for the stopped code index.

The cache isolation pair raced a peer twice. Both times the failure was two
distinct disk pickles written across two real pytest sessions, and both times a
peer had committed a registry-package source file within roughly a minute of the
run. Because the cache key hashes every non-test file in that package, a peer edit
genuinely moves the key between two subprocess sessions. Re-running the module
each time once the peer file settled returned `11 passed`, so the failures are the
race and not a regression. This Step's own new file is a test module and is
excluded from the hashed set, so it cannot cause the race itself.

One incident is worth recording because it nearly left a mess. Two production
files were patched during the mutation passes with a small Python script rather
than the editor, and on this platform that rewrote line endings from LF to CRLF
across a whole file. The content comparison against the committed state was clean,
because the repository normalises line endings, so a naive check would have called
it restored while the working tree carried a fully rewritten file that would have
churned every peer diff touching it. It was caught by comparing raw bytes against
the committed object rather than trusting the diff, and the file was restored to
its committed bytes exactly. The new test module was normalised the same way
before it was committed.

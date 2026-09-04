---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:2047f241cdf63dc0f31c8bb12443ccf15321c9b19933dd927e572dfbe8e6436f'
step_id: 'S56'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Close the generator assertions the wheelhouse refusal was hiding

## Scope

- `packaging/scoop/tests/test_scoop_generate.py`

## Changes

- `M` `packaging/scoop/tests/test_scoop_generate.py`
- `M` `packaging/homebrew/tests/test_homebrew_generate.py`

## Notes

All three assertions were gate defects; neither generator changed.

The Scoop manifest installs by name at an exact version from the index, so no
filename can appear in its install hook. Three assertions still demanded one,
and only the first was ever reported because it aborted the test. The rewrite
pins what the adopted design does guarantee -- the exact-version requirement,
the cache and constraint flags -- and closes the companion chain by reading the
built root wheel's own metadata. The cohort's filename and digest binding is
genuinely no longer provable through that manifest, and no assertion was
invented to pretend otherwise.

The excluded client library had a recorded reason: it belonged to a separate
distribution the formula does not install. Folding that workspace member into
the main package retired the reason and made the library a mandatory
requirement of the distribution the formula does install. Excluding it
generator-side would ship a formula missing a dependency, since each resource
installs without its own dependency resolution.

The build-backend comparison drew its expectation from every locked row, a set
far wider than the formula's contract, so an unrelated development pin governed
a build backend and moved with every lock refresh. It now asserts the
properties that must hold -- an immutable digest-derived index address, an
archive, a name that normalises to the resource -- and that every declared
backend is emitted with no fourth escaping. Two further restatements of the
same constants were removed with it.

## Scope

- `packaging/scoop/tests/test_scoop_generate.py`

## Changes

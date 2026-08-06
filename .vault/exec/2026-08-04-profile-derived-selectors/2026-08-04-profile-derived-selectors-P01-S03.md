---
tags:
  - '#exec'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:c5309e060bbc1731fd84199f1955e1183134abea6634d61fe126f355e08e92a0'
step_id: 'S03'
related:
  - "[[2026-08-04-profile-derived-selectors-plan]]"
---

# Retire the dormant selector-level as-of field, its two populated registry declarations, and the presence-only assertion that blesses it

## Scope

- `src/cadrumo/domain/calculations/registry/_bindings.py`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/`
- `src/cadrumo/application/modelo/tests/test_profile_binding_real_path.py`

## Description

## Outcome

The dormant selector-level as-of channel is retired. `rg` across the source tree returns
zero matches for the field after the change, against exactly four before it.

The executor re-confirmed the prior measurement independently before deleting anything, as
instructed: two semantic sweeps by meaning found no consumer under any other name, and a
literal search found exactly the four known sites — the model field, the two registry
declarations, and the test's defensive access with its assertion. Nothing was missed, so
the deletion proceeded.

Four files formed one semantic unit: the field on the selector model, the two
marital-status binding declarations that populated it, and the test line that asserted its
presence. The assertion was removed outright rather than left as a defensive access that
would silently read nothing forever.

Process deviation, recorded rather than glossed. The executor did not land its own commit.
While it was mid-verification a shared-worktree incident occurred and a bulk sweep
committed all outstanding in-flight work tree-wide, splitting this change across two of
those sweep commits. The executor verified its diff landed byte-for-byte in each, confirmed
both are ancestors of the current head, and confirmed no foreign content interleaved. This
is the no-pathspec sweep pattern the project's commit discipline exists to prevent, and it
is noted here so the deviation is visible in the record even though the outcome was clean.

Gates, all at the post-sweep head: tree-wide collection clean with zero errors, confirmed
both before and after the sweep. The registry binding and profile suites passed at 457.
The profile-binding real-path module passed at 11, run three times. The full modelo
application suite passed at 1426 under reduced parallelism and 1428 sequentially. The
registry suite passed at 3466.

Transient failures on the first full-parallelism pass were correctly triaged rather than
reported as regressions: two registry cache-fingerprinting races, a directory-fragment
inventory mismatch, a crashed worker, and one missing-legal-reference assertion naming the
sibling campaign's articles. None touched any file in this Step. Reduced-parallelism and
fully sequential re-runs came back clean, matching the project's own guidance that registry
suite failures under parallel pytest are more often a loader-cache race than a regression.
Coordinator confirmation: the registry now loads and both of the sibling campaign's new
parameters resolve, so that assertion has since cleared.

Not verified: the full source tree beyond collection, deliberately out of scope for this
Step and declined while the machine was under heavy concurrent load.

## Notes

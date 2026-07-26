---
tags:
  - '#audit'
  - '#compatibility-enrollment-deadlock'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - "[[2026-07-26-compatibility-enrollment-deadlock-adr]]"
---

# `compatibility-enrollment-deadlock` audit: `triage of the vacuity screen worklist`

## Scope

One triage pass over the full `dev/audit/vacuity_screen` worklist, classifying every
flagged function into the screen's own three classes: legitimate-absence,
off-module-guarded, and genuine missing-proof. The governing decision record required
this pass and required the genuine hits to become work rather than remain a standing
worklist nobody reads.

The screen flagged 32 functions across 230 test modules, not 35 — the earlier figure
counted output lines including the header. Every classification below rests on reading
the flagged function body and, where the verdict turned on it, its siblings. Semantic
search was not used: the code index was serving 222 chunks against ~4,600 files at the
time, and the operator had held the rebuild so other campaigns kept the GPU.

## Findings

### Class C, genuine missing proof — 9 functions, all fixed

Each asserted an empty violation set while iterating a corpus that, had it been empty,
would have produced exactly the same clean result. None could distinguish a measured
pass from a blind one.

Three shapes recurred. Four gates iterate a committed literal inventory
(`CORE_STRUCTS`, `_HARDENED_ERROR_KEYS`, `_OPERATOR_ERROR_LOCALE_KEYS`,
`_BOUNDARY_ROUNDTRIP_INVENTORY`) — an emptied literal is a visible diff rather than
silent rot, which is why these rank lower than the burned-gate class, but none proved
it scanned. Four gates in the docs tree key on `user_scope_source_pages`, a discovery
call that genuinely can return nothing; the language axis was guarded by sibling
assertions while the page axis was not. One walks the source tree for API stubs with no
assertion that any module was found.

Fixed by adding one proof-of-scan assertion per corpus: a truthiness or membership
assertion that fails when the walk returns nothing. Sites: `dev/docs/tests/test_api_stubs.py`,
`dev/docs/tests/test_docs_catalogue_drift.py`, `dev/docs/tests/test_docs_localization.py`
(three functions, one shared page corpus), `src/cadrumo/tests/test_docstring_core_struct_links.py`,
`test_locale_coverage_hardened_errors.py`, `test_locale_coverage_inventory.py`, and
`test_roundtrip_coverage.py`. Screen count fell from 32 to 22.

### Class B, off-module or in-test guarded — 9 functions, no work

Emptiness of the corpus would fail loudly elsewhere, which the screen's own docstring
classifies as not-a-finding.

Four `test_locale_translation_honesty` gates read the real catalogue YAML directly, so
an absent corpus raises rather than passing; two of them additionally have their
detector's proof pair in the same module. Three `test_registry_locale_key_parity` gates
are covered by a sibling that pins the scanned key count at a hard 86, which is a
concrete-corpus assertion. `test_generic_module_modelo_carveouts` reddens with "named
ratchet module missing" if its inventory does not contain the modules its baseline
names — an in-function proof of scan. `test_utc_validator_enrollment_inventory` consumes
the shared production AST substrate, whose emptiness fails the inner-envelope gate's
`test_the_governed_surface_is_not_empty`, which asserts concrete known paths are present.

That last one is the weakest of the nine and is recorded as such: the guard lives in a
different tree, so it holds today but nothing declares the dependency.

### Class A, legitimate absence — 13 functions, no work

Absence IS the property under test, or the empty assertion is the accept half of a
proof pair.

Three are deletion or retirement proofs (`_decimal.py` deleted, the retired `aeat`
package root absent, a missing env file returning empty). Two are `returncode == 0`
subprocess checks that the screen's zero-compare pattern catches as a false positive by
construction. Four are in-test setups that create the artefact and then assert its
removal or non-creation, so the corpus is present by construction. Four are the accept
halves of detector proof pairs — a synthetic clean input asserted to produce no
offenders, sitting beside synthetic violating inputs asserted to produce offenders.
Those last four are the shape the screen most reliably mis-flags, because a proof pair's
negative case is indistinguishable from a blind assertion by pattern alone.

### A limitation of the screen, found during the pass

`proves_it_scanned` is evaluated at MODULE level: a single proof-of-scan assertion
anywhere in a module clears every flagged function in it. That is why nine added
assertions cleared ten functions. In `test_roundtrip_coverage` the co-cleared function
scans the same corpus as the guarded one, so the clearing is legitimate there. But the
mechanism can launder a function that scans a DIFFERENT corpus from the one the module's
single proof covers, and the screen does not distinguish them.

This is a genuine over-clearing risk in the opposite direction from the over-reporting
the docstring already declares, and it is not among the four shapes that docstring says
the screen cannot see.

## Recommendations

Do not promote the screen to a CI gate. Its two declared false-positive classes are
real and were the majority of this worklist — 22 of 32 flagged functions needed no work
— so a gate would cry wolf at a 69% false-positive rate. It stays a screen, run at the
swarm-audit cadence.

Consider narrowing `proves_it_scanned` from module scope to function scope, accepting
the resulting increase in false positives, since a false positive costs one read and
the over-clearing above costs a silently unguarded gate. Not done here: it would
re-flag functions this pass has already classified, and the re-triage should be
deliberate rather than a side effect.

Treat the four accept-half proof-pair hits as the screen's known blind spot when
re-running it. They will re-flag every time and are correct as written; a future pass
should not "fix" them by weakening the pair.

The nine Class C fixes assert only that the corpus is non-empty. That is the property
the screen names, and it is strictly weaker than proving the corpus is COMPLETE. A gate
whose discovery call silently narrowed from 400 pages to 3 would still pass. Closing
that gap needs a per-corpus expected-floor, which is a larger decision and is not taken
here.

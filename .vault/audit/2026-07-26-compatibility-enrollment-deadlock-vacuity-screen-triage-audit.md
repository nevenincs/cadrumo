---
tags:
  - '#audit'
  - '#compatibility-enrollment-deadlock'
date: '2026-07-26'
modified: '2026-07-26'
body_hash: 'sha256:cf7db0529f23e0a63d477cf990889e496a9513d838a5d2550418aea3fd73785a'
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

### Re-triage after narrowing the exemption, and what the first pass under-measured

The limitation above was acted on rather than left recorded, and measuring it showed
the first pass had under-stated it. Module-wide credit was silencing 110 functions —
more than five times the 32-item worklist it was hiding them behind, so the majority
of the screen's true population was invisible when the first triage ran. Any
conclusion above about proportions is therefore about the visible tenth, not the whole.

Dropping module credit entirely was tried and rejected on evidence: 274 flagged,
mostly ordinary behaviour tests, which is not a worklist anyone reads. The credit is
now matched by CORPUS NAME — a sibling asserting the shared substrate is populated
still vouches for scans over that substrate, and no longer vouches for one it never
touched. That preserved every existing screen test unchanged, which is the signal
that it narrowed the credit rather than redefining it.

A second gap surfaced immediately: `proves_it_scanned` read only names and calls, so
`assert Settings.model_fields` did not clear its own gate. A guard that does not clear
the hit teaches its reader that guarding is pointless, which is the fastest way to get
a screen ignored. Attribute and subscript reads now count.

Of the 110 surfaced, 30 genuinely walk a corpus. Eleven are now guarded, and the
serious ones are worth naming: both CLI reference gates enumerate the live command
tree through a subprocess, so an empty walk meant every command was documented and
every leaf had a schema; the shipped-module gate calls itself a hard zero with no
baseline and no allowlist while walking an unguarded tree; the production-module
coverage gate and the test-topology gate both scan trees that, empty, report no gaps
and no misplacement. Each guarded corpus was measured non-empty rather than assumed —
1370 production modules, 1509 reachable, 253 facades, 787 discovery sites — so the
guards are satisfied by measurement, not by construction.

Thirteen corpus-walking hits remain unguarded, and roughly 84 further hits are
absence assertions, subprocess exit codes and ordinary behaviour tests needing no
work. The list is not closed and this says so.

## Recommendations

Do not promote the screen to a CI gate. Its declared false-positive classes are real
and remain the majority of the worklist, so a gate would cry wolf. It stays a screen,
run at the swarm-audit cadence.

The narrowing this pass recommended has been DONE, and by corpus name rather than by
dropping module credit — see the re-triage section above for why the wholesale form
was rejected on measurement.

Treat the four accept-half proof-pair hits as the screen's known blind spot when
re-running it. They will re-flag every time and are correct as written; a future pass
should not "fix" them by weakening the pair.

The nine Class C fixes assert only that the corpus is non-empty. That is the property
the screen names, and it is strictly weaker than proving the corpus is COMPLETE. A gate
whose discovery call silently narrowed from 400 pages to 3 would still pass. Closing
that gap needs a per-corpus expected-floor, which is a larger decision and is not taken
here.

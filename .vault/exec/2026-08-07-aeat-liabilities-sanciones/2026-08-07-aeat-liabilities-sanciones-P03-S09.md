---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:8a12aca704091f7e2e1bacea5ff56365ceab9610cb4ed9cbf6b1ffc576902e54'
step_id: 'S09'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---
# Write the guard unit test proving refusal on every synthetic landing URL including a payment-shaped and an aplazamiento-shaped URL against the empty prefix set, then a mutation proof populating one real-looking prefix and confirming it permits only that prefix

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/tests/test_deudas_read_landing_guard.py`

## Description

Wrote the guard proof: refusal across every synthetic landing shape, a positive
control, and a runtime mutation proof.

## Outcome

Modified files:

- `src/cadrumo/adapters/outbound/aeat/sede/tests/test_deudas_read_landing_guard.py`
  (new)
- `src/cadrumo/tests/aeat_literal_fixtures.py` (declared landing-shape canaries)

15 tests: the allow-list ships empty; every payment- and aplazamiento-shaped
landing is refused; a plausible read-shaped landing is refused too while no
specimen exists; an unreadable or origin-less landing is refused; an off-host
landing is refused; and the policy declares no drivable browser action.

A positive control carries the weight of the whole file. "Every URL is refused"
is not evidence on its own, because a guard refusing for an unrelated reason --
a rejected host, a malformed policy -- would satisfy it identically. The
control drives the SAME shared guard with a populated single-entry tuple, a
real argument to the real function rather than a patched module, and shows it
admits exactly that prefix while still refusing the payment sibling beside it.
That attributes the blanket refusals to the empty allow-list specifically.

## Verification

15 tests green:
`uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/sede/tests/test_deudas_read_landing_guard.py`.
Commits `9009926158` then `6032667d3c` for the canary centralisation.

The mutation proof ran from OUTSIDE the repository: a scratch script widened
the prefix tuple to a permissive value in memory and re-ran the file. No
tracked file changed, so no peer sweep could commit the mutation and a crash
would leave no residue. Result: 6 failed, 9 passed, exit 1. Restored by ending
the process; the file re-ran 15 green immediately after, and `git status`
confirmed no modification residue under `src`.

## Notes

The proof caught a flaw in its own first attempt. The initial run reported 15
PASSED under the mutation -- a false all-clear, because the plugin applied the
mutation in the pytest controller while xdist runs tests in separate worker
PROCESSES that never saw it. The tell was that
`test_the_allow_list_ships_empty` should have failed and did not. Re-run
single-process, it went red properly. Recorded because any in-memory mutation
proof in this repository is silently vacuous under the default parallel
configuration.

The mutation also produced a substantive safety finding. Under a fully
permissive allow-list the two literal "Pagar..." paths were STILL refused,
because the policy's canonical write-verb token scan catches "pagar" -- but the
pago-parcial, solicitar-aplazamiento and aplazamiento-fraccionamiento shapes
were PERMITTED. The token scan knows none of "pago", "aplazamiento" or
"fraccionamiento". The empty allow-list is therefore the only wall refusing
three of the five payment-adjacent shapes, which raises rather than lowers the
cost of populating it casually once a specimen exists.

The test file first owned its own AEAT host and route literals and reddened
`test_test_suite_aeat_route_literals_are_centralized_or_declared` with 13
offenders, all mine. Fixed by declaring the shapes as canaries in
`aeat_literal_fixtures.py` beside the censal ones, with the comment stating
plainly that these differ in kind: the censal canaries are observed AEAT paths,
these are SHAPED, because no specimen exists.

---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:887d5fdab61c7fc0b267b9cec720b1cba2a8ebd5df78d095aa52e4f754c4583d'
step_id: 'S107'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---
# Give each aliased fixture behaviour one canonical home and one name preserving per-site lifecycle

## Scope

- `src/cadrumo`

## Description

- Read the body-keyed census verdict for the surviving aliased behaviours rather
  than a fixture tally.
- Adjudicate each surviving pair on whether the bodies are genuinely
  substitutable, before giving either a shared home.
- Give each behaviour one canonical home and one name, keeping every per-site
  lifecycle axis — name, scope, autouse reach and the bucket a body closes over
  — declared where it applies.

## Outcome

**The requirement is met: `aliased behaviours=0` across 499 fixtures.** The
detector built two rows earlier reported thirteen; five survived the correction
that added the module values each body closes over; the last two are closed
here, and every one of the thirteen was adjudicated rather than waived.

**Pair one, the bundled authority.** `bundled_authority()` was written out under
`authority` in the dev tree and `registry_authority` in the package. Both now
bind `bundled_registry_authority_fixture(name=...)` from a canonical home in
`src/cadrumo/tests/`, which the dev tree already reaches by an established route
— `dev/` imports `cadrumo.tests.*` support at a dozen existing sites, and the
reverse direction stays forbidden.

A **third** site had the same body and the census could not see it.
`test_conformance_profile.py` imported the function as
`load_bundled_authority`, and an import alias changes the body's AST dump, so a
body-keyed grouping reads the identical call as a different behaviour. Worth
carrying forward as a property of the instrument rather than of this pair: the
census sees through a copied body but not through a renamed import, so
`import X as Y` is a blind spot in exactly the tool built to find copies. The
alias is gone and the site joins the other two.

**Pair two is the case that must NOT be merged naively, and is the reason this
row is not a mechanical sweep.** Two suites each open an isolated runtime and
yield a `TransactionCatalogueRepository`. The bodies are identical and they look
interchangeable only because each closes over its own module-level
`_BUCKET_ID` — `2828…` in aggregation, `4444…` in overview. Folding them onto
one shared bucket would have put two suites on one bucket-scoped master-key
session, and every test would still have passed. `bucket_id` is therefore a
REQUIRED argument of `bucket_scoped_transaction_catalogue_fixture`, never a
default, and the docstring states why so the next reader does not
helpfully add one.

**One design choice the instrument forced, and it was right to.** The authority
factory first carried a `scope` argument. The census then refused the fixture
outright: a scope passed as a variable is unresolvable to any static reading,
and it declines to state a value it cannot determine rather than guess. All
three callers want module scope, so scope is fixed at module and the knob is
gone. A refusal that costs a speculative parameter is the gate working.

## Verification

- Census verdict `aliased behaviours=0`, 499 fixtures, factory-bound 38 → 43.
- 382 tests collect across every changed module with no fixture-resolution error.
- The aggregation and overview suites run green apart from the tree-wide
  `RegistryValidationError` that predates this row; the aggregation log shows
  the catalogue saved under bucket `2828…`, which is the per-site bucket the
  factory was required to preserve.
- A dev-tree consumer requesting `authority` reaches the fixture body and fails
  inside it on that same registry refusal — not on a missing fixture, which is
  the wiring proof.

## Notes

**What this row does not deliver, stated rather than left to inference.** The
fixture-ownership manifest gate could not be run to a verdict. It is fail-closed
against a moving source universe and refused twice, naming different peer-edited
files each time — `_record_design_ir.py`, `_modelo_bindings.py` and
`test_invoice_currency_exclusion_advisory.py` on the first attempt, `_oss_ioss.py`
and two registry loader files on the second. The aliasing verdict above comes
from the census itself, which does not need a still tree; the manifest's
substitutable-duplicate verdict still needs one clean regeneration in a quiet
tree. That is the same external blocker recorded under the census row, not a new
one.

**A performance claim was available here and is deliberately not made.** Three
routes to the bundled authority — this factory, `resources().modelos.authority`,
and a direct call — resolve through one memo keyed on the registry and
source-evidence fingerprints. Measured in one process: 30.0s, then 2.6s, then
0.025s and flat, handing back the identical object each time. Consolidating the
fixture bodies therefore saves no load time whatsoever; what it consolidates is
how many places the behaviour is spelled. The real cost is the single 30-second
first load per process, which belongs to the registry compile-and-validate path
and not to this row.

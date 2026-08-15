---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:c59faff78855e5c4cc013024a52aebad9225ec1cc8f0b7fea6b0f4ab61537ec8'
step_id: 'S109'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh extend the re-export bridge and orphan detector to walk the test tree, since it currently skips it entirely and a whole class of orphaned export module is therefore invisible, which is how an adapter export survived its only consumer's deletion with zero importers anywhere

## Scope

- `dev/quality/import_hygiene_scan.py`
- `src/cadrumo/tests/test_import_hygiene_gate.py`

## Description

- Establish which of the two premises in the row is true at HEAD before
  editing, since the bridge detector and the orphan detector are named
  together but are not in the same state.
- Build the orphan detector the motivating incident actually describes, and
  make its verdict sound by widening the reach census rather than by
  suppressing what it reports.
- Classify every finding by judgement.

## Outcome

The row's scope path does not exist. There is one scanner,
`dev/quality/import_hygiene_scan.py`; `dev/import_hygiene_scan.py` is not
present at HEAD and no second copy exists anywhere. The row named a stale path,
and the architecture rule's citation is the correct one.

Of the row's two halves, one was already done and one did not exist at all.
The re-export bridge detector already walks the test tree: it tags every hit
with `is_test`, its own docstring records that an early `continue` past test
modules made the family's reach narrower than the rule it enforces, and a gate
named for that behaviour already pins it. It reports ten test-tree bridges
today and zero production ones. So the premise "it currently skips it entirely"
is stale for that half, and nothing needed changing there.

The orphan detector did not exist. Nothing in the scanner asked whether a
module has any importer at all, which is precisely the question the motivating
incident poses. That is what was built.

Two families landed, because the defect has two ends and a check that sees one
reports the other as clean. Family 9 finds a module nothing reaches. Family 8
finds the opposite end — an import naming a first-party target that no longer
resolves — and is the subject of the paired ruling recorded separately.

The orphan verdict's soundness turned out to rest entirely on the breadth of
the reach census, and each narrowing was found by measurement rather than
reasoning. A census scoped to the shipped package alone reported
`src/cadrumo/tests/declared_command_risk.py` as orphaned; it is imported by the
harness distribution and by development tooling, both outside that scan root.
A census counting only import statements reported four more, each reached
through a string the import graph cannot follow — the lazy CLI command table,
a subprocess module target, and two path-assembling test probes. The census
therefore spans the package, the harness distribution and the development tree,
with each tree resolved against its own source root, and counts static imports,
dynamic `importlib` targets and any string constant naming the module.

The bias here is deliberate and one-directional, and is documented in the
detector: counting a coincidental string as reach costs a missed orphan, while
missing a real reach reports a live module as dead, and that is the verdict
somebody acts on by deleting it.

After that, two orphans remain and both are genuine, with no reference of any
kind anywhere in the tree:
`src/cadrumo/adapters/persistence/storage/master_key/_bucket_identity.py` and
`src/cadrumo/core/storage_route_guidance.py`. The second states in its own
docstring that "several boundaries attach" its recovery text; those boundaries
are gone. Neither is a re-export bridge, and both sit in another lane's files,
so both are reported for routing rather than fixed here.

The gate is scoped accordingly. The orphaned-re-export-bridge subset is gated
at hard zero, which is clean today and is the subset the no-standing-bridge
rule already forbids outright — a bridge owning no behaviour with no importer
forwards nothing to nobody, and there is no reading under which it is
dormant-but-intended. The wider "defines its own things" subset is reported and
not gated, because a dead module and a module whose consumer has not been
written yet are the same shape, and that judgement is not one a gate is
entitled to make. No count and no ceiling is asserted anywhere.

Bite proof, run entirely outside the repository so no tracked file was
mutated: the real scan inputs were read, one synthetic defect appended in
memory, and the gate's own assertion re-evaluated. Family 9 reported zero
orphaned bridges on the untouched tree and reported the planted bridge when one
was introduced. The census-width claim was proved the same way — narrowing the
census to the package alone manufactured exactly the false orphan named above,
so the widening is load-bearing rather than decorative. Family 8's two bite
proofs are recorded with the paired row.

## Notes

Family 8's export half declines to judge a PEP 562 lazy facade, because such a
facade binds names no AST walk can enumerate. Nineteen of the package's 258
facades resolve lazily. This was found the honest way: the first bite proof
planted a dropped export against `cadrumo.core` and did not fire, which looked
like a broken detector and was in fact the documented decline working. The
proof was retargeted at an eager facade and fires there. Declining is correct —
a detector that guessed would report every lazily-resolved export in the
codebase — but it is a real coverage boundary and is stated wherever the gate
is cited rather than left to be discovered.

An early build of the same detector understood only plain `Name` assignment
targets and reported eleven hits, of which seven were one pair of loader
collectors bound by tuple unpacking. Each binding form that produced a measured
false positive — tuple unpacking, PEP 695 `type` aliases, annotated
assignment, `for` targets, import aliases — is now pinned as its own gate case,
so the surface walk cannot narrow again.

HEAD moved five times during this work. One of those commits swept the four
live dangling imports that family 8 had been measuring, so the family's floor
went from four to zero underneath the measurement. The final numbers are from a
re-measurement at the later HEAD, not from the earlier run.

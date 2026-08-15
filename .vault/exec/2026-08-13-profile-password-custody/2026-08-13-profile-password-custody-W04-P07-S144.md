---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:67d7c935401651e64982e16f69cd27a7ec00fa09c8b00e1bbbd104a4477fe320'
step_id: 'S144'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule whether a deletion landing without its consumer sweep should be mechanically detectable, since three separate removals in one session each shipped the deletion in one commit and the consumer repair in another or not at all, blocking collection tree-wide for every agent until somebody noticed, which makes the split the norm on this tree rather than the exception

## Scope

- `.vault/audit/2026-08-15-profile-password-custody-deletion-without-consumer-sweep-detectability-audit.md`
- `dev/quality/import_hygiene_scan.py`
- `src/cadrumo/tests/test_import_edge_integrity_gate.py`
- `src/cadrumo/tests/test_import_hygiene_gate.py`

## Description

- Rule on detectability, honestly, including the possibility that the answer
  is "a working mechanism already exists and the gap is elsewhere".
- Measure the existing mechanisms rather than reading their configuration and
  assuming they work.
- Build only what the ruling justifies.

## Outcome

The ruling is that the split should be mechanically detectable, that it can
only be detected by a check seeing the whole tree at once, and that the gap is
neither capability nor enrolment but a third thing: the mechanism with full
capability is red at rest and therefore cannot bite. The reasoning, the
measurements and the evidence are in the audit; what follows is what changed in
the tree.

The question was posed as capability-versus-enrolment and the honest answer is
neither. Capability exists: the type checker runs over all of `src` with
`allowed-unresolved-imports = []` and `all = "error"`, which makes every
unresolved import a hard failure, and it reaches both `TYPE_CHECKING`-guarded
edges and production modules no test imports. Enrolment exists too, and more
than the row's framing credited: the type check is a `prek` hook with
`pass_filenames = false`, so whole-tree rather than changed-file, and also a CI
step; the full-corpus collectability proof has its own CI job,
`cadrumo-test-harness`, not merely a `just` recipe nobody runs.

What was measured is that `check-types` exits 1 with 283 diagnostics. Four of
them were a live deletion-without-sweep — a CLI test importing four names the
bucket facade no longer exports. The mechanism saw the defect, reported it, and
the defect shipped. A ratchet at 283 goes from red to red when a new defect
arrives; there is no verdict change for anyone to act on.

So the build is an extraction, not a second mechanism. The single question
"does every first-party import target still resolve" was measured at zero on
this tree and can therefore be gated at zero, which restores the property the
broad checker has lost. That is family 8 in the scanner. Family 9 gates the
opposite end — a module nothing reaches — because the defect breaks an edge and
a check that sees one end reports the split as clean half the time. Family 9 is
the paired row's subject and is recorded there.

Both bite proofs for family 8 were run from outside the repository: the real
scan inputs were read, one synthetic defect appended in memory, and the gate's
assertion re-evaluated, so no tracked file was mutated and a crash would have
left no residue. The family reported zero dangling edges on the untouched tree,
reported the planted import of a deleted module, and reported the planted
import of a dropped export. Both kinds are also pinned as synthetic-tree cases
in the gate suite, along with five binding forms and one lazy-facade decline
that each began as a measured false positive.

Neither plan row is checked here. Family 8 is gated at hard zero and green;
family 9's bridge subset is gated at hard zero and green; two non-bridge
orphans and one uncovered reference channel are reported for routing rather
than absorbed.

## Notes

The row's premise reproduced twice more during the work, which is why the audit
treats it as primary evidence.

`26ba385a83` deleted the setup package and a filing module while leaving their
generated documentation stubs behind; those stubs were removed only in
`de045bd45a`, so between the two commits the nitpicky documentation build
carried stubs for deleted modules. The same commit left two `dev/quality/*.toml`
census files naming deleted source paths, and both were still dangling a day
later at `f964f2062a`.

The second reproduction is subtler and worth recording on its own. The
four-name bucket-export defect was repaired in `f964f2062a`, whose subject is a
registry export-layout sweep across nine modelos. The repair is real and
correct. But a CLI test's import fix shipped inside an unrelated registry
commit, so nothing in the history connects the repair to the removal it
answers. The split is invisible in the commit record as well as in the gates,
and a broad sweep subject is how it gets there.

That commit also landed while the measurement was running, taking family 8's
floor from four to zero underneath it. The numbers reported here are from a
re-measurement at the later HEAD.

One conclusion is deliberately not drawn. This work did not touch the standing
type debt, and as long as `check-types` sits at 283 diagnostics it will keep
detecting defects that ship. Families 8 and 9 are the part of that problem that
could be made to bite now, not a substitute for fixing it.

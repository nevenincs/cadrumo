---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:7174ba0b6cfe28b61a3e21cb7535a33d7b1b2e4bcbc2db18814385efac6425a5'
step_id: 'S53'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh stop the supervised key-derivation child from importing the custody package graph to perform one hash

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/_kdf_worker.py and src/cadrumo/adapters/persistence/storage/custody/_kdf_supervision.py`

## Description

- Reproduce the measurement independently before changing anything, and locate
  where the cost actually lives rather than where the symptom appears.
- Convert the facades whose eager graph the child was paying for, preserving one
  canonical home per symbol and changing only WHEN a module executes.
- Pin the result as a property of the child's module table, never as a wall-clock
  budget.

## Outcome

The cost was in neither file this row names, and finding that is the substance of
the step. Importing the worker's own codec alone cost two seconds while importing
the top-level package cost under two tenths, so the expense was the parent
package initialisation chain that Python executes for ANY submodule import --
the database toolkit, the object mapper, encrypted columns, the blob store, the
shared-master package and the bucket layer, none of it reachable from a single
hash. The row named the files where the symptom appears; the cost lived in the
facades above them.

Four conversions to deferred module attributes, three of them generated
mechanically from each facade's own import block and verified faithful by proving
the generated export set matched the declared public surface exactly in both
directions. Nothing was duplicated: one canonical home per symbol, one import
path, only the execution moment moved -- which is the sanctioned instrument, and
the project's rule permits it precisely where eager import cost is shown to
matter.

Verified independently on this host rather than accepted: the worker's import
falls from 1.711 seconds to 0.497 seconds, and the storage facade from over two
seconds to 0.058. The author's controlled same-process A/B against the
reconstructed old graph reads 1.123 against 0.463 seconds, a stable ratio of
about two and a half, with the absolute saving LARGER under load -- which is the
condition the multi-minute suites were measured in.

The security parameter is provably untouched. The diff against every file
defining a key-derivation parameter is EMPTY, so no parameter can have moved, and
the fallback still reads sixty-four mebibytes at three iterations. Supervision,
child isolation, the ready-before-secret handshake and the framed-result
discipline are all unchanged. This is the outcome the row demanded: the time came
out of the import, not out of the cryptography.

The new gate asserts the PROPERTY -- that the child's module table excludes the
database toolkit, the HTML parser, the blob store, the envelope layer and the
shared-master package -- deliberately not a wall-clock budget, which would be
flaky on a loaded host and would fail for reasons unrelated to the import graph.
It carries a floor so the exclusions cannot pass vacuously, and a companion
proving the probe still observes a forbidden import. It bit for real on its first
run, naming the HTML parser, which is how the last leak was found.

## Notes

Two genuine pre-existing import cycles surfaced once the eager ordering stopped
concealing them, and both had to be closed for the tree to import at all. They
are exactly what the separately-recorded concern about deferred imports
predicted: a deferred import postpones a cycle rather than removing it, and these
had been held at bay by evaluation order alone. Their emergence during a routine
conversion is the evidence, not a side effect.

Completeness was proven rather than asserted: every first-party module was
imported, sixteen hundred and ninety-seven attempted with zero failures, and
every exported name still resolves through the three converted facades.

One number was deliberately NOT claimed. Wall-clock on the shared host is
load-dominated with several suites running concurrently, so cross-time comparison
of the handover suite would have been meaningless, and the author declined to
report an improvement they could not defend. The controlled subprocess
measurement is the honest signal.

The residual half second is mostly the core facade's eager graph, which is
nine hundred and fifteen lines and already partially lazy, so it resists the
mechanical conversion used here. It is carried as its own row because every
process imports that facade, so the payout extends well beyond this step.

The change reached HEAD inside another campaign's commit about retiring the
recovery-phrase surface, which swept all six files including the untracked gate
before this step could stage them. Content verified present and green at HEAD.

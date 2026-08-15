---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:f8288a1e015d30bfa86000785ea4d3c36587233acbc161e668c29bec610e1b3b'
step_id: 'S84'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh resolve the deterministic identity-anchoring refusal in the isolated storage-root reaping test, which reproduces alone in seconds and is therefore neither an ordering nor a parallelism artefact, the unconfirmed hypothesis being that it anchors on a storage root whose parent directory was never materialised where the passing sibling tests anchor on an already-existing path, and establish the mechanism by measurement rather than adopting that inference

## Scope

- `src/cadrumo/adapters/persistence/storage/tests/`

## Description

- Reproduce the refusal in isolation and capture the full call chain from the test body
  down to the failing system call.
- Replicate the production component walk in an out-of-repository script that reports
  the Win32 error per component, across four path shapes, instead of collapsing every
  failure into one opaque refusal.
- Run the counterfactual: the identical body with the storage root materialised.
- Establish which side is wrong by reading what production requires before it can reach
  the mint at all, and by comparing against every passing sibling.
- Re-found the test on a materialised root and add an anti-vacuity assertion that the
  receipt actually landed where the teardown discovers it.
- Prove the corrected test bites by neutering the teardown at runtime from outside the
  repository, and revoke the credential the neutered teardown left behind.

## Outcome

The measurement first, since the row explicitly forbids adopting its own inference.

The refusal is a plain file-not-found on the final component of the anchored walk. The
custody anchor opens every component of the directory it is about to write into, from
the drive root outward; the walk reaches the storage root, asks the operating system for
a handle on it, and is told the path does not exist. Every component above it opens
cleanly. The refusal is raised on the last one.

Four shapes were measured. With the storage root absent and its own parent present - the
failing test's exact shape - the walk refuses at the final index, on the storage root
itself. With the storage root materialised, the walk completes with no refusal. With the
storage root and its parent both absent, the walk refuses one component earlier, on the
parent. With a real parent and the absent child the anchor is asked to create, the walk
refuses on that child.

So the row's stated hypothesis does not hold as written. It supposed a storage root
whose parent directory was never materialised; the parent is present and anchors
cleanly, and the third measured shape shows that a genuinely absent parent produces a
refusal at a different component. What was never materialised is the storage root
itself. The hypothesis is right in substance under the other available reading - the
anchor target is the parent of the keystore child being created, and that target is the
root - but the literal claim about the root's parent is refuted by the walk. Recording
both readings rather than choosing the flattering one.

The counterfactual settles causation. Running the identical body twice, differing only
in whether the storage root is created first, the absent-root run refuses at the anchor
before any credential is written, and the materialised-root run mints, writes the
receipt, custodies the key, and has it revoked on context exit. Nothing else varies.

The test is the wrong side, and this is not a close call.

Production cannot reach a mint through an absent root. The mint is called from one
place, inside the candidate-promotion window of the login flow, and by then the password
envelope has been loaded from a directory under the root, a bucket session is open, and
the handover journal has already been written under the root. All three require it to
exist. The row's own alternative - that production refuses a legitimate root - would
need production to produce this shape, and it cannot.

The refusal is also correct by design rather than incidental. The directory primitive
documents that it takes a single child of an existing root and is deliberately not a
recursive convenience function, because a recursive walk restores the check-then-create
window it exists to close. Teaching custody to materialise the root on demand would
trade a real substitution defence for a test's convenience.

Every passing sibling confirms the boundary. The custody roundtrip cases pass the
temporary directory itself as the root, which exists. The user-profile handover cases
and the CLI session-lifecycle cases each create their root explicitly before use, nine
and three sites respectively. The failing case was the only one anchoring on a root
nobody had made.

The re-founding therefore materialises the root in the test, which is what the helper's
consumers do when they do not drive profile creation - the helper yields the root's
location, and creation is what ordinarily brings it into being. A second assertion was
added because the original could have passed vacuously: the teardown discovers profiles
by scanning the root's capsule directories, so a receipt that never landed there would
leave it nothing to find and nothing to fail on. The test now proves the receipt is
present before asserting the credential is gone after.

The corrected test bites. Neutering the teardown at runtime, patched from outside the
repository so no tracked file changed, reds it on its own subject: the credential
survives the context exit. The proof revokes the orphan it created rather than leaving a
permanent entry in the host's credential store.

## Notes

- A secondary defect was found and not fixed, because it lies outside this row's
  ownership. The shared helper's own docstring promises an empty real storage root, and
  it yields an absent one. The prose is what invited the failing test's assumption.
  Roughly forty call sites depend on the helper, almost all of which drive profile
  creation and so never notice, which is why the correction was made in the test rather
  than in the helper. Raised for routing.
- The generic wording of the refusal was considered and deliberately left alone. It does
  not distinguish an absent directory from a substituted one, which reads as poor
  diagnostics but is the right posture for a fail-closed identity anchor: the message is
  not an oracle for what an attacker replaced.
- The storage test package carries substantial ambient red from concurrent work -
  missing public exports from the master-key surface, schema-lineage floor drift,
  sensitive-surface inventory drift, and runtime-route guards. Thirty-four failures
  under per-file isolation, none in this row's file, none absorbed here.

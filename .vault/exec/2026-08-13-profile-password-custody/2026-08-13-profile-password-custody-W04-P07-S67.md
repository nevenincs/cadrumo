---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:f0da2016ea1c094256702f72dee451c4c3a04c2f0474377153fa465cd90b6181'
step_id: 'S67'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh delete the retired workspace-initialisation package in one atomic commit, its entry point being an unconditional refusal with no callers kept alive only by two string references, re-homing the four genuinely valuable tests it hosts onto the package that owns active-profile registration and deleting the typing test that keeps a retired contract alive, the atomicity mattering because removing the package without updating both string references reds the import-smoke inventory

## Scope

- `src/cadrumo/application/setup/ and src/cadrumo/tests/test_layout_import_smoke.py`

## Description

- Ground the row's four claims against the package read whole before touching anything.
- Delete `src/cadrumo/application/setup/` entire: `__init__.py`, `_contracts.py`, `_service.py`, `tests/__init__.py`.
- Re-home four test modules onto `src/cadrumo/application/user_profile/tests/`, repointing the two cross-package imports that reached the setup package's sibling onto the owning package's own facade.
- Rename the vague `test_cli.py` to `test_first_run_config_cli_surface.py` in its new home.
- Delete `test_contracts_output_language_roundtrip.py`, whose only subject was the retired command contract.
- Drop `cadrumo.application.setup` from the canonical layout import inventory in `src/cadrumo/tests/test_layout_import_smoke.py`.
- Drop the setup service entry from the scanned-path table in `src/cadrumo/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`, whose gate reads each named file's text and would raise on the deleted path.
- Regenerate the API stubs, retiring three setup stubs and the `application` toctree entry.

## Outcome

Three of the row's four claims held exactly. The entry point was an unconditional
refusal that discarded its argument and raised before any work. It had no
production callers: the only occurrences of `initialize_workspace`,
`InitializeWorkspaceCommand` and `InitializeWorkspaceResult` outside the package
were vault prose and one stale generated-manifest row. And the split of tests was
four-move, one-die, as claimed.

The claim that did NOT hold is the count of string references. The row said two;
the live set at execution time was five distinct surfaces. Two are Python gates
inside the test suite and are the two the row meant: the canonical layout import
inventory, and the scanned-path table in the CLI custody-lifecycle gate, which
reads each named path's text and would have raised rather than merely asserted.
Both were swept. The remaining three are outside the pytest testpaths: the
generated API reference stubs (three files plus a parent toctree entry), and two
generated manifests under the development quality tree. The API stubs were
regenerated through the owning tool. The two manifests were deliberately left
alone and are reported below.

Per-test classification, made from what each module proves rather than from the
row's tally:

- `test_atomic_create_rollback.py` proves a refused credential-registration create
  commits no capsule, writes no pointer and leaves no label projection, and carries
  its own anti-tautology partner proving the success path lands exactly those
  artifacts. Its subject is the live registration door. MOVED.
- `test_atomic_create_roundtrip.py` proves one profile created through the canonical
  atomic provisioner reads back with a consistent identity across list, show, login,
  duplicate, export and import. Subject live. MOVED.
- `test_first_run_config_cli_surface.py`, formerly `test_cli.py`, proves the
  operator-facing first-run configuration surface exposes the profile and auth
  lifecycles and refuses an unsupported provider. Subject live. MOVED.
- `test_event_emission_contract.py` pins the file-and-symbol identity of three
  required bucket-event emission sites, two of which live in the destination
  package, and floors its own scan corpus so a relocation cannot make it pass
  vacuously. Subject live. MOVED.
- `test_contracts_output_language_roundtrip.py` proves only that the retired
  command's language field is enum-typed. Its subject is the retired contract
  itself, so it dies with it rather than carrying a dead assertion into a live
  package. DELETED.

Verification. A full collection sweep was run before finishing. The four re-homed
modules collect fourteen unit tests in their new home plus two integration tests,
and no collection error names any path in this Step's scope; the single collection
error in the run belongs to the locale parity gate, which another agent holds and
which fails on a missing symbol in the locale tooling. The destination modules and
both swept gates were then executed sequentially. The emission-contract gate passes
green in its new home, and its bite was proven by patching the file reader at
runtime from a plugin outside the repository so the capsule-record module appears
to have lost its bucket-created emission: the gate reds on exactly that assertion
and returns to green when the patch is removed. No tracked file was modified for
the proof and the working tree carried no residue afterwards.

## Notes

Twelve tests are red across the executed set and none is attributable to this Step.
Seven sit in two of the re-homed modules and five in the CLI custody-lifecycle
gate. Every one fails because a CLI verb is absent or because profile creation
through the wizard path now refuses; the refusal string and the absence of the
duplicate, export and passphrase verbs were both already true of the commit
immediately preceding this Step's landing, and the git rename detection records two
of the four re-homed modules as moving with zero content change and the other two
with a single import line each. The failures are the in-flight custody cutover
showing through, and they were equally red at the old location.

The commit token was held elsewhere, so this Step's change was left complete in the
working tree rather than committed by its executor. It was landed by another
session, bundled with concurrent peer work, under a commit retiring the setup
package and folding its tests into the profile package, with the regenerated stubs
following in a paired documentation commit. The landed content is this Step's work
rather than an independent parallel deletion, and the commit itself is the evidence:
rename detection records the four valuable modules moving at ninety-eight to one
hundred percent similarity, the two atomic-create modules carrying exactly the
one-line facade repoint each that this Step authored, the renamed CLI-surface module
byte-identical, the typing test deleted with no rename pair, and the two consumer
sweeps present at the exact line counts this Step removed.

A second verification pass was run against the tree three commits later, because the
subject had been committed out from under the working copy and a landed change is
only worth as much as its state at head. The re-derivation confirmed the retirement
is atomically complete. Both in-suite string references are gone. A sweep of every
non-vault surface — the whole source tree, the development tree, the built
documentation, the build manifest and task file, and the agent harness data — finds
the package named nowhere except the two generated quality manifests already
reported. The three retired symbols survive only in one of those same manifests.
Separating genuine deletions from renames confirms nothing valuable was dropped:
every module this Step classified as MOVED has a rename pair, and the only test
deleted outright is the one classified as DELETED. The import-smoke inventory, the
emission-contract gate and the integration rollback proofs run green together at
head.

One difference from what this Step authored is a peer improvement layered onto the
re-homed emission-contract gate in the same commit: the profile-values-updated
member moved from the tracked-gap tuple into the required-emission table, pointed at
the wizard persistence module, with a needle naming the emission rather than the
bare symbol precisely because a bare symbol is satisfied by the module's own prose.
That is a strengthening of the gate by its wizard-side owner, not damage from the
move, and it passes.

Two generated manifests under the development quality tree still name the deleted
package: a fixture-ownership record for a fixture that moved with its module, and a
recovery-rehoming ledger row pointing at a line number the deleted service had not
had for some time. Neither is inside the pytest testpaths, so neither reds the
suite. Both were left untouched on purpose: the fixture-ownership regeneration
already refuses on this tree because peer agents are mutating filing, operations and
registry sources concurrently, so regenerating it would have swept unrelated peer
work into this Step's change. They need a regeneration pass once the tree is quiet.

The API stub regeneration is tree-wide, not change-scoped. It also retired two
registry stubs and one filing stub and emitted three new registry stubs belonging to
other agents. Those were left in place for their owners rather than reverted.

The head-state collection sweep reported two errors, both in the calculations
fidelity suite and both reading as the registry directory changing during cache
fingerprinting while concurrent registry writes were in flight — the tree's head at
the time was itself a registry sweep commit. Re-collecting those two modules
sequentially yields twenty-three tests and a clean exit, which is the loader-cache
race the local-execution discipline predicts rather than a regression, and it has no
relationship to the retired package.

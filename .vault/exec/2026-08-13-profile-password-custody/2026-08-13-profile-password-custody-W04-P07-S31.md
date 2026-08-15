---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:3922d8c48c3e40140a532d6f52e18f2e7cc6916a8012aa5041a4fb2549303df0'
step_id: 'S31'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh fold the three unconstrained kibibyte Argon2 parameter models onto the ADR-canonical mebibyte custody record and dissolve the shared-bounds module whose only purpose was holding an import cycle open between two of them

## Scope

- `src/cadrumo/adapters/persistence/storage/`

## Description

- Ground the row's premise against the tree before folding anything, recording per model which
  unit it carries and whether it is genuinely unconstrained.
- Dissolve the package-level shared-bounds module into the canonical enrolment record that was
  its sole in-tree consumer, keeping every constant's value byte-identical.
- Re-point the storage facade's type-checking import and its lazy export map at the master-key
  facade, and export the Argon2 version marker from that facade.
- Re-point the on-disk `master.kdf` record's window import at the enrolment record beside it and
  drop the private-alias spelling, since the constants now have one public home.
- Regenerate the API stubs so the removed module's orphan stub cannot crash the next nitpicky
  autodoc build.

## Outcome

**The row's fold did not happen, and it must not.** All three models were located and read; none
is promotable onto the mebibyte custody record. The substitutability pre-filter is decisive
against every one of them, and for two of them the conversion would strand operator ciphertext.
The bounds-module dissolution, which is the row's second half, is delivered in full.

**Per model, the unit each actually carries.**

The canonical mebibyte record is `ProfileCustodyKdfParameters` in
`src/cadrumo/adapters/persistence/storage/custody/_records.py`. Its accepted set is a finite
grid: memory in `{19, 32, 64, 128, 256}` MiB, iterations in `{2, 3, 4, 6, 8, 10}`, parallelism in
`{1, 2, 4}`, a canonical-base64 16-byte salt, and a 32-byte output. The accepted decision states
that grid verbatim.

Model one, `KdfParams` in `src/cadrumo/adapters/persistence/storage/master_key/_kdf_params.py`,
carries kibibytes. Its floor is `19 * 1024` KiB, which is 19 MiB exactly, and its ceiling is
`1024 * 1024` KiB. Iterations run 2 to 16 and parallelism 1 to 8, both continuous. It is NOT
unconstrained: it already reads a validated window, and its floor equals the custody grid's
weakest point. It produces no weaker derivation.

Model two, `_KdfParameters` in
`src/cadrumo/adapters/persistence/storage/master_key/_master_key_records.py`, is the on-disk
`master.kdf` wire record. It carries kibibytes under exactly the same window, read from the same
declaration. It too is already constrained, and produces no weaker derivation.

Model three is `EncryptedProfileBundleExport` in
`src/cadrumo/application/user_profile/_bundle_encryption.py`. It carries kibibytes and it is the
one model that is genuinely unconstrained: `memory_cost`, `time_cost` and `parallelism` are bare
integers with no bound, and `salt_b64` carries no length rule. Its read path hands all four
straight to the Argon2 derivation helper.

**The weaker-derivation finding, stated first because it outranks the refactor.**

Only model three can express a below-floor parameter set, and it can express an arbitrarily weak
one: one kibibyte, one iteration, a one-byte salt. That is the same pair of defects the on-disk
record's own docstring records as having been closed on its sibling, reproduced verbatim on a
third surface.

The honest severity is a hardening gap, not a live weakening of operator data. The write path
always stamps the canonical default, so every bundle this application emits sits at the OWASP
floor; and a tampered envelope's weak parameters only reproduce a key the tamperer already chose,
because the authenticated-encryption tag still gates the plaintext. What is lost is that a
re-exported envelope can circulate as an application-grade encrypted bundle while being
brute-forceable, and that a short salt escapes as a raw third-party hashing error rather than a
typed refusal. The module is outside this row's scope line and outside this executor's declared
ownership, so it is reported to the dispatching agent for assignment rather than edited here.

**Why no model folds: the substitutability reasoning.**

The pre-filter asks whether the target's constraint shape is a superset of the candidate's. It is
not. The custody record carries constraints none of the three carry: a closed literal grid on all
three cost axes, a canonical-base64 string salt with an exact length rule, and a literal output
width. Its accepted set is strictly NARROWER on every axis than the kibibyte window: five discrete
memory points against a continuous range, six discrete iteration counts against 2 through 16, and
three parallelism values against 1 through 8. A superset was required and a strict subset is what
exists, so every one of the three sites is excluded by the filter on its own terms.

The prior investigation row had already reached the same conclusion from the derivation side: the
custody worker varies its output width and version per stored parameters while the master-key
derivation fixes the output width and has no version axis. Divergent, not nested.

Two independent hard stops sit behind the filter, and either alone would refuse the fold.

First, narrowing strands data. Both master-key models validate parameters that already exist on
operator disk. An enrolled store at 24 MiB, or at parallelism three, satisfies the kibibyte window
and satisfies no point of the mebibyte grid. Folding would make that store unreadable.
Key-management caution is explicit that this class of change is owner-gated, and the creation path
here does not mint only grid-compatible values, so the confirmation that would permit removal does
not hold.

Second, the unit change is a wire change. The `master.kdf` document persists a field named
`memory_cost` holding kibibytes. Re-typing it as mebibytes reinterprets every already-written
document by a factor of 1024 with no marker distinguishing the two readings, so a stored 19456
would read as 19456 MiB. The pre-capsule stores this record serves hold real operator ciphertext,
and their retirement is deliberately ordered behind two still-open rows precisely because of that.
The same argument applies to the bundle-export envelope, which is a transport record with an
exact-equality version gate and no upgrader.

No cryptographic parameter was weakened anywhere. Every constant moved carries its original value;
the floor stays at the OWASP baseline; nothing was relaxed to make a conversion fit.

**The bounds module, and the cycle it was said to hold open.**

The module's own docstring stated its reason for existing: two records described the same
parameter set from different sides, and the manifest-side record's package could not import the
master-key package without closing a cycle, so the constants were parked in a neutral
package-level module.

That cycle no longer exists. The manifest-side record was deleted by earlier work in this
campaign, which the enrolment record's docstring already recorded. A tree-wide search confirmed
the module had exactly one in-tree consumer left, the enrolment record itself, plus one facade
re-export of the Argon2 version marker. A module holding a seam open between two parties, one of
which is gone, is a vestige rather than a seam.

So the cycle was not broken; it was already absent, and the dissolution is a straight move. The
constants and the two single-valued literal types now live in the enrolment record beside the
model that reads them, and the on-disk record beside it reads them from there. Both readers are
inside one package, so no cross-package edge exists to become a cycle. No deferred or
function-local import was added anywhere, and none was needed. The removed module leaves no
reference behind in source, in the generated reference, or in the harness.

**Verification.**

The custody and master-key suites, the capsule-lifecycle and active-profile-resolution suites, and
the hard-cutover absence gate ran together: 320 passed, one failed. That one failure is the
pre-declared, already-red detector-vocabulary test tracked by a separate row; its assertion
compares an unrelated symbol name set and is unchanged by this work.

The wider storage suite reports 39 failures. None is attributable here: every failing module was
checked against the symbols this row touched and none references them, the dominant cause is the
bucket-directory-creation refusal another row is actively working, and the single module that did
mention a key-derivation default asserts against a file this row never opened, which contains no
key-derivation code at all. This was established by attribution rather than by a clean run at the
pre-change baseline, which is stated plainly because the two are not the same evidence.

The linter and formatter are clean on every changed module. The type checker reports three
diagnostics across the two packages, all in test modules this row did not touch. The generated
reference was regenerated; the only stub delta belonging here is the removal of the dissolved
module's orphan stub and its toctree entry.

A runtime check confirmed the relocated constants resolve identically through both the storage
facade and the master-key facade, and that the canonical default still materialises the OWASP
baseline unchanged.

## Notes

The three-model premise in the originating row is partly stale: two of the three were already
constrained by earlier work in this campaign, and only the bundle-export envelope remains open.
That one is outside this row's scope line, so it is reported rather than fixed, and it is the
finding that should outlive this record.

The row's instruction to fold is not followed, and deliberately so. The evidence refuses it on the
pre-filter, on data-stranding grounds, and on wire-format grounds independently. Recording the
mismatch is the sanctioned outcome when folding is unavailable; forcing the conversion would have
required either weakening a cryptographic parameter or making already-written operator ciphertext
unreadable.

The dissolved module's constants now sit in a module that is itself part of the retired
shared-master surface. That is intentional co-location rather than an oversight: when that surface
is deleted by the rows already scheduled for it, the window goes with the only records that read
it, instead of leaving a package-level orphan behind.

Peer commits landed over this worktree mid-run and absorbed these changes into their own sweeps.
Nothing was committed from here.

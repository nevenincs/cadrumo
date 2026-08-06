---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:96b9f27cac3d97a0d2ff883daaefdaf0b7c42ad1c05eeb1f335758ea83236c14'
step_id: 'S51'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# eliminate the fake-named bindings from the sanitizer residual-identity test, reconcile the test-debt baseline the same test broke, and replace the bare encoding literal in the legal attribution screen

## Scope

- `src/cadrumo/adapters/inbound/sanitizer/tests`

## Description

- Rename the sanitiser's planted specimen identifiers from the banned
  fake-prefixed names to `_PLANTED_NIF` and `_PLANTED_IBAN`, values unchanged.
- Record at the declaration why the name avoids the test-double vocabulary, so
  the next reader does not rename it back.
- Route the same module's `SRC_CADRUMO` import onto the `cadrumo.tests` public
  facade instead of its private inventory submodule.
- Declare a module-local UTF-8 constant in the legal attribution screen and use
  it at the catalogue read.

## Outcome

Three failures, two owners, and in both cases the gate was right and the code
was wrong. Nothing was allowlisted, ratcheted, or baselined.

### The sanitiser control was misnamed, not misconceived

Two of the failures came from one module, the sanitiser's residual-identity
gate, which proves scrubbed artefacts carry no leftover personal identifier.
The tree-wide test-double ban flagged its two planted identity constants
because their names began with the banned prefix.

Read against the code, those constants are the opposite of a test double. They
are checksum-valid identity values planted into a specimen that the real
`sanitize_pdf` then processes; they are what makes the module's absence
assertions non-vacuous, and the module's own docstring calls them the live
positive control. Deleting them would have hollowed out the gate. The defect
was purely the name: the banned vocabulary reads as substitution, and these
substitute for nothing.

They were renamed for what they are rather than what they are not, and the
choice pairs them with the `_SYNTHETIC_` values the sanitiser writes in their
place, so the specimen's before and after sides now share one vocabulary. The
declaration carries the reasoning, because a bare rename invites a later reader
to revert it as cosmetic.

### The test-debt ruling

The same module reached its package-root constant through the private inventory
submodule, a cross-package private import that pushed the test-debt ratchet to
58 over an allowed 57 and tripped both the count ratchet and the named-set
equality assertion.

The baseline was NOT grown, and the decision was not close. The owning package
already exports that constant in its `__all__`; the import was simply not using
it. The gate's own failure text names this exact resolution and prefers it. So
the import moved onto the facade, the violation stopped existing rather than
becoming tolerated, and the ratchet stays at 57.

The general reasoning stands on the ratchet's meaning. That file is a set of
individually reasoned dispositions for private reaches with no sensible public
promotion; an entry asserts that no facade route exists. Adding one here would
have recorded a false claim, and it would have moved the ratchet's floor
permanently upward for a defect that took a one-line fix. A ratchet entry is a
debt admission, and there was no debt to admit.

The facade route was checked before it was taken: the package initialiser's
eager imports are stdlib-only and introduce no cycle with the adapter package,
and its lazy attribute hook exists to keep a heavy parser out of the import
graph, which this constant does not touch.

### The dev encoding literal

Independent of the other two and pre-existing. The screen carried a bare
encoding literal at its catalogue read. The gate prescribes a different fix for
dev tooling than for shipped code, because dev tooling must not import the
shipped package's internals, so the constant is declared module-locally. Every
sibling screen in the same package already does exactly this. The comment
records why the constant is local rather than shared, since that asymmetry is
otherwise unexplained.

### Verification

All three gates failed first and were captured. The mock-inventory gate named
both constants by line. The UTF-8 gate named the one dev line and reported zero
ratcheted files. The import-hygiene pair reported 58 current against 57
documented, and named the private reach as the single undocumented site. All
four ran; none were deselected into a false green.

After the fix all four pass, and the sanitiser package and all three gate
modules pass whole, 105 tests, so no sibling assertion was disturbed.

The control was then proven still live rather than merely still green. Driven
directly, the planted pair is flagged jointly and individually, while values of
identical shape with broken checksums are not flagged at all, which shows the
specific values remain load-bearing rather than the pattern alone. The
end-to-end leg still finds genuine sanitiser output clean against the manifest
the sanitiser itself emitted. The edited dev screen was also run end to end and
reads its full catalogue through the changed line.

## Notes

The first attempt at the mutation probe was invalid and was redone. It patched
the planted values in the specimen's raw bytes, which only reached the
uncompressed metadata surface because the generator compresses the content
stream, so detection persisted and would have been misread as the values not
mattering. Rebuilding the specimen through the module's own generator gave the
clean result. Worth recording because the flawed probe failed in the direction
that looks like a finding.

One observation outside this Step's scope and deliberately not acted on: the
legal attribution screen's docstring states that four filing-grade citations
are mis-attributed today, and the screen now reports zero. The zero was checked
against an empty-scan explanation and is a real negative, with all registry
modelos carrying citations and the approving-provision detection resolving
normally, so the prose appears simply to have outlived the legal-authority work
that corrected those citations. Correcting the narrative is legal-authority
work and belongs to that owner.

Code review was not dispatched from here, as this executor has no delegation
tool available in its harness. The review remains required before the Step is
treated as closed and is handed back to the dispatching agent.

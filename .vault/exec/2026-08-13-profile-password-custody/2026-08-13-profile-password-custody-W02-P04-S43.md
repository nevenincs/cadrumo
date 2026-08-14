---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:e26175a079f28a0a5e3070c411e00c12971b9cc584f580931d9dfe7ea7e77935'
step_id: 'S43'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Have Terra XHigh re-root the hard-cutover absence gate across the whole application layer, teach it to read dynamic and attribute-string import targets and to flag a private-submodule reach, anchor its scope proof to the layer directory independently of the scan root, and declare each remaining live reach so the entry expires when its replacement lands

## Scope

- `src/cadrumo/application/tests/`
- `src/cadrumo/application/overview/tests/`

## Description

- Relocate the absence gate from `src/cadrumo/application/user_profile/tests/` to
  `src/cadrumo/application/tests/`, the narrowest boundary that owns an
  application-layer-wide assertion.
- Re-root the scan from one package to the whole application layer, 531 production
  modules, and argue in the module docstring why the package tree is not the root.
- Make the module reach the primary net: report any import resolving into
  `adapters/persistence/storage/master_key` whatever symbol it names, across static
  `ImportFrom`, plain `Import`, an imported package NAME, `import_module` string
  targets positional and keyword, relative targets, `__import__`, the spec finders,
  submodule paths and attribute chains.
- Keep the provider-name list as the second net, and read `getattr` string arguments
  against it, since a `getattr` argument is a symbol rather than a module path.
- Add a third net reporting a reach into a private submodule anywhere under the
  persistence-storage substrate.
- Anchor the scope proof to a tracked fixture in a sibling package, and enumerate
  packages recursively at every depth rather than direct children only.
- Declare each of the seven live reaches with a stated replacement, every declared
  reach required so the staleness check can expire it.

## Outcome

The gate covers the application layer instead of one package, and the module net
carries the load the name list could not. A provider-family name list asserts only
"not these nine names"; what the forwarding port carries is the session seam, so
re-rooting alone would have left it passing. Four reaches surfaced that name no
retired symbol at all: the forwarding port, operator scoping, the language
resolver, and bundle export's raw Argon2id KDF import. Three more reach the provider
through the storage package facade without ever naming the package, which is why the
name net stays. The two nets catch disjoint sets and neither is a backstop for the
other.

An independent adversarial review returned revision required with three high
findings, all three now closed and each proven by a probe reproducing the review's
own demonstration.

The first was a declaration field that accepted findings without requiring them, to
straddle an uncommitted edit. Nothing checked it for staleness, so once that edit
landed it would have accepted the provider name forever on the one module at the
centre of the original false closure. The review asked for a second staleness rule
on that field; that would have closed the demonstrated hole while re-creating the
disease one level down, green against one tree state and red against the other. The
class was deleted instead. A finding accepted without being required is invisible to
a staleness check that can only expire what is required, so there is now one field of
reaches and a structural assertion over the dataclass fields that fails if a future
author reintroduces the same shape under another name.

The second was a scope proof that inverted on success: it required a declared reach
to exist outside the old root, so simulating a finished cutover red the gate, and the
standing pressure was to keep one violation alive to hold the proof up. It is now
anchored to a tracked fixture in a sibling package carrying one reach of each shape,
placed where it cannot execute. A fixture survives the cutover succeeding; a census
of live violations cannot.

The third was a matcher that missed the most idiomatic form of the reach, where the
package is named as an imported symbol rather than in the module path, along with
keyword targets, relative targets and several dynamic-import spellings. All are now
covered, verified across every production module in the layer with no new findings
and no false positives. Genuinely computed targets, built by f-string or
concatenation, remain uncovered and are documented as such rather than left under the
strong claim.

The review separately confirmed what mattered most: it tried to construct a wrong
scan root that still passes and could not, because the layer anchor is derived
independently of the scan root. The original defect is not reproduced one level up.

## Notes

Bundle export's import of the Argon2id parameters and KEK derivation is the
primitive rather than the provider seam, and is the least objectionable reach in the
layer. It is declared rather than excused, because judging a reach defensible is a
decision worth writing down and not a reason to leave it invisible.

Four reaches sit outside this root: two outbound tax-authority adapter modules, the
outbound Google OAuth flow, and the command-line profile-readiness check, the last of
which composes custody exactly as an application module does. The module docstring
names all four and records the exclusion as a real cost rather than a clean line.

The declaration entries express ownership as the required replacement in domain
terms rather than by naming the owning plan row, because source, comments, tests and
docstrings may not cite development records. That was ruled on explicitly rather than
assumed.

The declarations describe committed state, not the local working tree. An
uncommitted change to the forwarding port removes four provider names the
declarations still require, so the gate reads red on one assertion in a tree carrying
that change, and green against committed state and against the tree once the
declaration is updated. Both endpoints were verified. Declaring the working tree
instead would have red the shared state for everyone with no one able to fix it. The
change that lands those removals drops those four names from that one entry in the
same commit, leaving the module reach as the sole declared reach.

Two sibling gates share the defect class and were reported rather than fixed. The
shim detector skips every package initialiser outright, and its pure-re-export test
counts wrapper definitions as real definitions, so a forwarding layer written as
wrapper functions evades it by construction: the port carries 46 module-level
functions and 43 classes against 16 imports. A separate row owns that hardening.

The shared worktree was churning throughout. Test collection failed twice on peer
in-flight import errors in the custody capsule records and KDF codec modules, both
clearing on retry; the tree-wide import-hygiene gate carries six failures from peer
work; and the sibling package hosting the scope fixture carries failures from peer
legal-grounding work over review status on registry legal references. None is
related to this Step. Every commit was made by explicit pathspec so a peer's staged
content was never consumed.

---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:e6f7fcb0ed63e345c88e74866117b56b37c2b9b041334e41477c88a63312c342'
step_id: 'S43'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Have Terra XHigh re-root the hard-cutover absence gate across the whole application layer, teach it to read dynamic and attribute-string import targets and to flag a private-submodule reach, anchor its scope proof to the layer directory independently of the scan root, and declare each remaining live reach so the entry expires when its replacement lands

## Scope

- `src/cadrumo/application/tests/`

## Description

- Relocate the absence gate from `src/cadrumo/application/user_profile/tests/` to
  `src/cadrumo/application/tests/`, the narrowest boundary that owns an
  application-layer-wide assertion.
- Re-root the scan from one package to the whole application layer, 531 production
  modules, and argue in the module docstring why the package tree is not the root.
- Make the module reach the primary net: report any import resolving into
  `adapters/persistence/storage/master_key` whatever symbol it names, across static
  `ImportFrom`, plain `Import`, `import_module` string targets and submodule paths,
  normalising relative and absolute forms to one finding.
- Keep the provider-name list as the second net, and read `getattr` string arguments
  so a symbol laundered through a string is not invisible.
- Add a third net reporting a reach into a private submodule anywhere under the
  persistence-storage substrate.
- Anchor the scope proof to the layer directory rather than to the scan root, so it
  fails when the root is wrong instead of restating it.
- Declare each of the seven live reaches with a stated replacement, an anchor that
  must stay live, and a narrow landing window for symbol reaches that are mid-removal.

## Outcome

The gate covers the application layer instead of one package, and the module net
carries the load the name list could not. A provider-family name list asserts only
"not these nine names"; what the forwarding port in `profile_custody` actually
carries is the session seam, so re-rooting alone would have left it passing. Four
reaches surfaced that name no retired symbol at all: the forwarding port, operator
scoping, the language resolver, and bundle export's raw Argon2id KDF import. Three
more reach the provider through the `storage` package facade without ever naming the
package, which is why the name net stays.

Both tree states are green with the anchor still biting. The provider forwards in
the port are mid-removal, so an exact-match declaration would have red at HEAD and
passed a commit later. Splitting each entry into an anchor that must stay live and a
window that only provider-family names may enter keeps the gate stable across that
landing without going blind; a module reach cannot be parked in the window, and an
entry without an anchor is refused.

Nine deliberate breaks were run through a pytest plugin resident outside the
repository, patching reads at runtime so no tracked file changed. The two that matter
most: injecting an import that names only surviving session substrate reds the gate,
which no name list could have caught; and replaying the port's pre-edit content with
the landing window emptied reds naming all four provider forwards, which is what
stops the green run against that content from being vacuous. The remaining seven
cover a reach injected into a sibling package, both self-expiry paths, the scope
proof under a re-narrowed root, and the stated-reason requirement. Eleven tests,
under eleven seconds; ruff, ty and basedpyright clean.

## Notes

Bundle export's import of the Argon2id parameters and KEK derivation is the
primitive rather than the provider seam, and is the least objectionable reach in the
layer. It is declared rather than excused, because judging a reach defensible is a
decision worth writing down and not a reason to leave it invisible.

Two outbound AEAT adapter modules, the observation store and the Clave Movil client,
reach the retired surface and sit outside this root. They are flagged in the module
docstring as covered by the replacement work rather than silently exonerated, and are
not addressed here.

The declaration entries express ownership as the required replacement in domain
terms rather than by naming the owning plan row, because source, comments, tests and
docstrings may not cite development records.

Two sibling gates share the defect class and were reported rather than fixed. The
shim detector skips every package initialiser outright, and its pure-re-export test
counts wrapper definitions as real definitions, so a forwarding layer written as
wrapper functions evades it by construction: the port carries 46 module-level
functions and 43 classes against 16 imports. A separate row owns that hardening.

The shared worktree was churning throughout. Test collection failed twice on peer
in-flight import errors in the custody capsule records and KDF codec modules, both
clearing on retry, and the tree-wide import-hygiene gate carries six failures from
peer work that are unrelated to this Step. Both commits were made by explicit
pathspec so a peer's staged content was never consumed.

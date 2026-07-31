---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:75dbfeea16d80c6d5b5be8ee22d1f20c0627c4fffc69081f7734f459bfd74b87'
step_id: 'S40'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# take the filing-year grounding resolver off the public registry facade or rename it so it cannot be mistaken for the law-determined resolver, implementing the ADR ruling that currently has no code

## Scope

- `src/cadrumo/domain/calculations/registry/__init__.py`

## Description

- Confirm the defect at HEAD: the registry package facade exported
  `select_revision` and `select_revision_for_filing_year` as consecutive
  `__all__` entries, so the two resolvers stood side by side in one namespace
  under near-identical names.
- Enumerate every consumer of the evidence-attribution resolver across the whole
  tree before choosing a disposition.
- Rename `select_revision_for_filing_year` to `_select_revision_for_filing_year`
  in `_external_grounding.py` and update its single call site in
  `build_external_grounding_audit`.
- Rewrite the resolver's docstring summary line from a law-shaped phrasing
  ("Resolve the single revision applicable to a filing year") to an
  evidence-shaped one ("Attribute bundled oracle evidence of a filing year to
  one revision"), and record at the declaration why the symbol must stay
  private and what name shape a future cross-package consumer would require.
- Drop the symbol from the facade import block and from `__all__`.

## Outcome

The resolver is module-private to the grounding fold. The facade now carries
`select_revision` alone, so the two-resolver ambiguity the decision record names
no longer exists in any public namespace.

**Placement choice: private, not renamed.** The decision record offers two
dispositions - stay private to the grounding fold, or be exposed under a name
that cannot be mistaken for the law-determined path "if a cross-package consumer
genuinely needs it". A whole-tree search returned exactly four sites: the two
facade lines, one call site, and the definition itself. The call site sits 54
lines above the definition in the same module. There is no cross-package
consumer, no dev-side consumer, and no documentation reference, so the
conditional attached to the rename branch is unsatisfied. Renaming would have
left an unconsumed public export on a 429-entry facade - surface a reader must
justify, and a symbol that a future author could reach for precisely because it
is exported. Private is the disposition that removes the hazard rather than
relabelling it.

The docstring was widened rather than merely retitled. The rejected hazard is
not obvious from the signature: returning `None` is unremarkable until a reader
knows the sibling resolver raises, and that abstention is correct for a
governance fold reading captured evidence and wrong for anything that computes,
verifies, files, or exports. The reasoning now sits at the declaration, so a
future author promoting the symbol has to read the argument against doing so
first.

Verification, actually run:

- `rg` for the symbol across the whole tree returns two hits, both the new
  private name inside `_external_grounding.py`; zero hits under `dev/` and
  `docs/`.
- `ruff check` on both changed files: `All checks passed!`;
  `ruff format --check`: `2 files already formatted`.
- The re-pointed grounding gate plus the cross-module import-resolution gate,
  under the default selector: `3 passed in 64.29s`. Re-run unfiltered and
  serial (`-n0 -m ""`) to defeat the marker-selection false pass: `6 passed in
  37.77s`.
- Behaviour preservation measured, not assumed: importing the facade in a fresh
  interpreter reports `facade imports OK; __all__ entries: 429`,
  `select_revision_for_filing_year on facade: False`, `select_revision on
  facade: True`, and the live fold still yields `grounding audit rows: 90
  findings: 0 unmatched: 0` - the same 90 rows the earlier review recorded, so
  the internal call site resolves and the attribution behaviour is unchanged.

Landed as `9fb34585b3` over the explicit pathspec pair
`registry/__init__.py` and `registry/_external_grounding.py`.

## Notes

The mandatory semantic-discovery probe was WAIVED by explicit operator
direction for this step: the semantic index is broken and its service stopped,
with a standing instruction not to start, restart, or reindex it. Discovery was
carried by `rg` plus whole-file reads of the grounding module, the facade, and
both review records.

The facade carried live peer WIP at first read - a concurrent campaign's
addition of a manifest-only field set to the same file, two insertions. The
edit therefore went through the apply-cached gated drive rather than a pathspec
commit: a copy of the file at HEAD was taken, only this Step's two deletions
were applied to that copy, the resulting HEAD-anchored patch was staged with
`git apply --cached`, and the working tree was left untouched so the peer's
lines survived. The staged set was checked for the peer's marker immediately
before committing and returned zero, and the commit was made from the verified
index against an asserted file list.

The peer committed their change during that window. The staged patch rebased
onto their commit cleanly, because it carried only the two deletions and its
context lines were unaffected. Both were confirmed afterwards: the peer's field
set is present twice at HEAD, and this Step's commit shows two deletions and no
insertions in the facade. Neither campaign lost work; this is recorded because
the window between reading a shared file and committing it is real, and the
gated drive is what made the overlap harmless rather than a revert.

The API reference stubs were deliberately not regenerated. No module was added,
moved, or deleted, so the stub tree cannot have drifted from this change, and
the scaffold verb is tree-wide - running it here would have swept unrelated
peer modules into this commit.

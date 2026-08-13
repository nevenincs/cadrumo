---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:574ec58f776a97844f714a594ea7cccbd37b5022c18fab7e8620003301464012'
step_id: 'S04'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# run the full persistence and pydantic-model roundtrip suite to confirm the relocation changed no shape

## Scope

- `src/cadrumo/tests/`

## Description

- Confirm the five relocations are committed and the two emptied identifier modules are
  gone from the tree before measuring anything.
- Run a tree-wide collect-only and require zero error lines, per the Wave's stated release
  condition that a cross-package importer is invisible to both a symbol grep and a type
  checker.
- Run every persistence boundary declared in the roundtrip inventory, sequentially, with
  full output captured to disk rather than sliced through a pipeline.
- Run the identifier-facing structural gates alongside the boundaries: the hex-64
  redeclaration gate, the facade export gate, the cross-module import resolver, the frozen
  persistence records gate and the identity package's own suite.
- Triage every failure to an owner before reading anything into the result.

## Outcome

**The relocation changed no shape. That is the claim this row exists to test, and it holds.**

All twenty-six declared persistence boundaries pass: 373 tests green across the two runs.
That set includes every boundary a relocated identifier crosses - the encrypted SQL
repository, the domain modelos and domain invoices secure-storage roundtrips, the filing
history repository, the observations repository, the attachment store, the run-trace
persistence and the registry cross-boundary roundtrip. No roundtrip refused a value it
previously accepted and no strict-equality assertion moved.

Tree-wide collection is clean: 25095 tests collected, 4434 deselected, **zero error lines**.
This is the Wave's own stated release condition rather than a checker pass, chosen because a
cross-package importer that a relocation orphans is invisible to a symbol grep and to the
type checker, and that blind spot is what made this Wave ship a P0 twice. Both emptied
modules are absent from the tree and nothing imports them.

**Three failures surfaced. All three were triaged to an owner before this row was read as
green, and none of them is a shape change.**

*Peer-owned, storage refusal prose.* The envelope secure-bound repository test expects the
refusal to read "no active bucket session" and receives the bare locale key
`errors.storage.runtime.not_ready`. The storage runtime commit that removed the recovery
prose swept its sibling runtime test and missed this one, leaving an unswept casualty in an
active peer campaign. The surface carries no uncommitted work, so the failure is committed
state, reproducible, and squarely that campaign's to close. Not touched.

*Peer-owned, facade baseline drift.* The `__all__` regression cap has drifted across six
package initialisers - the filing and prorrata-register application packages, the corpus
manifest, the bienes-inversion domain package, and the CLI entrypoint and its config
subpackage. Several campaigns contributed. **The positive signal for this row is what is
absent from that list:** `core/identity` does not appear, which is the direct evidence that
the five relocations promoted their symbols into the facade and updated the baseline
correctly. Had a relocation been sloppy, this is the gate that would have named it.

*Owner-surface, and now rowed.* The hex-64 redeclaration gate is red on a single site, an
inline pattern on the M303 product-software evidence digest. This one belongs to this
campaign, and it is a new site rather than a missed one: this campaign's gate landed green on
2026-08-10 and a peer commit added the declaration past it on 2026-08-12. It is not a shape
regression from the relocation - the relocated identifiers are untouched by it - so it does
not falsify this row's claim. It is carried as its own row rather than absorbed silently here,
because a fix buried inside a verification record is invisible to review.

## Notes

**What this row does and does not certify.** It certifies that the five relocations preserved
every persisted and validated shape, proven by real adapters across every declared boundary
with strict equality, and that nothing in the tree lost an import. It does NOT certify that
the campaign's structural gates are green tree-wide - one is not, and it is named above with
its own open row. Reading this checkbox as "W01 is finished" would be the exact conflation the
plan warns about, where delivered-as-specified and delivered-narrower wear the same mark.

**Measurement discipline.** The suite was run with parallelism disabled and random ordering
disabled, output redirected in full to a file and read back from disk. The tree currently
carries several agents' uncommitted work and a parallel run over this backing share produces
artefact failures, so a sequential run is the only reading worth triaging. Exit status was
captured on the command itself rather than inferred from a pipeline.

**The two peer failures were deliberately not fixed.** Both sit in files belonging to active
peer campaigns and neither is an identifier surface. Patching them to make this row's run look
clean would be the "opportunistic edit of peer work" failure mode, and it would also hide two
genuine unswept regressions from the campaigns that own them. They are reported instead.

**Vault state is on disk and uncommitted.** The repository index lock has been held by a dead
writer since 19:31, diagnosed by modification time and left untouched. This record and the
plan row state are complete on disk and commit when the lock clears.

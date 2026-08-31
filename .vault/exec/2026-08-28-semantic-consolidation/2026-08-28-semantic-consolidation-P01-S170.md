---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:f8028a065c025a0e5a7c60dca4d6086cba87defc91c3216aa3244ec22843cbb6'
step_id: 'S170'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Retire the four storage child namespaces the parent map was blocking, and re-confirm that three previously-reverted namespaces still fail on their own merits

## Scope

- `src/cadrumo/adapters/persistence/storage/`

## Changes

- `M` `blob_store`, `envelope`, `bucket`, `master_key` namespaces made inert; consumers repointed
- `M` `core.resources`, `aeat.browser`, `application.invoices` retired and REVERTED again
- `verify:` no file fails to parse; no relative import resolves to a missing module
- `verify:` of 708 tree-wide collection errors, 0 name any namespace retired here

## Notes

The four storage children were refused earlier by the parent-first guard. They
retire cleanly now that `P01.S07` removed the parent's lazy map, which is the
constraint behaving exactly as recorded rather than a new discovery.

### Three that fail on their own merits, re-confirmed

A sweep across every remaining clean namespace re-retired three that had been
reverted earlier in the campaign, because the sweep's refusal criteria cannot
see why they were reverted. They broke the same way a second time and were
reverted again:

- `core.resources` -- consumers reach it as `resources.bundled_path(...)`,
  attribute access on the module object
- `aeat.browser` -- a consumer imports `Profile`, which the eager block does not
  carry
- `application.invoices` -- a gate asserts the production resolver IS publicly
  exported, which retirement contradicts rather than breaks

Worth recording as a property of the tooling: a batch sweep re-proposes anything
whose exclusion lives in a human judgement rather than in a guard. The
parent-first case became a guard and never came back; these three have no
guard, so they will be re-proposed by every future sweep until one exists or
they are settled.

### Tree state at close

The tree-wide collection is red, at 708 errors, all from a peer's in-flight
refactor of `domain/calculations/registry/record_design*` -- one file that
failed to parse mid-write and a private helper being moved between modules.
None of it is this campaign's, and a clean tree-wide verification run was not
available at close.

What could be verified was: the damage scan reads zero unparseable files and
zero unresolvable relative imports, and no collection error names a namespace
retired here. That is weaker evidence than a green collection and is recorded
as such rather than as a pass.

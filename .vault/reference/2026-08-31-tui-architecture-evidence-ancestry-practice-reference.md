---
tags:
  - '#reference'
  - '#tui-architecture'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:4057026f1d65ed5587d413837baeaa9c6231e920d6ebbbc8935be192b7c8f699'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# `tui-architecture` reference: `evidence ancestry practice`

What an evidence document must say about the tree it was stamped against, kept
from the two dependency-receipt references retired under interface `W06.P13.S99`.
Those two were orphaned -- both minted hours before the amendment that retired
their schemas by name, and neither a descendant of it -- but two things about how
they made their claims were right and outlive the schema family they belonged to.

## Summary

### Scope an ancestry claim to paths, never to the whole tree

A receipt that claims the whole repository was clean at the moment of stamping
stops being true the instant anyone commits anything, however unrelated. In a
busy tree that is minutes. The consequence is not merely that the claim ages: it
is that two receipts for the same predecessor can both be honestly written and
still disagree, which is exactly how two divergent receipts for one predecessor
came to exist in this feature.

A path-scoped claim names the specific paths whose contents the verdict covers,
and it stays true for as long as those paths are unchanged. It also becomes
checkable: a reader confirms it with one command rather than reasoning about
what has landed since. State plainly what is NOT claimed -- nothing about the
repository as a whole -- so a later reader cannot over-read the scope.

### Reproduce with the exact commands and their observed results

Record the commands verbatim, and record what each one actually returned when
it was run -- an empty output, a pass count, an exit status. A command without
its observed result tells a reader how to look but not what was seen, so a later
run that disagrees cannot be recognised as a disagreement. A result without its
command cannot be re-derived at all. The pair is the evidence; either half alone
is an assertion.

Bind a predecessor by its own recorded verdict rather than by filename, so a
predecessor that turns red or changes shape breaks the dependent claim instead
of passing as a path that happens to exist.

### Why this note exists rather than the receipts

The receipt schemas these practices were written under were retired by name.
The practices are not schema-specific: they apply to any document that attests
to a state of the tree. Keeping them attached to a retired schema family is how
they would have been archived along with it.

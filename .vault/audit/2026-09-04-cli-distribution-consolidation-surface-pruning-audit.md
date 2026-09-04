---
tags:
  - '#audit'
  - '#cli-distribution-consolidation'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:e9e245bc411631028622133d341be04272f52025a9c42045b313ed0ea7692fdb'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# `cli-distribution-consolidation` audit: `surface pruning`

## Scope

Whether the container base-image resolver is dead code, which the pruning phase
assumes. Re-derived from the live tree rather than from the plan row.

## Findings

### surface-pruning | medium | The resolver's caller is gone; the hazard it guards is not

The premise holds as far as it goes. `dev/packaging/smoke_docker.py`, the
install proof that once called the resolver, no longer exists, and
`linux_base_image` now has no production caller anywhere in the tree. Read as a
reachability question, the module is dead.

Read as a control, it is not. Its only importer is the singularity gate, which
walks every Python, YAML and workflow surface and uses the abstract syntax tree
to separate a line that BINDS the base-image literal from one that merely names
it in a docstring or an assertion message. The Dockerfile remains live and is
the single declaration: it sets the image as a build-argument default and every
stage derives from that argument. Nothing else in the tree restates the string
today — but that is the gate's doing, not a property of the tree. The shape the
gate was built against is on record in the resolver's own history: the literal
written twice, once in the Dockerfile and once as a command-line default, with
a comment asserting they agreed and nothing enforcing it.

So the governing distinction is between a control whose hazard has passed and
one whose callers have merely moved on. This is the second. Deleting the module
deletes the gate with it, and the next command-line default reintroduces the
drift silently.

## Recommendations

Withdraw the Step rather than execute it: the resolver is the gate's engine,
not an orphan, and the tree is already in the state the Step was reaching for.

If the naming is the real objection — a private module under the packaging
package with no packaging consumer — the honest change is to relocate it beside
the gate it serves, not to remove it. That is a rename, and should be tracked as
one, so that what is being changed is the module's home rather than the
protection it provides.

Left open pending an operator decision; no other Step depends on it.

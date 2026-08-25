---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:d677c2f5598be2d26937967ca4d57e26f605bc21d5c9bbecaa442b2a24796d4f'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-08-25-tui-architecture-s160-approved-amendment-architecture-review-audit]]"
---

# `tui-architecture` audit: `S170 plan review`

## Scope

Independent plan-only review of commit `577ab7c8b49603ff74099583a18f442c512c2be4`
against the accepted TUI architecture ADR cluster, the approved native-WORK
architecture-remediation packet, the canonical defining-module rule, and the
current cohesive plan at HEAD `dc9050908e5`. No plan or source file was changed.

The amended S170 row correctly requires the public
`cadrumo.application.modelo.work_addressing` defining module, deletion of both
private selector homes and every package/private export path, one pure selector
over a caller-supplied captured `WorkUnitCatalogue` and already-resolved bucket,
the distinct visible-all-state, exact-all-state, operator 12-character, and
active-only modes, cardinality before either revision assertion, direct-import
convergence across every named consumer class, preservation of constraint-
divergent lifecycle and typed error boundaries as delegating wrappers, a real
encrypted-SQL post-capture/no-second-SELECT proof, and current-HEAD exact-AST plus
Vaultspec-RAG fixed-point gates. The blockers below concern whether Terra can
execute that otherwise complete row without contradicting the same plan.

## Findings

### downstream-defining-module | high | S160 and S174 resurrect the module and facade that S170 deletes

S170 atomically deletes `src/cadrumo/application/modelo/_work_addressing.py` and
all `src/cadrumo/application/modelo/__init__.py` work-addressing bindings. Later
row S160 still assigns native WORK capture to `_work_addressing.py` and requires
promotion through that package facade; S174 again assigns revision-identity
cutover work to `_work_addressing.py` and requires facade promotion. S161, S164,
S166, and S129 also require promotion or export through the same Modelo package
facade after S170 has made it inert. The phase ordering makes all of those rows
follow S170. The accepted canonical-defining-module amendment instead makes every
package namespace inert and requires direct imports from one public defining
module. Terra must therefore either recreate a deleted private home, add a
forbidden re-export, or silently reinterpret later-row scope. The plan is not
executable without architectural ambiguity.

### catalogue-scan-wording | medium | The teardown clause also deletes the canonical selector's necessary scan

S170 requires one pure selector over the supplied catalogue, but later says to
delete every `catalogue scan`. The accepted WORK decision is narrower: active-
only delegates to that same scan, while substitutable or parallel repository
scans are converged or deleted. The unqualified plan wording literally removes
the iteration the canonical pure selector needs and leaves Terra to guess which
scan is exempt.

## Recommendations

FAIL. Amend the cohesive plan through the Vaultspec plan CLI before dispatch:
make S160 consume and extend the public `work_addressing.py` defining module by
direct import, and reconcile S174 to its accepted semantically named public
defining module with no package-facade promotion or deleted private path. Remove
the stale Modelo-facade clauses from S161, S164, S166, and S129 in favor of their
accepted public defining modules. Narrow S170's teardown phrase to parallel or
substitutable catalogue scans while retaining the sole pure captured-catalogue
scan. Re-run the plan checker and review the resulting whole-plan diff before
assigning S170 to Terra.

## Remediation re-review

### Scope and evidence

Fresh plan-only re-review of remediation commit
`cebbad34fe5282218220a39a4012665892aadf7e` against both findings above, the
accepted canonical-defining-module amendment, and the downstream W03.P20
dependency order. The review inspected the committed diff and complete current
text of S170, S174, S160, S161, S164, S166, and S129. The Vaultspec plan checker
reports only the intentional `PLAN022` non-monotonic-ID warning caused by the
dependency-ordered insertion of S168-S174 before S160.

### Prior finding closure

The `downstream-defining-module` HIGH is closed. S174 and S160 now define and
extend the sole public `application/modelo/work_addressing.py` module and require
direct imports across production, S126 registration, test, dynamic, and tooling
consumers. Neither row recreates `_work_addressing.py`; each names
`application/modelo/__init__.py` only as an inert-namespace gate. S161 hard-moves
review ownership to public `application/modelo/work_review.py`; S164 defines the
public calculation contract in `application/modelo/calculation.py` while keeping
the unrelated implementation collaborator private; S166 hard-moves the manifest
authority to public `application/modelo/workspace_manifest.py`; and S129 performs
the final public moves to `workspace_models.py`, `workspace_producers.py`, and
`workspace.py`. Every row requires direct consumer migration, package-binding
deletion, and no shim, alias, fallback, bridge, or re-export.

The downstream order is coherent: S174 supplies the pure one-capture revision
assertion before S160 adds native WORK capture; S161, S164, and S166 establish
their public native-owner homes before S167 registration; and S129 relocates the
completed S125/S126/S128 contract, registration, and assembly families only
after those implementation rows, migrating all receipt and frontend consumers
atomically.

The `catalogue-scan-wording` MEDIUM is closed. S170 now deletes selector-owned
repository reads and only parallel, substitutable, repository-owning scans or
first-match picks, while explicitly retaining the sole canonical pure scan over
the supplied captured catalogue.

### Remediation disposition

PASS. Commit `cebbad34fe5282218220a39a4012665892aadf7e` closes both prior
findings. The seven reviewed rows now give Terra one unambiguous public-module,
direct-import execution path consistent with the accepted amendment; no new
critical, high, medium, or low finding remains in the reviewed remediation
scope.

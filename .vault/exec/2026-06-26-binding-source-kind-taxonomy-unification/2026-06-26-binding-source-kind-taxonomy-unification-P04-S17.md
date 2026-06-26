---
tags:
  - '#exec'
  - '#binding-source-kind-taxonomy-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S17'
related:
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-source-kind-taxonomy-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S17 and 2026-06-26-binding-source-kind-taxonomy-unification-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Run the full bindings test surface and both parity halves and owner-triage the full tree and ## Scope

- `src/aeat/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the full bindings test surface and both parity halves and owner-triage the full tree

## Scope

- `src/aeat/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

P04 is a verification-only Step (no production edit). Ran the full bindings test
surface and both parity halves against HEAD and owner-triaged the full tree.

- Both parity halves green: the domain enum-registry gate
  (`test_binding_source_kind_taxonomy.py`) and the application enum-mesh gate
  (`test_binding_source_kind_mesh_parity.py`).
- Full bindings surface green: registry, aggregation, calculations, modelo, and
  invoices test dirs — 3353 + 1042 tests passed across two runs.
- `pytest --collect-only -q src/aeat` collects cleanly.

## Outcome

P04 complete; phase-2.1 taxonomy unification is structurally done.
`BindingSourceKind` is the single source-kind authority across the registry and
the mesh; the two duplicate enums are gone; the counterpart subset is derived; the
two-half parity gate reads the live mesh sets so a future drift fails CI.
Behaviour-preserving throughout — no casilla value shifted.

The enum-mesh gate deliberately reads the LIVE owned/deferred mesh sets (it does
not hard-code any source's disposition), so r2's in-flight withholding enrollment
(moving `withholding` from deferred to owned) will be reflected automatically once
it lands, without a gate edit.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Owner-triaged full-tree failure recorded, NOT fixed (per full-tree-gate-must-
distinguish-owner): the docstring-core-struct gate fails on
`aeat.application.aggregation._withholding_source` — an untracked r2 withholding
module missing a `:class:`ModeloRevision`` docstring link. Outside this feature's
surface; r2 owns the fix.

Declined cross-feature ask: a request to land r2's withholding resolver enrollment
(remove WITHHOLDING from DEFERRED, wire the resolver into the calculate mesh) was
attempted but backed out cleanly — it is entangled with r2's live uncommitted
`aggregation/__init__.py` re-export WIP (the package re-export the enrollment
import depends on is not yet committed at HEAD, so an own-only enrollment commit
would either sweep peer WIP or reference a symbol absent at HEAD). r2 is mid-edit
on those exact files and should complete the enrollment. My phase-2.1 enrollment
edits were fully reverted; `_source_mesh.py` is clean and `aggregation/__init__.py`
carries only peer WIP.

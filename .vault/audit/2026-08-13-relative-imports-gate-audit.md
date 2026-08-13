---
tags:
  - '#audit'
  - '#relative-imports-gate'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:403ba75acd2e38f0f36338a0c46404bfe54661de8ef950bbbb8c9f66feb5d1fe'
related: []
---

# `relative-imports-gate` audit: `relative-imports gate: cluster adjudication and closure`

## Scope

The relative-imports mandate gate (`dev/quality/relative_imports.py`, mirrored as the
pytest gate `src/cadrumo/tests/test_relative_imports_only.py`) exited 1 with 87
violations at HEAD, blocking the style lane and therefore every downstream CI
observation for every concurrent campaign. Neither surface carries an allowlist or
exception mechanism, so no violation could be recorded away.

Each violation was classified before any rewrite, on the principle that a mechanical
absolute-to-relative rewrite satisfies the gate while preserving or hiding whatever
defect produced the absolute import. Three clusters emerged: one layering inversion,
one facade-ownership breach, and three isolated sites.

## Findings

### bound-input-projection-layer | critical | 58 absolute imports encoded a domain-to-application inversion

`resolve_available_bound_inputs_by_casilla_id` lived in
`src/cadrumo/application/modelo/_binding_resolution.py`. Fifty-eight test modules
imported it absolutely; twenty of those sit under
`src/cadrumo/domain/calculations/registry/tests/`, so domain reached up into
application. The relative rewrite available to the gate was a five-dot upward import,
which satisfies the gate and preserves the inversion in a new notation.

The cause was traceable. An identical-shape twin, `resolve_bound_inputs_by_casilla_id`,
occupied the corresponding slot in `src/cadrumo/domain/calculations/registry/_bindings.py`
until a deduplication commit on 2026-08-12 deleted it and retargeted every test caller
to the application copy. That sweep is what introduced the absolute imports. The ruling
behind it chose which duplicate died, on the grounds that the strict variant had no
production caller distinguishing it; it did not rule on the surviving function's layer.

The survivor has zero application-owned dependencies. It reads `ModeloRevision`,
`InputKind`, `BindingId` and `resolve_bound_casilla_binding_value` from the registry and
`CasillaId` from core, every one of which the registry module already imports. Nineteen
of the twenty domain tests carry no other application import at all, and they exercise
pure registry schema and formula behaviour through `calculate_registry_snapshot`, using
the projector only to shape binding values into casilla inputs.

Adjudicated as a misplaced canonical home rather than a misplaced test suite or a
legitimate cross-boundary contract. Resolved by relocating the symbol beside the
per-casilla primitive it folds over, in one atomic commit carrying the move, both
facades, the production consumers and every test import. The singularity gate that
pinned the old definition site moved with the symbol, keeping its assertions about the
retired name intact, so one bound-input projection stays provable tree-wide.

### filing-evidence-facade-reach | high | 23 imports bypassed the owning package facade

`general_m303_filing_evidence` is defined in `src/cadrumo/tests/filing_evidence.py`,
which carries its own module-level `__all__` but was not re-exported from the
`cadrumo.tests` package facade. Twenty-three cross-package consumers reached the
submodule directly. The relative rewrite the gate would have accepted preserves that
breach, because the ownership rule requires a cross-package import to resolve to the
owning package's canonical public facade.

Promotion was therefore treated as a precondition of the rewrite rather than a
follow-up. An eager re-export was rejected: the module pulls the registry, IVA, filing
evidence and modelos domain surfaces, so eager promotion would drag the domain layer
into every core test's import graph. The lazy resolution shape the same facade already
uses for the committed justificante parse cache was extended instead, and the
single-name conditional was generalised into the name-to-submodule mapping an existing
application facade already established for the identical reason.

### tests-support-submodules-unowned | medium | two sibling support modules remain off the facade

`src/cadrumo/tests/registry_observations.py` and `src/cadrumo/tests/secure_sql.py` are
reached cross-package as direct submodule imports throughout the tree and appear on no
facade. The relative-imports gate accepts that shape because the modules are not
underscore-named; the ownership rule does not. The filing-evidence builder is now the
only one of the three routed through the facade, so the three siblings are governed
inconsistently.

### export-hard-cut-module-object | low | the module-object import was load-bearing, not sloppiness

`src/cadrumo/application/filing/tests/test_export_snapshot_authority_hard_cut.py` bound
the filing package as a module object to prove a retired symbol is absent, asserting it
three ways including a membership check against the package's `__all__`. A name-by-name
rewrite would have satisfied the gate and deleted the proof. Preserved by importing the
subpackage relatively from its parent, and confirmed still failing on a planted
attribute and on an appended export.

### dynamic-import-strings | low | the gate's known blind spot holds no ownership breach today

The gate cannot see module names built as string literals. A sweep of `cadrumo.`-prefixed
strings across the package found the genuine dynamic import sites resolve to public
facades, satisfying the ownership rule that binds them equally. The remaining occurrences
are error-registry dotted paths, logger names, schema identifiers and caller labels,
which are data rather than imports. One test reaches a private module through
`importlib`, which the gate cannot see and which is recorded here rather than swept,
since it lies outside this campaign's surface.

## Recommendations

Tied to `bound-input-projection-layer`: a follow-on ADR should decide whether a
deduplication that picks a survivor on production-caller grounds must also adjudicate
the survivor's layer before the losing copy is deleted. The failure mode this campaign
absorbed is that choosing the survivor by caller count silently relocated a domain
concept into application and inverted twenty test modules' dependency direction, with
no gate able to see it until an unrelated import mandate exposed the absolute imports.

Tied to `tests-support-submodules-unowned`: the two remaining support submodules should
either be promoted to the `cadrumo.tests` facade on the same lazy pattern, or the
package's support submodules should be declared a sanctioned carve-out from the
facade-ownership rule with the reason recorded. Governing three siblings three ways is
the state to end, not the specific direction chosen.

Tied to `dynamic-import-strings`: the gate's docstring already names the blind spot and
directs reviewers to grep for the prefix. That instruction is the whole enforcement, so
it should be treated as author discipline rather than a gate, and the one private
`importlib` reach found in a test should be routed to whoever owns that surface.

Not a recommendation but a closure note: the gate reached zero on this campaign's
surface and was then reopened by six violations arriving in a new file from a concurrent
campaign, three of which also reach private modules for symbols absent from the owning
facade whose own definition file was under uncommitted edit at the time. That surface
belongs to its author, and the durable point is that a tree-wide style gate cannot be
held green by the campaign that cleared it.

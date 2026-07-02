---
tags:
  - '#audit'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-02'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace fichero-boe-parity-gate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `fichero-boe-parity-gate` audit: `fichero-BOE parity gate execution status`

## Scope

Honest execution-status record for the fichero-BOE parity gate after P01-P04
landed, distinguishing completed work from deferred and reframed plan Steps, so
plan-step closure is backed by evidence and the remaining surface is explicit.
Companion to the per-Step exec records; this audit is the deferral register the
`plan-closure-requires-exec-records` rule calls for.

## Findings

### landed-and-tested | low | P01-P04 core gate is committed, green, and regression-locked

The pre-write completeness gate is landed across four commits (`807a55eb9` P01
subview manifest projection, `0eaefcc98` P02 representable/rendered derivation,
`db7eda99d` P03 panic core, `e616666ad` P04 multi-modelo parity lock). Seventeen
feature tests pass in isolation. The gate raises a hard `FilingExportError`
before any bytes are written when a fixed-width `.boe` would omit a required,
representable casilla, enumerating each missing casilla with its number and
segmento. It is scoped to `layout.format == "fixed_width"` (the fichero-BOE DR
format); xml_dictionary exports are excluded because an absent casilla is a
legitimately-absent optional element, not a blank slot.

### reframed-numbering-segmento | low | P03.S09 satisfied by the panic message, not a separate assertion

The plan Step called for a runtime assertion that each rendered casilla's number
and segmento match the registry-declared metadata. This is redundant: the
registry manifest validator already cross-checks manifest metadata against the
casilla at registry-build. The intent is met by enumerating number and segmento
in the panic message (P03.S11), giving the operator the structural identity of
each drift without a tautological runtime re-check. Step left unchecked; intent
delivered.

### reframed-record-order | low | P03.S10 record-order fidelity moved to offline analysis, not a runtime check

A runtime "records emitted in registry-declared order" assertion is tautological:
the renderer sorts records by `record.order` before emitting, so a runtime
monotonicity check can never fail. True order-fidelity (does the layout's declared
order match the official Diseno) is a registry-authoring property, not an
export-time one. Step left unchecked as a deliberate no-tautological-tests
decision; no runtime order gate was added.

### deferred-coverage-advisory | medium | P03.S12-S14 blocked by active peer WIP on _export.py

The coverage advisory (a non-blocking `Notice` when a fixed-width `.boe` revision
declares no completeness manifest, so the operator learns the export was not
completeness-verified) is not implemented. It requires editing
`application/filing/_export.py`, `application/modelo/_export.py`, the CLI export
command, and adding locale keys in four languages. `_export.py` carries active
uncommitted peer WIP (an import-centralization refactor), so per
`uncommitted-wip-is-not-orphaned` the edit is deferred until that WIP commits, to
land via the apply-cached drive or a clean commit. The panic path (the actual
under-declaration defect) is unaffected; the advisory is honesty polish for the
manifest-absent case.

### reframed-parity-fidelity | low | P04.S16 delivered as a non-vacuous guard, not order fidelity

The parity test asserts `required_applicable` is non-empty per covered modelo (the
gate is genuinely active, never vacuously passing) alongside the subset parity.
Full numbering/segmento/order fidelity in the test was not added, consistent with
the reframing above. Step left unchecked; the non-vacuous guard is committed.

### owner-triage-peer-circular-import | low | the src/aeat collect gate is red from unrelated peer WIP

The broad owner-gate run (P05.S20) hit a circular-import collection error in
`aeat.application.workflow` (`WorkflowEvent`), surfaced through the modelo tests.
`workflow/_models.py`, `review/_actions.py`, `modelo/_action_errors.py` and
siblings all carry uncommitted peer changes; the import cycle is theirs, not this
feature's. The filing owner surface is green in isolation (17 feature tests plus
the existing filing export suite). Per `full-tree-gate-must-distinguish-owner`,
this is peer churn, not an owner regression; the collect-only gate stays open
until the peer refactor settles.

### code-review-critical-empty-kind | critical | the shipped gate keyed on id membership, not value presence — fixed in the working tree, commit blocked

The dispatched `vaultspec-code-review` found a CONFIRMED critical defect in the
committed gate (`db7eda99d`): `rendered_casilla_ids` computed
`{value.casilla_id for value in draft.values}` and intersected it with the
representable set. But `build_draft` emits a `ModeloValue` row for EVERY declared
casilla, marking an unsupplied one `EMPTY` (`value=None`). So casilla-id membership
in `draft.values` is the full declared set, not the valued set: an `EMPTY`,
manifest-required, schema-optional casilla (e.g. M130 `06`) counted as "rendered,"
the gate's `missing` set came up empty, and the export succeeded with a valid
digest -- exactly the structurally-thin file the gate exists to refuse. The
reviewer reproduced it end-to-end on M130 casillas `06`/`08`/`10`/`16`/`18`. The
paired test (`test_thin_fixed_width_draft_panics_before_writing`) was tautological
w.r.t. the real bug: it removed the `ModeloValue` tuple entry (an unreachable
state) instead of emptying it. Fix: `rendered_casilla_ids` filters
`value.value is not None` (value is None iff `kind == EMPTY`, per the `ModeloValue`
contract); the test now empties a required-applicable casilla (the real production
state) and asserts the panic. Fourteen filing tests pass with the fix, including
the corrected thin-draft test and the P04 parity (complete drafts still reach disk;
zeros are real values, only `EMPTY` is excluded). STATUS: fix implemented and
tested in the working tree; the commit is blocked because a concurrent peer has 238
files staged in the shared index (a codebase-wide import-centralization sweep,
including `_export.py`). Committing now would sweep peer work, so the fix lands via
the apply-cached drive once that changeset commits and the index clears. The
committed gate is currently ineffective (it never fires on the real thin state) but
causes no active harm: it does not false-panic and writes nothing incorrect.

RESOLUTION: the fix LANDED. The value-presence code fix was co-committed into a
concurrent peer import-centralization commit (`3c1748da7`, which swept the
working-tree change via `git commit -a`) -- verified intact in HEAD. The
strengthened test (emptying a required-applicable casilla in place to reproduce the
real `EMPTY` state) landed cleanly via pathspec (`2488ef810`). All 17 feature tests
pass against HEAD. The gate now fires on the real production thin state. No peer
work was swept by this feature (the peer's 238-file changeset committed on its own;
my reverse-apply left their index intact throughout).

### code-review-medium-row-field | medium | dormant false-panic vector via row_field_casilla_ids

`boe_representable_casilla_ids` unions `record.row_field_casilla_ids.values()` into
the representable set, but those casillas are materialised from `binding_values`,
never `draft.values`, so `rendered_casilla_ids` can never see them. A
manifest-required casilla whose only representable route is a `row_field_casilla_ids`
mapping would show permanently missing and false-panic on every export. Currently
dormant: no shipped registry revision has a manifest-required casilla routed solely
through `row_field_casilla_ids` (confirmed across 130/111/115/123/131). Follow-up:
either extend the rendered computation to count binding-materialised row casillas,
or add a registry-build validator forbidding a manifest-required casilla from being
row_field-only.

### code-review-medium-coverage | medium | P04 parity lock covers 4 of 12 gated modelos

Twelve fixed-width modelos carry a completeness manifest and are gated in
production (`111 115 123 130 131 180 200 202 232 303 349 720`); the P04 lock covers
only `130 111 115 123` (the four with reusable complete-draft builders). Extending
the lock to at least 200 and 303 (named in the P02 empirical grounding) requires
authoring complete-draft fixtures for them. Follow-up.

## Recommendations

- Commit the CRITICAL `rendered_casilla_ids` value-presence fix (ready and tested in
  the working tree) via the apply-cached drive as soon as the 238-file peer
  import-centralization changeset lands and the shared index clears.
- Land the coverage advisory (P03.S12-S14) once the peer `_export.py` WIP commits,
  routing the manifest-absent signal through the typed `Notice` channel and adding
  the locale keys via the locales CLI.
- Re-run the `src/aeat` collect-only gate after the peer workflow/review refactor
  commits to confirm the circular import clears; it is not this feature's to fix.
- Codify the `modelo-export-mirrors-official-structure` rule extension (P05.S19) to
  bind the fichero-BOE transport after the code review closes.
- Address any findings the dispatched `vaultspec-code-review` returns before
  declaring the feature structurally complete.

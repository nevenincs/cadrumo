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

## Recommendations

- Land the coverage advisory (P03.S12-S14) once the peer `_export.py` WIP commits,
  routing the manifest-absent signal through the typed `Notice` channel and adding
  the locale keys via the locales CLI.
- Re-run the `src/aeat` collect-only gate after the peer workflow/review refactor
  commits to confirm the circular import clears; it is not this feature's to fix.
- Codify the `modelo-export-mirrors-official-structure` rule extension (P05.S19) to
  bind the fichero-BOE transport after the code review closes.
- Address any findings the dispatched `vaultspec-code-review` returns before
  declaring the feature structurally complete.

---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:e5476667bfed216c509da552b909d7ecd11c60c626b9b51c3aa099279987e860'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
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

# `ci-lane-deconflation` audit: `Calculate and wizard results omit source provenance`

## Scope

`src/cadrumo/entrypoints/cli/_modelo_revision_payload_parts.py` and the two command result shapes that consume it, `WorkCalculateResult` (`_modelo_payloads.py:624`) and `WorkWizardResult` (`_modelo_work_wizard_payloads.py:51`).

Surfaced while running `test_modelo_payloads.py -m integration` at HEAD 2026-08-31 during unrelated work on the `legal_refs` tuple defect. Two failures remained after that fix and are the subject here. Read-only: no production code was changed by this audit, and the code in question belongs to another lane.

## Findings

### calculate and wizard results no longer carry `source_provenance`, while revision reads still do | `_modelo_revision_payload_parts.py:165`

`test_calculation_revision_result_shapes_subclass_the_shared_projection_base` fails for both `WorkCalculateResult` and `WorkWizardResult`. Measured directly rather than inferred from the assertion text:

- `CalculationRevisionCommandProjectionFields` does NOT subclass `CalculationRevisionProjectionFields` (`issubclass` is `False`).
- The set difference between the two is exactly one field: **`source_provenance`**.

So this is not a stale test against a renamed base. A deliberately compact create-style projection was introduced, and the one field it drops is the provenance field.

### the dropped field is grounding, and its own docstring says it must survive to the JSON boundary

`source_provenance: tuple[SourceProvenancePayload, ...]` carries, per its own documentation, "the resolver -> source-object -> fingerprint trace the calculation source mesh recorded when it produced the revision", projected from `CalculationRevision.source_provenance`. It also carries `dependency_treatment`, the registry's declared carry classification, and the docstring states the reason in as many words: so that a `factual_evidence` carry -- a fact to reconcile against a taxpayer's own document, rather than a figure that settles the return -- "stays distinguishable at the JSON boundary".

What is lost: an operator who runs `aeat app modelo work calculate` or the wizard receives no provenance trace and no carry classification, while the same revision read back through the revision surface carries both. `aeat-calculation-grounding` requires grounding to be preserved "from the registry source to the operator-facing surface" on every CLI emit, and this is precisely an operator-facing emit.

### this is the same shape as a defect the bindings ADR already fixed once

`2026-06-14-bindings-interface-hardening-adr` records a provenance asymmetry "at exactly the operator boundary", where casilla values carried full grounding to draft and export while binding values were flattened. The remedy then was parity, not a compact sibling. The current split reproduces the shape on a different axis: the same revision is grounded when read and ungrounded when created.

**Not asserted:** that the compact projection is wrong. A create-style result may have a defensible reason to be smaller. What is asserted is that dropping the provenance field specifically is a grounding decision, and it is not recorded as one anywhere the gate or the ADRs can see.

## Recommendations

1. Route to the lane that introduced `CalculationRevisionCommandProjectionFields` (the CLI payload projection work, `5d6e4975` "project the grounding refs instead of respelling them"). This audit deliberately does not edit that code.

2. Decide the question explicitly rather than by test edit: either the compact projection carries `source_provenance` and subclasses the shared base, or the omission is ruled on and recorded with its reason. **Do not resolve the red by relaxing the test's `issubclass` assertion** -- that converts a grounding decision into a silently weakened gate, which is the failure mode `aeat-quality-gates` names.

3. If the omission is kept, state where an operator obtains the provenance trace and the `dependency_treatment` classification after a calculate, since the field's own docstring makes that distinguishability a requirement rather than a convenience.

4. Check the sibling surfaces for the same asymmetry before closing: any other create-style result built on the compact base inherits the same gap.

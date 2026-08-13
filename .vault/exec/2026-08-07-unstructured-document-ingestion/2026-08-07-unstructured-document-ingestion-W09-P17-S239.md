---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:985905c69f0aded271fbb8e7e694684c4e338d0da664d37e0c3d6a94ef80fd81'
step_id: 'S239'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# RULED and REWORDED. The original wording, name the offending value, instructed a breach of a landed privacy decision and is withdrawn: internal_record_fault_context projects the failing model, the field path and the constraint message and NEVER the input, on the stated ground that a validated record on this path holds taxpayer data and the value that breached a constraint is exactly the value that must not cross an output boundary, while the field and the rule are what make the defect reportable and neither is sensitive. A counterparty tax identifier is precisely that value. The deliverable is therefore the FIELD and the CONSTRAINT, never the value. RULED for the general fix over the one-site patch: project field-and-constraint context onto CliValidationBoundaryError too, reusing internal_record_fault_context rather than authoring a second projection, and keep the MESSAGE generic so the end-user surface does not become the per-field dump the existing rationale objects to. The detail rides context, which both renderers already emit for the two sibling boundary members. That narrows the existing rationale rather than discarding it, since the noise objection was about the message. The rationale is sound for the case it imagines, an operator who mistyped an argument and can look at what they typed, and fails for the case it does not: a constraint breached on a field the operator never supplied, where check the command's arguments points at arguments that are all correct, which is verbatim the failure the projection was written to fix. This CLI's operator is an autonomous agent for whom structured context is not noise. Blast radius measured: 38 sequence goldens pin a null context and six test modules assert the generic message, and those goldens are generated artefacts already rowed for regeneration under W02.P05.S222

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

## Outcome

Executed. This row's own account is written into the plan row text, which opens with its verdict (RULED and REWORDED — the original wording instructed a breach of a landed privacy decision and is withdrawn) and gives the reasoning a record would have carried.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account.** The real account exists verbatim in the plan; it was filed as a work item rather than as evidence, which is why no record accompanied it.

## Notes

---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:c14a6af89e5fdb37469e2ee80a8dd9767196394708b6be651778b0bdb612bc0a'
step_id: 'S01'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Add the FieldOrigin provenance StrEnum (EXACT_STRUCTURED, TEXT_LAYER, VISION, TABULAR_MAPPED, OPERATOR) with facade export, gated by enum round-trip tests and the import-hygiene gate

## Scope

- `src/cadrumo/core`

## Description

- No code was written for this Step. It was found already satisfied at HEAD and closed by verification against the Step's own specification rather than re-landed.
- Confirmed `FieldOrigin` exists as a StrEnum in `src/cadrumo/core/_field_origin.py`, carrying exactly the five members the Step names.
- Confirmed the eager facade export and the `__all__` entry in the core package.
- Confirmed the round-trip gate exists at `src/cadrumo/core/tests/test_field_origin.py` and read it in full to judge whether it is tautological.
- Confirmed the enum is live rather than dormant: the extraction interchange contract in the LLM package types its producer's origin field against it.

## Outcome

Delivered by a prior commit, verified here. This is a closure by verification, not by implementation, and the distinction is recorded deliberately: claiming delivery would misattribute the work, and checking the row silently would leave three indistinguishable states behind one checkbox.

What was checked, and how. The five members carry the exact tokens the Step enumerates, each byte-identical to its stored form. The gate asserts the member set is closed, that each member carries its expected token, that each token hydrates back to its member, and that an unknown token raises rather than being accepted.

The gate is non-tautological, which is the part worth recording because it is the failure mode this class of test usually has. The expected tokens are pinned to literals in the test rather than derived from the member names. A gate deriving them by lowercasing the member name would restate the implementation and pass whatever the enum said, including after a rename that silently orphaned every persisted record. The refusal assertion is the necessary companion: without it a permissive enum would satisfy every positive assertion above while admitting arbitrary strings at the boundary.

The adjudication this Step was flagged for made itself moot, and the reason is the durable part. The brief identified a per-field extraction provenance contract already living in the LLM package as the highest duplication risk in the phase, and asked whether its source-kind taxonomy was the canonical home to extend rather than adding a second enum. That taxonomy no longer exists: the producer contract now types its origin field against the core enum directly, so the concept was migrated onto one home rather than forked. Nothing was left to adjudicate.

Had it still been open, the reasoning would have been to put the axis in core and migrate the LLM-local taxonomy onto it, which is what the tree did. The axis has producers in the LLM package, a projection layer in the application layer, and an operator-facing surface in the entrypoints layer; core is the only home all three reach without one depending on another. The module holding the interchange contract is an application-layer contract module by its own docstring, so it is a consumer of the axis rather than a candidate owner of it.

The enum carries no numeric model self-confidence field, and its own docstring records why: a model's confidence in its output cannot corroborate that output. The trustworthy axes are how a value was obtained and what verification it passed, and both are facts. That reasoning is sound and was left untouched.

## Verification

    uv run --no-sync pytest src/cadrumo/core/tests/test_field_role.py src/cadrumo/core/tests/test_field_origin.py src/cadrumo/application/tests/test_field_role_importer_coverage.py -p no:randomly -p no:cacheprovider
    80 passed in 6.38s

This Step's gate ran inside that selection. The log was written in full to disk and read back; grepping it for deselection and error markers returned nothing, so every collected test ran rather than being silently deselected by a marker lane.

The facade export was verified by importing it rather than by reading it:

    uv run --no-sync python -c "from cadrumo.core import FieldRole, FieldOrigin; print(len(list(FieldRole)), FieldRole.UNMAPPED.value, FieldOrigin.TABULAR_MAPPED.value)"
    22 unmapped tabular_mapped

The prior commit that delivered the module was identified by inspection of the history for the module path, so the closure cites a specific landed change rather than the mere present-day existence of a file.

## Notes

No commit was issued from this Step, because nothing was written.

The repository-wide import-hygiene gate named in the Step's own gating clause was red throughout the phase at 83 reaches against 79 documented, from four undocumented private test imports that arrived in peer commits. It is unrelated to this Step's surface and was recorded rather than patched. The Step's other gate, the round-trip suite, is green.

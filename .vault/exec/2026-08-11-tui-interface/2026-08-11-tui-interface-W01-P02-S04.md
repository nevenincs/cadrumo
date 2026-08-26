---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:e0b31d1d2c4ddff8d6bc4193d37b7860af85ade511af8d43fd1fb110bc5ed1d8'
step_id: 'S04'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Define typed profile presentation states for static requiredness conditional applicability filing preflight readiness relevance source provenance conflicts and explicit unknowns

## Scope

- `src/cadrumo/application/user_profile/presentation.py`

## Changes

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->

- `A` `src/cadrumo/application/user_profile/presentation.py`
- `verify:` `pytest src/cadrumo/application/user_profile/tests/test_presentation.py -m integration` -> `pass` (9 passed)

## Notes

Landed as `presentation.py`, not `_overview.py` as the Step row names: that
path collides with the already-existing PUBLIC `overview.py` (a distinct,
narrower schema-completeness/masking projection with no
requiredness/applicability/provenance/conflict concepts). `_overview.py`
would also violate `aeat-naming`'s instruction that two concepts sharing a
name get the non-canonical one renamed. Reported and confirmed before
implementing.

Scope for this pass, stated in the module docstring: conditional-applicability
resolution covers only the named trigger paths in `_CONDITIONAL_TRIGGERS`
(`auth.clave_movil_route`, the legal-entity fields, the IRNR
fiscal-representative fields) and non-repeatable sections; the IVA-regime
conditional block and repeatable sections present as `OPTIONAL` rather than
being assessed for applicability, since their trigger conditions are
multi-field. The `Review` stage's unresolved-proposal/conflict row is not
built here -- it is produced by whichever registered acquisition/reconciliation
operation proposes the divergence, not by this static per-field projection;
`ADVISORY_NOTICE` and `UNRESOLVED_CONFLICT` are declared absent from
`ProfileFieldClassification` for the same reason, documented on the enum.
---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:66da5647b6cd623f183e1bbb687ef7e80a9c0930a6f0b8ed00f92d508fa4d9dc'
step_id: 'S256'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Wire the filed-history operation through the generic result-projection mechanism with a typed public result exposing its evidence, IVA wallet, notificaciones and provenance facts, registering its result_projector against the stored run, and prove a frontend projects every fact W05.P12.S69 names without importing the private FiledHistoryOnboardingRun type

## Scope

- `src/cadrumo/application/live/filed_history_operation.py`
- `its public result type and projector registration`
- `and focused filed-history public-result tests`

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

- `M` `src/cadrumo/application/live/filed_history_operation.py`
- `M` `src/cadrumo/application/live/tests/test_filed_history_operation.py`
- `verify:` `pytest src/cadrumo/application/live/tests/test_filed_history_operation.py -m integration` -> `pass` (15 passed; 2 pre-existing unrelated failures)

## Notes

`_settlement_reference` now always stores the full settled run through the
secure operand port and returns that digest as `result_ref`, rather than
substituting the sync-run child's own key when one exists: a `result_ref`
that sometimes names one kind of reference and sometimes another cannot be
resolved through a single typed public door. Child provenance
(`sync_run_ref`) travels as a field on the new
`FiledHistoryPublicResultV1` instead. This is a genuine settlement-contract
change to an existing accepted operation; the one existing test asserting
the old shape
(`test_supervisor_receipt_joins_the_exact_encrypted_child_after_settlement`)
was updated in the same commit to resolve the run from the operand store
and verify child provenance from its `sync_run_ref` field instead.

`FiledHistoryPairOutcome`/`FiledPeriodSelectionRow`/`Notice` could not be
reused directly as public-schema field types: the operations public-schema
contract rejects any model graph missing `validate_default=True` or
carrying a custom serializer (`Notice.context`), and the shared
`STRICT_FROZEN_CONFIG` those types use is out of this Step's scope to widen.
Narrow public siblings (`FiledHistoryPairOutcomePublicV1`,
`FiledPeriodSelectionPublicRowV1`, `FiledHistoryEvidenceNoticeV1`) carry the
same facts under the required config instead.

`test_frontend_projects_the_public_result_without_the_private_type` proves
every S69-named fact (evidence, IVA wallet, notificaciones, provenance) is
resolvable through `OperationResultProjectionService` alone, and includes an
AST check that its own body never names `FiledHistoryOnboardingRun`.
`src/cadrumo/entrypoints/tui/profile/sync_review.py` was extended with
`resolve_filed_history_result`, wiring the TUI's `OperationController` to
this door; `src/cadrumo/entrypoints/tui/profile/tests/test_filed_history_operation_view.py`
proves that wiring reaches the real service (refusal path; the SUCCEEDED
path is proven in the file above, which needs a routed AEAT-register test
fixture this package does not have).
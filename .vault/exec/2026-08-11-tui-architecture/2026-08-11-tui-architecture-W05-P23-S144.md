---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:17d9d58757274aa2e4507bbc9609b00dff967263c014aebc7cae59873f0a3b10'
step_id: 'S144'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Enroll the calculate and recalculate edit family through ModeloEditContractV1 and the transient financial operand handoff, register the typed ModeloWorkspaceRefreshTargetV1 resolver, and ensure frontend entrypoints can submit only typed requests without custody or mutation access

## Scope

- `src/cadrumo/application/modelo/_operation_definitions.py`

## Changes

- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `M` `src/cadrumo/application/modelo/_edit_execution.py`
- `M` `src/cadrumo/application/modelo/_edit_models.py`
- `M` `src/cadrumo/application/operations/registry.py`
- `M` `src/cadrumo/application/operations/tests/test_registry.py`
- `M` `src/cadrumo/application/modelo/tests/test_lifecycle_operation_conformance.py`
- `A` `.vault/adr/2026-08-27-tui-architecture-credential-free-type-aware-gate-adr.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_lifecycle_operation_conformance.py src/cadrumo/application/operations/tests/test_registry.py -m unit -n0` -> `pass`

## Notes

The Step row names a private `_operation_definitions.py`. It is public here,
per S150's own precedent: every existing enrolment exemplar is public.

`modelo.edit.apply` delegates to the existing `apply_modelo_edit` single
writer under a recorded operation identity. No lifecycle policy is
re-implemented: the commit-point baseline recheck, the calculate/recalculate
discrimination (recalculate refuses honestly via the pre-existing
`RECALCULATE_NOT_YET_WIRED` reason - cited as existing state, not
introduced here), and the co-committed result receipt all stay owned by
that function.

**The mirrored wire payload, and why it exists.** `ModeloEditSubmissionV1`
was built entirely inside the Edit Contract module, never against the
operations payload-graph gate, so embedding it directly failed that gate at
nearly every layer - a design-level property of the module, not a run of
bad luck. Two domain fields on the baseline (`modelo: ModeloCode`,
`period: Period`) either customise their Pydantic core schema or lack
`strict=True`; `ModeloScalar` (`Decimal | int | str | bool | date | None`)
fails the gate's validation/serialization schema-identity check because
`Decimal` always serializes to a string. The operation's request type is
therefore a total, per-field mirror - `ModeloEditApplyBaselineV1`,
`ModeloEditApplySubmissionV1`, and one shared mirrored scalar-value type
reused across scalar, binding and row intents - translating back to the
real domain types in `to_baseline()`/`to_submission()`. The mirrored
payload is INPUT, not authority: `apply_modelo_edit` re-resolves and
re-validates every coordinate at the guarded commit point regardless of
what the wire carried, so a stale or forged mirror cannot be believed - a
mismatch surfaces as the typed no-effect result, never a bad write. A
narrower reference (an admitted-submission id instead of the full graph)
was considered and ruled out: `admit_modelo_edit` is stateless and returns
the baseline to the caller with nothing persisted under a lookupable id, so
the submission genuinely originates at the operation boundary.

**`detail_row_intents` is deliberately ABSENT from the wire type**, not
silently emptied: `ModeloDetailRow` (the per-modelo M184/M232/M349/M347/M210
row union) embeds coercive `BeforeValidator` code hydration on many
fields - built for CLI `--row key=value` parsing, not a static wire shape -
and the payload gate refuses that structurally regardless of whether a row
is ever submitted. This operation cannot carry a detail-row edit yet: the
type cannot be constructed with one at all, which is loud, not silent. A
caller needing a detail-row edit has no operation-enrolled path today; the
real six-row mirror is its own follow-up Step (drafted, not yet added -
pending review).

**Manual-override financial-amount bounds.** `transient_financial_operands`
declares the amount's EUR/scale-2/min-max bounds on the definition - a real
declaration, not an assertion that the operation asks for it mid-flight.
`OperationExecutorContext` has no accessor for
`OperationTransientFinancialOperandProtocolV1` today, so no executor
anywhere can exercise the broker side of that contract. The manual-override
amount instead arrives through the already-admitted scalar intent value,
and a submission-mirror validator duplicates the SAME bounds there, so an
out-of-range amount cannot be constructed rather than being caught later.
This should collapse into the broker once the executor-context wire lands
(its own follow-up Step, drafted, not yet added - pending review).

**Deferred and cited, not silently absorbed:**
- The typed Workspace refresh target resolver - `W05.P23.S306`, carved out
  during this Step's discovery; `operations/registry.py` was not touched
  for it here.
- The executor-context financial-operand broker wire - a follow-up Step
  drafted separately, pending review before it is added.
- The six-row `ModeloDetailRow` mirror for `detail_row_intents` - a
  follow-up Step drafted separately, pending review before it is added.
- `W05.P23.S307` (the operations `STRICT_FROZEN_CONFIG` gap: silently
  accepts a default that would fail its own field validation, across 432
  files) was surfaced while building this Step and deliberately left open
  as independent work, not folded in and not abandoned.

**Two gate discoveries landed as their own commits, not folded into this
one:** `2026-08-27-tui-architecture-credential-free-type-aware-gate-adr`
(accepted) and its implementing fix admit a Hex64-shaped, digest-named
field past the operations credential-free check, which otherwise blocked
every `ContentDigest`-typed compare-and-swap coordinate on this baseline by
name alone. Separately, the modelo lifecycle conformance suite
(`test_lifecycle_operation_conformance.py`) imported `OperationDefinition`
only under `TYPE_CHECKING` while using it at runtime, so its entire 45-test
suite over all seven enrolled operations had been raising `NameError`
before a single assertion ran - asserting nothing, for any of them, until
fixed here. Once it actually ran, it caught a real defect in this Step's
own first draft: the executor was constructing `WorkUnitCatalogueRepository()`
and its siblings inline rather than letting `apply_modelo_edit` default
them internally like every sibling lifecycle action. `apply_modelo_edit`'s
repository parameters now default and resolve the same way
(`verify_modelo_revision`, `amend_modelo_revision`,
`file_modelo_revision`, `export_modelo_revision`), so the executor
constructs no repository of its own. Had the suite's own defect gone
unnoticed, an operation violating this module's own single-writer claim
would have shipped as its seventh member with a green, but empty, gate
behind it.

**Worktree capture, recorded rather than corrected in place.** A mid-progress
snapshot of this Step's own uncommitted work - `operation_definitions.py`
before the repository-defaulting cleanup above, plus the `_edit_models.py`
`validate_default` fix - was captured whole into an unrelated peer commit
during this Step's build. Content verified correct at HEAD; history was not
rewritten, per the shared-worktree rule. The sharper risk such a capture
carries is not the wrong commit message, it is an unfinished intermediate
becoming the shipped record with nothing to flag it as incomplete - this
Step's own build was the source of that intermediate, so it is recorded
here rather than left to be discovered later.

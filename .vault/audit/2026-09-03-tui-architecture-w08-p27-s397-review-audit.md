---
tags:
  - '#audit'
  - '#tui-architecture-w08-p27-s397-review'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:94c8fbf41e1cfa371175411599ecc0de521e83a33b1be16fa79f036d80339481'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture-w08-p27-s397-review` audit: `AEAT Sync workspace projection review`

## Scope

Reviewed the committed S397 baseline and live remediation in
`src/cadrumo/application/aeat_sync/workspace.py`, its package initializer, and
`src/cadrumo/application/aeat_sync/tests/test_workspace.py` against the exact
workspace-projection plan step and the application, redaction, storage, and
import-boundary rules. The review exercised serialization, scope, duplicate,
source-semantics, supported-action, determinism, and no-I/O behavior. Focused
pytest, Ruff, ty, and basedpyright gates were also run.

## Findings

### protected-payload-retention | high | The safe projection retains every excluded sensitive input as ordinary pickleable state

The row models declare protected taxpayer names, NIFs, profile values,
notification concepts, URLs, document text, certificate and evidence
identifiers, raw evidence objects, and secrets as normal Pydantic fields with
`exclude=True`. That flag protects `model_dump`, but it does not remove the
values from the projection. They remain directly readable from attributes and
`__dict__`, and Python serialization of a complete projection reproduced the
NIF, bucket identity, URL, certificate identity, raw-evidence sentinel, and
secret sentinel. `AeatSyncWorkspaceProjectionV1.bucket_id` and notification
`semantic_identity` are likewise normal serialized object state despite the
requirement that these private coordinates be nonserializable. The frontend
projection therefore remains a plaintext payload carrier rather than excluding
protected facts at its construction boundary.

### unsupported-action-authority | high | Closed enum membership is mistaken for application action admission

`AeatSyncSupportedAction` spells eight presentation-local verbs, including
generic compare, review, adopt, and reconcile actions. Neither row validation
nor `project_aeat_sync_workspace` resolves them against the operator-action
catalogue or a registered operation/capability. The projector also admits any
enum member on any area: a Notifications overview row accepted
`ADOPT_CENSUS`, and a reconciliation explicitly in `NO_ACTION` accepted
`RECONCILE`. Sorting this tuple makes it deterministic but does not make it
supported. A later TUI could therefore present or execute authority the
application has not admitted.

### collapsed-source-availability | high | One zone availability cannot preserve independent local and AEAT source truth

Each multi-source zone carries one availability and observation timestamp while
its `sources` field is only a tuple of authority names. This cannot represent a
common valid state such as locally observed filing facts with AEAT filing
evidence locked, unavailable, stale, or never captured. Marking the whole zone
non-observable rejects the local rows; marking it available erases why the AEAT
side is unknown. Row-level `NOT_OBSERVED` is not a substitute because it cannot
distinguish unavailable, locked, or never-captured evidence. The contract thus
does not preserve the independent source availability/freshness axes required
for truthful AEAT Sync behavior.

### package-facade | high | The new package initializer violates the mandatory inert-package boundary

`src/cadrumo/application/aeat_sync/__init__.py` re-exports the complete
workspace API, and the first focused test requires that forwarding facade.
The architecture rule requires package initializers to be inert namespace
markers and every consumer, including tests, to import public symbols directly
from their defining module. This creates a second public import home before the
workspace has any consumer.

### incomplete-scope-and-duplicate-proof | medium | Missing scope coordinates and contradictory logical duplicates are accepted

Every row's bucket and subject coordinates are optional. A row carrying neither
is accepted into a bucket projection, so the projector cannot prove that row is
not cross-bucket or cross-subject. Duplicate checks are also weaker than the
logical identities: two overview rows for the same area are accepted when their
private semantic identities differ, and the same census path is accepted twice
when the caller assigns different categories. Both cases inflate measured
counts with contradictory views of one logical item.

### test-teeth | medium | Green focused tests omit the authority and serialization failure modes

The eight tests prove JSON/repr exclusion, explicit mismatched bucket rejection,
one duplicate case per collection, and deterministic ordering. They do not
exercise Python serialization, missing scope coordinates, same-area overview
duplicates, same-path census category disagreement, per-source availability,
area-specific supported-action closure, or `NO_ACTION` with an executable
action. The package-facade assertion additionally locks in a direct rule
violation.

## Recommendations

S397 must not close in its current form.

1. Split private source inputs from public output rows. Retain only the minimum
   stable selection coordinate through a deliberately nonserializable private
   capability/value boundary; do not store protected values or raw evidence on
   the output models. Make bucket/subject provenance mandatory at admission or
   accept source-specific typed inputs that prove scope before projecting it
   away.
2. Replace the free supported-action enum with injected, catalogue- or
   operation-validated action references and enforce the allowed action set for
   each row kind and reconciliation state.
3. Model source observations independently for every local and AEAT authority,
   including availability, freshness, refusal, and measured count. Derive zone
   admission without collapsing those axes.
4. Restore an inert `application/aeat_sync/__init__.py` and import directly from
   `application.aeat_sync.workspace`.
5. Key overview rows by area and census rows by canonical path, reject missing
   scope evidence, and add adversarial tests for every failure mode above.

Focused gate evidence: 8 tests passed; Ruff passed; ty passed; basedpyright
reported zero errors and warnings. These green checks do not close the semantic
and security findings.

## Final disposition

Post-remediation review resolves every finding above. Public projection and row
types physically omit protected payload, bucket, subject, and private
notification identity fields; those coordinates exist only on mandatory
admission facts and are projected away. Python pickle, `vars`, attribute
absence, subclass-stripping, and repr/JSON tests pin that boundary. The package
initializer is inert.

Each zone now retains independent source observations with availability,
freshness, refusal, and measured count. Confident rows require the exact
attributed source to be observable and non-empty, while known-empty and unknown
remain distinct. Overview authority joins are area-specific. Logical duplicate
checks use overview area, private admission-only notification identity, natural
filing address, and a census path normalized by case and collapsed whitespace.

Every concrete public row now inherits the public immutable capability row
contract, so admitted action and operation provenance is physically retained by
real overview, census, filed-declaration, notification, evidence-comparison,
and reconciliation instances and their serialized representations. Supplied
action declarations must equal their complete entry in
`OPERATOR_ACTION_CATALOGUE`; forged same-ID/different-command entries are
refused. Row/area/state closure, exact public operation-contract lookup, TUI
frontend admission, pull-action operation joins, and `NO_ACTION` closure are
enforced before projection.

Final focused evidence: 12 tests passed with all lanes enabled; Ruff passed; ty
passed; basedpyright reported zero errors, warnings, and notes.

Final result: **CLOSE**. S397 may close.

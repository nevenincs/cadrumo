---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:5f5512438a66b47bdbb8d1c96c567aa06e38c6ede65b63004d3939df0bfedd55'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-architecture-censo-operation-authority-reconciliation-research]]"
---

# `tui-architecture` audit: `S30 censal reviewed operand review`

## Scope

Audited `W03.P06.S30` against the amended operation architecture, censo
authority research, plan and execution record. The review covered strict model
shape, canonical profile baseline identity, revision and content digest,
field-intent completeness and ordering, self-digest integrity, encrypted
at-rest storage, canonical ownership, facade direction, duplication, and real
test integrity.

## Findings

### intent-totality | high | The reviewed operand accepts missing canonical field decisions

`CensalReviewedOperand.field_intents` has no minimum length or total-set
validator. It checks only that supplied paths are individually adoptable and
non-duplicated. A production construction with an empty tuple validates and
receives a proposed-effect digest, while the shipped fixture covers only two of
the three `CENSAL_ADOPTABLE_PATHS`. The contract therefore cannot distinguish a
deliberate preserve decision from an omitted decision and does not implement
the Step's one adopt-or-preserve intent per canonical path requirement.
`src/cadrumo/application/user_profile/_censal_operation.py:67` and
`src/cadrumo/application/user_profile/tests/test_censal_operation_operand.py:99`.

### outbound-dto-ownership | high | The application operand gains a forbidden runtime dependency on an outbound adapter

The persisted application-owned operand types its observation directly as
`CensalDatosResult` imported from `cadrumo.adapters.outbound.aeat.sede`. This is
a runtime Pydantic dependency from application to a concrete adapter, whereas
the neighboring censo application service deliberately confines the same type
to `TYPE_CHECKING`. The architecture gate explicitly reports
`cadrumo.application.user_profile._censal_operation ->
cadrumo.adapters.outbound.aeat.sede` as a broken layered-architecture edge.
Persisting the adapter DTO also makes the durable operand schema change whenever
the parser adapter changes. `src/cadrumo/application/user_profile/_censal_operation.py:10`.

### intent-totality-resolution | high | Resolved: strict hydration requires the full canonical ordered path tuple

Re-review confirms the validator now requires the supplied path tuple to equal
`CENSAL_ADOPTABLE_PATHS` exactly. The complete fixture carries all three paths,
and strict negative coverage refuses empty, partial, duplicate, reversed, and
extra unknown-path payloads. Proposed-effect digest tampering continues to
refuse. The original HIGH finding is closed.

### outbound-dto-ownership-resolution | high | Resolved: the parser returns the application-owned observation directly

Re-review confirms `CensalObservation`, its identity, and its address are
defined once in the application user-profile package and exported through that
package facade. The outbound parser imports that facade and constructs the
canonical models directly. The former adapter DTO classes and exports were
deleted, repository search finds no compatibility alias or bridge, and
import-linter no longer reports the S30 application-to-adapter edge. The
original HIGH finding is closed.

### parser-static-gate | medium | The remediated outbound parser remains red under BasedPyright

The focused parser and operand behavior is green, but BasedPyright reports
three `reportUnnecessaryIsInstance` errors in the now-modified
`src/cadrumo/adapters/outbound/aeat/sede/_censal_datos.py` at the current lines
225, 318, and 320. The errors do not invalidate the canonical observation or
intent semantics, but the touched remediation surface does not yet satisfy the
project's no-skip type-check gate.

### parser-static-gate-resolution | medium | Resolved: object-boundary validation is fail-closed and the focused type gate is green

Re-review confirms the parser now routes table, row, and cell objects through
`_require_tag`, whose `object` boundary narrows only after a runtime `Tag`
check and raises `SedeParseError` with `external_shape_changed` on mismatch. A
direct non-Tag probe exercised that refusal. BasedPyright reports zero errors,
warnings, or notes across the canonical observation, operand, parser, and both
focused test modules. The focused behavioral lane passes 43 tests. The MEDIUM
finding is closed.

### facade-diagnostic-assessment | low | Existing facade diagnostics are not introduced or widened by S30

A separate BasedPyright run over `application.user_profile.__init__` continues
to disclose four diagnostics on `apply_censal_read`, `apply_cotejo`,
`resolve_login_target`, and `PROFILE_CAPSULE_ARCHIVE_MAX_PAYLOAD_BYTES`. The
S30 diff adds only the three typed `CensalObservation` exports, their lazy
bindings, and their `__all__` entries; none of those additions is diagnosed.
The focused S30 modules and their facade consumer are clean, so this is not an
in-scope S30 regression. Import-linter remains red on unrelated existing
application-to-adapter edges but no longer lists `_censal_operation`.

## Recommendations

- For `intent-totality`, require the intent paths to equal the canonical
  adoptable path set exactly, in canonical order, and add empty, partial,
  duplicate, reordered, and complete-set strict hydration tests. Do not infer a
  default for omitted paths.
- For `outbound-dto-ownership`, define or reuse an application/domain-owned
  immutable censo observation contract and make the outbound adapter project
  into it. Keep parser-specific types outside the persisted operand and restore
  the layered import gate.
- Retain the existing secure-reference repository as the sole store and
  `apply_cotejo` as the future sole writer; the reviewed diff correctly adds no
  duplicate store, orchestration, or apply path.
- Do not close `W03.P06.S30` until both HIGH findings are fixed and this audit
  is reattested.
- Both original HIGH findings are closed. Remove the three BasedPyright errors
  on the touched parser without weakening checking, rerun the same focused
  parser/operand tests and type gate, then reattest this remaining MEDIUM item
  before closing `W03.P06.S30`.
- Final reattestation completed: both HIGH findings and the MEDIUM parser gate
  are closed, no in-scope blocking finding remains, and `W03.P06.S30` may close.

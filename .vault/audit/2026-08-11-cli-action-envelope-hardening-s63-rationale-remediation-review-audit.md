---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:2939f5579f4e2e2e7dad81529b0b5cd4f8f475b085964100fb3ce6a8e1bb29b8'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# `cli-action-envelope-hardening` audit: `S63 rationale remediation lifecycle review`

## Scope

Independent lifecycle review of open Step S63: the strict `CadrumoError` base contract, the amended plan ownership for `FilingProducerSnapshotError` and `OrdenAnualHtmlParseError`, the two class-local bare-root classifications, their consumers, error-envelope admission, legacy suggestion transport, and the historical-default rehoming join.

## Findings

### s63-rationale-remediation-review | high | PASS: the remediation has one bounded authority and no compatibility restoration

The plan amendment explicitly scopes the base plus the two defining modules and remains open. The only remediation additions are class-local `ClassVar` rationale values. Both classes retain direct `ValueError` bases, are not `CadrumoError` subclasses, and have no declared error-code registry row. `CadrumoError` rejects the retired `suggestion` keyword, and `ErrorEnvelope` rejects a `suggestion` field as forbidden extra input. Both bare-root classes are rejected before envelope construction; neither can create a second action, runbook, renderer, or registry authority.

### s63-rationale-remediation-review | high | PASS: the classifications are inert locale-neutral machine metadata

The two values are stable ASCII hyphenated identifiers, owned in each class dictionary. They carry no command text, action identity, recovery field, locale key, or renderer input. The filing carrier is caught at the Modelo export boundary and converted to registered `ModeloExportError`; the Orden carrier remains in the shared pure HTML parser consumed by the annual-Orden registry compiler. The only runtime reader of the rationale convention is the exception-base hygiene gate, and the class variables are absent from exception instance context merging.

### s63-rationale-remediation-review | medium | PASS: retired suggestion transport has no remaining exception producer or consumer

The production AST census found zero `suggestion` initializer parameters and zero instance attribute accesses. The five remaining keyword sites are ordinary LLM-preview or localized argument names, not exception constructors or envelope fields. Defensive reserved-key filtering retains `suggestion` only to refuse accidental action-context transport; it is not a compatibility path.

### s63-rationale-remediation-review | medium | external | two current failures are outside the reviewed S63 ownership

The real Orden authority lane passes 102 of 103 tests. Its one failure is `test_s24_open_ended_backfilled_revision_has_orden_aplicabilidad[303-2023]`: the test lists `303/2023` as open-ended while the current registry revision declares `valid_to=2023-12-31`. Git blame assigns the test tuple to `e7cbbc4` and the bounded registry record to `182bca5`; both are M303 registry work, not S63. The profile malformed-pointer integration test also remains red before its S63 assertion because quiet profile creation now requires `--tax-residence-jurisdiction-scope`; that contract is owned by the wizard/profile surface.

### s63-rationale-remediation-review | high | PASS: the rehoming source join remains structurally exact

The direct validator reports `E_REHOMING_VALIDATED:238` and the full relocated rehoming suite passes 74 tests. Read-only replay correctly returns `E_REHOMING_MIGRATION_CHECK_CONTENT` while preserving the ledger SHA-256. Regeneration has zero row, disposition, current-error, structural, or ownership delta; its 12 locator-only deltas are peer-owned and S63 owns none.

## Recommendations

Keep S63 open until the coordinating executor performs its plan-state decision; this review does not close the step. Route the `303/2023` disagreement to the M303 registry/test owner, and update the malformed-profile fixture through its wizard/profile owner. Do not register or reparent either internal carrier, add localization for its rationale identifier, or reintroduce exception-level suggestion transport.

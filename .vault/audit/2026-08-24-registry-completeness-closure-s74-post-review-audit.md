---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0c15a42b8665196009c1def58916a6afd2262c56983f6dcad8d83522acf949de'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# `registry-completeness-closure` audit: `S74 Modelo 036 filing-route post-review`

## Scope

Independently reviewed commit `6e51a5c18a` for the Modelo 036 correction:
the authority reference, amended S12 record, S74 execution record, plan state, and
generated feature index. Semantic discovery located the one existing Modelo 036
lifecycle service and the CENSO portal boundary; exact search then checked the
receipt field, CLI boundary, filing-producer vocabulary, and source/export owner
routes. The review also reproduced the Step record's reported focused-test failure.

## Findings

### m036-sede-only-public-docstrings | medium | Existing lifecycle and CLI docstrings still narrow the supported human-filing route to Sede

The corrected reference and execution records accurately state that the operator may
record a Modelo 036 filed through Sede or in person at a competent AEAT office, and
that `sede_justificante` is optional electronic-receipt evidence. However,
`M036DeclarationCommand`, `record_m036_declaration`, and the three command callback
docstrings still say that the declaration was filed "at sede" or "through the sede
portal." The optional field is implemented correctly, but these public descriptions
now contradict the official route and the reviewed registry record. Commit
`6e51a5c18a` deliberately changed no production code, so it did not create a second
writer, model, producer vocabulary, or source route; the stale wording is a separate
documentation-only repair.

The reported focused-test failure is unrelated to S74. The review reproduced
`test_record_refuses_a_command_profile_that_does_not_own_the_bucket`: its empty-event
assertion sees the mandatory `profile.bucket.created` event emitted during profile
setup before the refused M036 command. The reviewed commit modifies Vault documents
only and cannot be the cause. The all-registry filing-capability assertion remains an
explicitly unresolved worklist gate, not a green S74 verification claim.

## Recommendations

Complete `W02.P04.S81`: align the existing M036 lifecycle and thin CLI docstrings
with Sede-or-competent-AEAT-office recording, retain the optional electronic-receipt
meaning of `sede_justificante`, and preserve the no-local-filing boundary. Do not add
any new command, producer, declaration model, source-casilla route, or export path.

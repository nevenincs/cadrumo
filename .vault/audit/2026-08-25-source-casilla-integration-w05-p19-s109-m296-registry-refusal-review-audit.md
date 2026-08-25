---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:81fb39ba0dc8b662d39e91c3dc0cd37bd9b9ae52cbc96249addf1b152ab81524'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-source-casilla-integration-W05-P19-S109]]"
  - "[[2026-08-25-source-casilla-integration-m296-row-source-grounding-research]]"
---
# `source-casilla-integration` audit: `W05 P19 S109 Modelo 296 registry refusal review`

## Scope

Independent review of `6c1236581c` and `ddb6986443`, the M296 census entry,
S109 execution record, source mesh/route, registry revisions, connected-proof
composition, and focused registry-refusal tests.

## Findings

### bounded-registry-refusal | low | The M296 predicate is valid and keeps the row registry-blocked

The 440-character review condition loads through the manifest schema. It retains
`registry_blocked`, the campaign owner, 2026-12-31 expiry, and the owned
2026-11-30 follow-up. The expiry mutation is rejected by census governance.

### intentional-unmeasured-coverage | low | No M296 binding means coverage is correctly unmeasured

Every loaded M296 revision has no `withholding296` binding. The source remains
deferred, has no canonical resolver owner or connected proof fixture, and the
coverage limb is `unmeasured` with the matching refusal reason. This is an
honest absence of a scoped registry destination, not a hidden positive or
refused connection claim.

### separate-withholding-lifecycle | low | Existing M180/M193 retenciones remain real but non-substitutable

The review strengthened the test from a generic withholding disposition check
to prove `retenciones_aggregation` is enrolled and resolver-owned, and bound by
both M180 and M193 revisions. That established lifecycle is distinct from, and
does not promote, the unbound M296 `withholding296` candidate. Direct/manual
M296 paths remain outside source ownership.

### tracking-record | low | S109 now records the implemented refusal rather than leaving a scaffold

The S109 execution record was completed through the Vault CLI. It names the
registry-blocked outcome and intentional unmeasured coverage without claiming a
resolver or lifecycle.

## Recommendations

Approve S109 as the reviewed bounded M296 registry refusal. Reopen only after
an officially grounded M296 binding and the canonical secure row-preserving
owner/lifecycle/export proof are available. Do not reuse M180/M193 retenciones
or a manual path as that authority.

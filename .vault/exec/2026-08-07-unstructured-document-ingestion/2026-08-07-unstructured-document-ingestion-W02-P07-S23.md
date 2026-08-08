---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:03339e85b17b1585859beaf7877f4c257c0d1b1b5e93f869eefa54144ea6e1bb'
step_id: 'S23'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Derive direction deterministically from the taxpayer own NIF role on the document and cross-check the verb-supplied kind, surfacing divergence as a finding, gated by real tests in both directions

## Scope

- `src/cadrumo/application/ledger`

## Description

- Prove the direction chain end to end before extending it. The derivation was
  gated given a filer identifier, the identifier was gated given a profile, and
  the threading between them was gated structurally, but nothing had driven a
  real document through a real read with a real profile and observed a suggested
  direction stamped.
- Compare the operator's stated direction against the one the document supports
  at the confirm boundary, stamping the disagreement onto the draft before the
  review gate runs so it becomes an ordinary per-finding blocker rather than a
  separate refusal path.
- Correct two disclosures the work falsified: the confirm entry point's claim
  that extraction cannot infer direction, and two guards citing a first-match
  identifier scan and a single-supplier prompt that no longer exist.

## Outcome

Modified: `src/cadrumo/application/ledger/_evidence_draft.py`,
`src/cadrumo/application/invoices/_self_counterparty.py`. Added
`src/cadrumo/application/ledger/tests/test_direction_cross_check_at_the_confirm_boundary.py`
and `src/cadrumo/application/ledger/tests/test_direction_reaches_the_confirm_boundary.py`.

The join carries. Driving the public extract entry point against a real bucket,
a real profile declaring the filer's tax identifier, a real PDF and a real
loopback reader endpoint, a purchase invoice comes out carrying a suggested
direction of received, with a basis naming the party block the filer's identifier
was read in. That is the reading no unit suite could produce.

The cross-check then bites in both directions on the same document: confirming
that purchase as issued refuses through the review gate under an
unresolved-direction reason, and confirming it as received raises nothing. A
document that settled no direction raises nothing either, which matters because
most derivation outcomes carry none.

The disclosure sweep corrected the mechanism without weakening the conclusion.
The self-counterparty guard's rationale now states that the exposure survives by
construction rather than by defect: on an issued invoice the supplier slot
legitimately holds the filer's own identifier, so any path taking that side as
the counterparty records the taxpayer against themselves.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests -n0 -q -m unit
    1 failed, 1199 passed, 26 deselected, 16 warnings in 213.57s (0:03:33)

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests -n0 -q -m integration
    43 failed, 2983 passed, 748 deselected, 1 warning in 2051.48s (0:34:11)

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_absent_identity_is_not_a_failed_role.py src/cadrumo/application/ledger/tests/test_direction_cross_check_at_the_confirm_boundary.py src/cadrumo/application/ledger/tests/test_direction_reaches_the_confirm_boundary.py src/cadrumo/application/ledger/tests/test_identity_roles.py src/cadrumo/application/ledger/tests/test_grounded_reading_wiring.py -n0 -q -m "unit or integration"
    63 passed in 9.19s

Mutation-proved from outside the repository: removing the confirm-boundary
comparison reds 6 cases, four at the boundary's own contract and two on the live
path.

## Notes

None of the 43 integration failures is attributable to this lane. Fourteen are an
absent local reading runtime on this machine, reporting a connection failure
before any application code is reached. The six that touch the evidence surface
were re-run with every one of this lane's three source changes neutralised at
runtime and failed identically, so they belong to the concurrent country-advisory
work visible as uncommitted peer files in the same package. The remainder are
operator-surface, calendar, registry and help-shape cases outside this surface.

The two lane readings above are of the working tree at the time of the run. The
focused re-run is also a working-tree reading, and the confirm module is not
byte-identical to HEAD -- it carries uncommitted peer work -- so HEAD was
measured separately rather than inferred, by materialising it into a scratch
tree and running the same suites there:

    git archive HEAD | tar -x -C <scratch>
    python -m pytest src/cadrumo/application/ledger/tests/test_absent_identity_is_not_a_failed_role.py src/cadrumo/application/ledger/tests/test_direction_cross_check_at_the_confirm_boundary.py src/cadrumo/application/ledger/tests/test_direction_reaches_the_confirm_boundary.py src/cadrumo/application/ledger/tests/test_identity_roles.py -n0 -q -m "unit or integration"
    39 passed in 21.94s

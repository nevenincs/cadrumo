---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:df71a63540d6c405593317e95504d7c366bb22bb018b3e98664518cc54825d1f'
step_id: 'S216'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# RULED. Narrow the counterparty role resolver so an ABSENT counterparty identifier is not a role failure while an UNVERIFIABLE one still is. Measured after the filer-id threading landed: every DraftDiscrepancyKind blocks by construction, nine of nine, so a document that simply does not print a counterparty NIF can no longer be confirmed without an individual resolution. A factura simplificada may legitimately omit it and the issuer-establishment module's own docstring calls an ordinary domestic ticket with no identified customer common and legitimate practice, while a receipt carrying no identifiers at all raises role_unresolved where there is nothing to resolve. That is a blocker firing across a large correct population, which trains the operator to clear it unread and destroys its value on the checksum-failure case where it is genuinely right. Rejected leaving it, which blocks legitimate documents, and rejected routing role_unresolved to the advisory channel, which also weakens the checksum case that is the genuine catch. CONDITION on the fix: absence must mean the question was not asked, never that the role is fine, so verify nothing downstream reads an unresolved role as a resolved one

## Scope

- `src/cadrumo/application/ledger`

## Description

- Narrow the counterparty role resolution so a document printing no counterparty
  identifier, or only the filer's own, raises no unresolved-role finding, while a
  printed identifier that fails verification still does. The discriminator is the
  resolver's own unverified-identity findings: nothing rejected means nothing was
  stated.
- Record an identity rejection at the stage that performs it. The reading stage
  drops a checksum-failing identifier to `None` and builds no envelope, so the
  role resolution received it as an absence indistinguishable from a document
  that printed nothing; the rejection now surfaces as an identity-unverified
  finding from `src/cadrumo/llm/_invoice_field_grounding.py`.
- Restate the resolver module's contract and correct the one existing case that
  asserted an unresolved role on an empty candidate set.

## Outcome

Modified: `src/cadrumo/application/ledger/_identity_roles.py`,
`src/cadrumo/llm/_invoice_field_grounding.py`,
`src/cadrumo/application/ledger/tests/test_identity_roles.py`. Added
`src/cadrumo/application/ledger/tests/test_absent_identity_is_not_a_failed_role.py`.

Measured on the live reading path, driving the public extract entry point against
a real encrypted bucket, a real profile carrying the filer's identifier, a real
PDF and a real loopback reader endpoint. Before: a counterparty identifier that
failed its checksum, a factura simplificada carrying only the filer's identifier,
and a receipt carrying no identifiers at all each raised an unresolved role and
each blocked. After: the two absent shapes raise nothing and block nothing, and
the checksum shape blocks under an ambiguous-identity reason that names the
printed identifier that failed.

The condition holds. The resolution still carries no resolved value under an
unanchored envelope whose note says the document stated nothing, and the confirm
path treats an absent extracted identifier as a required operator input rather
than as a settled one, so no consumer can read the withheld finding as a
resolved role.

A finding for the plan, not worked around: the resolver's unverified-identity
branch is unreachable from the model reading path, because the grounder rejects
the value before the draft is built. That is why the rejection had to be recorded
upstream; without it the narrowing would have silently stopped blocking the one
case it must keep blocking.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests -n0 -q -m unit
    1 failed, 1199 passed, 26 deselected, 16 warnings in 213.57s (0:03:33)

The single failure was `test_identity_roles.py::test_a_document_stating_no_identifier_resolves_to_an_unresolved_role`,
which asserted the behaviour this Step rules out; it was corrected to the new
contract and the suite re-run:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_identity_roles.py -n0 -q
    18 passed in 0.99s

Mutation-proved from outside the repository, by a pytest plugin on `PYTHONPATH`
that rebinds the production symbols at configure time and asserts an observable
behaviour change before reporting:

- restoring the unresolved-role finding on an absence reds 4 cases across the
  unit and live-path suites;
- removing the reading stage's rejection record reds 2, including the live-path
  case that proves the checksum document still blocks.

## Notes

The failing unit case above is the only in-scope regression; it encoded the prior
contract and was corrected rather than accommodated.

A repository sweeper committed this lane's source edits mid-flight under
`a629434f9eae7a2e243dc62c1e35b8749c21c444`; the corrected existing case landed
separately as `ceda8e1cf6a8aef75dc3e3f8ab5768880e66ebfb`.

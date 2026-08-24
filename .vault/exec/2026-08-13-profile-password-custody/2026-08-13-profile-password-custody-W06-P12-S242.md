---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:14273333b5f6b8bd9b3ba1eb70a7a2382a746dab389a5ceb96be56d97134e1b3'
step_id: 'S242'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Regenerate every affected documentation sequence golden through the owning CLI after live behavior is adjudicated and reconcile frame counts without hand-authored output

## Scope

- `docs/_sequences/`

## Description

- Enumerated 23 affected sequence IDs from the S240/S241 contract commits.
- Regenerated every ID exclusively through `dev.docs.sequences refresh --sequence`; 20 generated JSON files changed and three were already byte-current.
- Rechecked every affected sequence through the owning CLI and reconciled its generated frame structure against the current contract.

## Outcome

Complete. The 20 generated golden changes landed concurrently in `90ada31ea4`; this closure records the independently executed owning-CLI refresh and verification without claiming unrelated work.

## Notes

- All 23 affected single-sequence golden checks passed.
- Parser/compare/contract proof passed `61` tests; documented-command conformance passed `349` tests.
- The mandatory full run was executed and remains red outside the adjudicated S240/S241 set: `148` golden divergences and `12` cumulative page-coherence failures across broader registry, operation-runtime, workstation-hardware, profile-channel, and stale-contract surfaces. No unadjudicated golden was refreshed.
- A compact rerun after concurrent commits reduced cumulative failures to 11 pages while the golden inventory remained 148 divergences across 23 pages. The residual clusters are disjoint:
  - Profile/recovery provisioning: `check-aeat-notifications`, `quickstart`, `profile-setup`, and `troubleshooting`; migrate stale create/login fixtures to verified recovery and repair profile status/list composition.
  - Operation-composition runtime regressions: `classify-with-llm`, `import-bank-statements`, and portions of `modelo-390`/`troubleshooting`; restore the missing production operation projections before rerecording.
  - Filing-spine cumulative state: `filing-spine`; reconcile once-per-page seed reuse and the missing `latest-draft` selector target.
  - Registry/revision and page-contract drift: `how-renta-is-assembled`, `choose-modelo`, `filing-calendar`, `filing-readiness`, `first-quarterly-filing`, `irpf-lifecycle`, `iva-lifecycle`, Modelos 100/130/303/349/390, and `review-calculation-values`; adjudicate current registry authority and revision IDs before refresh.
  - Ledger/invoice dynamic output: `ledger-evidence` and `manage-invoices`; adjudicate current evidence/catalogue identities and counts, then refresh their distinct contracts.
  - Verification history/provenance: `verification-reports`; adjudicate M303 provenance IDs and the work-history frame-count change.
  - Censal projection: `censo-update`; reconcile the changed validation/fact payloads.
  - Host diagnostics: `workstation-setup`; centrally mask volatile free-memory facts while preserving registry-integrity failures, then refresh.
- The scoped S241 cumulative pages had already passed before refresh: authentication, Modelos 100/130/303/349, and ledger evidence.
- Formal review verified CLI ownership, scope, and frame reconciliation.

---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:1b6b5f68be47ad1d6a1f6636eea947dc1abcd29280b6102a5b6d34701f4d1cb7'
step_id: 'S27'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

# Supersede the topology ADR through the pipeline rather than the in-place rewrite already landed, the superseding record must answer the two deleted objections, sibling-serving answered by the shared repo and no-precedent answered by verda-cloud/homebrew-tap carrying Formula and bucket together, and must reconcile the scoop-runner-topology ADR explicitly as unaffected because it rules on which runner executes the lane not where manifests live. Ownership is with account-distribution-lead if its account-wide ruling subsumes the cadrumo scope, asked 2026-07-25 and awaiting reply. GATE, vault check all passes and the superseded record carries superseded_by

## Scope

- `.vault/adr`

## Description

- Author a new ADR that supersedes the topology record through the pipeline, rather than editing it a second time.
- Answer the sibling-serving objection: an in-repository bucket is product-scoped by construction and cannot serve a sibling.
- Answer the no-precedent objection with a precedent verified at source.
- Reconcile the Scoop runner record explicitly as unaffected, stating the orthogonality rather than leaving it derivable.
- Apply the supersession through the owning verb so the superseded record carries a machine-readable pointer.

## Outcome

The superseded record now carries a `superseded_by` pointer and a `superseded` status, and its body is untouched: it stands as the historical account of what was decided at product scope.

Both deleted objections are answered on their merits rather than removed. The sibling-serving objection is answered by observing it optimised the wrong count, minimising repositories created while leaving per-product user commands growing linearly. The no-precedent objection is answered by a production account carrying a populated `Formula/` and `bucket/` side by side in one repository, confirmed by direct structured query against its contents rather than inferred from documentation.

The Scoop runner record is reconciled as unaffected, with the reason stated: it rules on which runner executes the evidence lane, this record rules on where the manifest lives, and retargeting the bucket changes the URL the lane names and nothing else. Its operator gate is unchanged and still open.

## Notes

A new feature tag was needed because the record could not be scaffolded under either existing one: both the account-standard and the topology ADR already occupy their feature-and-date filename, and a topic infix is not permitted for decision records. A false date would have been the alternative and was rejected.

The cost of a third record on adjacent questions is real and is recorded in the Consequences section rather than glossed. It was accepted because the only alternative was a third in-place rewrite of an accepted decision, which is precisely the defect this record exists to correct.

The record deliberately does not restate the account-wide substance it depends on. The derived matrix, the release mechanism, the naming rule, and proportional evidence are owned by the account-standard ADR and are cited rather than duplicated, so they cannot fork.

The step's ownership question, whether the account-wide ruling subsumes the cadrumo scope, is resolved in the affirmative and stated in the record: this is the topology half of the account standard applied at the scope the superseded record occupied.

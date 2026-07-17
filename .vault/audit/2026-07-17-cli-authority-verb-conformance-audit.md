---
tags:
  - '#audit'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-adr]]"
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
  - "[[2026-07-16-cli-authority-verb-conformance-duplication-authority-audit]]"
---

# `cli-authority-verb-conformance` audit: `Rescope and split closure`

## Scope

This record documents the disposition of the 254-step `cli-authority-verb-conformance` implementation plan. The plan is being RESCOPED AND SPLIT into six smaller, individually-closeable successor plans. It is not abandoned, and it is not being falsely completed. Every step that has not actually landed remains unchecked in the monolith plan; no undone step was marked done to manufacture a clean close.

The governing decision record remains accepted and unchanged. The duplication-authority audit's thirteen-cluster table remains the successor index that maps each cluster to its new owning plan. All execution records for landed steps are preserved. What is retired is the 254-step plan structure and its W05 contract-migration and W06 whole-surface verification ceremony, not the work itself.

This record exists to honor the plan-closure discipline: a plan may only close against execution evidence, or against an explicit rescope note naming its successors. This is that note.

## Findings

### rescope-disposition | high | The monolith plan is superseded by six successor plans, not closed as complete

The plan stands at 64 of 254 steps complete. The remaining 190 steps are redistributed across six successor plans, each cut vertically so that a family's backend authority, its CLI door, its contracts, and its documentation land together and the plan can close on its own focused verification. The successor stems are `2026-07-17-duplication-evidence-repair-plan`, `2026-07-17-auth-cert-recovery-custody-plan`, `2026-07-17-all-profile-reset-plan`, `2026-07-17-ledger-evidence-atomicity-plan`, `2026-07-17-export-publication-plan`, and `2026-07-17-cli-authority-quality-backlog-plan`.

### completed-clusters | medium | Four clusters have genuinely landed and carry execution evidence

The active-profile pointer and strong-logout cluster is complete: atomic pointer handling, rollback, contention, session eviction, provider teardown, key zeroization, engine disposal, override refusal, and close-before-clear logout all carry recorded evidence. Authentication custody is complete: typed target-scoped logout and reset operations replaced the broad clear, with distinct schemas, events, contract metadata, four-locale help, and real workflow tests. Certificate custody is complete: the certificate-specific keyring backend, selector, factory branch, and exports are deleted, and selected-profile secure storage is the sole certificate-secret authority, with crash-resumable set and remove proven against real secure storage. Passphrase and recovery custody is complete: distinct typed recovery operations, file-only custody, preserved envelopes across verification, and secret-free serialization all carry proofs. The architecture-measurement prerequisite is likewise complete and gates every successor.

### cutover-fiction | medium | The indivisible W04 and W05 cutover was not a real constraint

The plan asserted that command removal and contract migration form one indivisible release checkpoint spanning the whole campaign. The logout family disproved this by landing independently with nothing broken. The real invariant is narrower and per-family: a removed spelling, its payload schema, its write-policy token, its four locales, its Model Context Protocol mirror, its help and risk metadata, its error suggestions, and its regenerated documentation must move in one change for that family. Standing conformance gates run green after each vertical and serve as the continuous cutover checkpoint. Only serialization on genuinely shared files needs coordinating.

### honest-closure-reframe | medium | Honest closure means valid evidence and no false-green, not zero clones

The decision record keeps the clone count advisory. Sixty-five clone groups at 0.41 percent duplicated lines is low debt. An amber verdict carrying a measured count is an acceptable close; what is not acceptable is a green verdict produced without valid evidence, which is the defect the duplication runner repair exists to remove. Clone disposition belongs in a triage pass classifying each group as cluster-owned, intentional, or advisory residue, not in a sixty-five-item elimination campaign.

## Recommendations

Execute the successor plans in operator-safety order. Duplication evidence repair comes first because a false-green health verdict corrupts every later judgment. Authentication, certificate, and recovery custody follows, absorbing the already-landed backend work and finishing only its CLI doors and contracts. All-profile reset follows because it carries the worst outstanding safety defect: reset can delete the active bucket and leave a dangling pointer while bypassing retention. Ledger evidence atomicity precedes the language-model split work because they share split persistence. Portable export and publication follows. The quality backlog absorbs the residue and may be scheduled against spare capacity.

Each successor plan closes with its own focused verification and its own mandatory fresh-context honesty review, per plan rather than per epoch. The whole-surface verification ceremony dissolves into continuous CI conformance per landing.

Preserve on archive: the decision record, the cluster table and its intentional-non-consolidation inventory, and every execution record. Do not delete them.

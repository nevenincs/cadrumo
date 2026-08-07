---
name: plan-closure-requires-exec-records
trigger: always_on
---

# Plan closure requires exec records

A plan step must not be marked complete unless a matching exec record exists, or
the close audit explicitly records why the step is only a deferred
carry-forward.

Step checkboxes are the operator-facing truth only when backed by execution
evidence. Closed audits have found steps already checked with no execution
record, and implementation complete while its plan still showed zero progress —
both making the handover impossible to trust and hiding the real remaining work.

Three distinct states otherwise wear the same checkbox: delivered as specified,
delivered against a narrower scope, and recorded-but-not-implemented.

## How

- **Good:** create one `.vault/exec` record per completed step before or
  alongside marking it checked, then rebuild the feature index and run
  feature-scoped vault checks.
- **Good:** leave a step unchecked when it is intentionally deferred, and name
  the follow-up campaign or blocker in the close audit.
- **Bad:** marking a step checked based only on code inspection, or claiming a
  campaign complete while plan status reports missing exec records.

**An ADR amendment that rules on CODE is not self-executing.** The amending
Step's deliverable is "the record is correct", which is genuinely complete the
moment the prose is right — so it closes honestly while the implementation debt
it created has no owner and no row, and every later reader sees the ruling as in
force while HEAD still carries the rejected design. Open the implementing rows in
the **same action** as the amendment, before closing the amending Step, and name
them in its exec record. If a ruling reverses a shipped design, grep the source
for prose describing the old state as pending or undecided.

**"The ADR says X" is not evidence that X is true of the tree.** Verify rulings
against HEAD the way you verify any claim.

Companion: `aeat-campaign-close-honesty-review`.

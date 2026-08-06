---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:883797dab7525b7169ff1c3f9fafa116e65f8b3095df81db5c75502d84a70bb6'
step_id: 'S242'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Correct namespace registry metadata drift and make each namespace definition the sole authority for identifier, schema version, sensitivity, default object key, key grammar, owner, and custody

## Scope

- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`
- `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`

## Description

- Establish that this step duplicates a step already closed under a sibling backlog plan.
- Read the namespace definition model and confirm it carries all seven authority fields the step names.
- Confirm the two drifted key grammars the step calls out were corrected, by reading the live compiled values rather than the commit message that claims it.
- Run the registry suite at the current commit.

## Outcome

Already satisfied. Closed as verified rather than re-implemented.

The definition model is a strict frozen pydantic model carrying every one of the seven axes the step enumerates: the registry key and the namespace identifier, the owner, the sensitivity class, the envelope schema version, the object-key grammar, the optional default object key, and custody as the scope plus custody-disposition pair. Each is a required field except the default object key, which is legitimately absent for the multi-row namespaces. There is no eighth home for any of them.

The metadata drift the step names was corrected under a commit that states the correction precisely, but a commit message is a claim, so the live compiled values were read instead. The transaction catalogue grammar now reads as the per-transaction row shape followed by the per-bucket membership index, which are the two key shapes the repository actually writes; it previously declared a bucket-scoped catalogue key that was in fact the audit event object id, not a secure-object key at all. The calculation-observations grammar now carries the optional per-member trailing segment that the per-grupo-member fan-in writes, which the earlier value omitted. Both are descriptive metadata with no runtime key derivation reading them, so the correction is behaviour-preserving, and both now describe the live shapes.

Sole-authority enforcement is a real gate rather than a docstring claim. The registry suite pins the full inventory at sixty-six rows, asserts every namespace and every owner uses the current product prefix family, asserts no row retains a retired product prefix, and pins the exact key-namespace-owner triple for each of the five rows whose namespace still contains the tax-authority segment, so a rename cannot quietly move one. Custody is covered twice: every row is asserted to declare an explicit custody disposition, and the custody-profile projection is checked against worked examples that assert both membership and non-membership, including a namespace deliberately excluded from both profiles. Non-membership assertions are what stop that projection test passing on an over-broad profile.

Run at the current commit as part of a thirty-four test run covering the registry suite and both namespace adoption gates: all passed. No change was needed or made.

## Notes

Semantic code search was degraded and reported itself healthy, with an empty degraded-reasons list. A probe naming the secure-object namespace registry and its schema-version and sensitivity fields returned hits only from an unrelated inbound terminal-interface module and a theme re-export, and the registry module itself did not appear. That is the truncated-index signature, so every finding in this record was reached by direct read and targeted grep, and the registry values were confirmed by importing the compiled definitions and printing them rather than by reading the source declaration.

The inventory count in the sixty-six-row assertion is a hardcoded figure in the test name as well as the body. It ratchets correctly, in that a newly registered namespace fails until the count is updated deliberately, but the count living in the test name means a future correction has to rename the function. Worth noting, not worth changing under this step.

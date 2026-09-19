---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:1ddfbfd5bbfb5e46289ba65ccbea674978cacc8b4f53976bd81fffcf2f24d7c0'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# `object-name-declustering` audit: `s12 rehearsal tests review`

## Scope

Reviewed the S12 rehearsal detector-teeth suite against the accepted object-name
declustering ADR, research, reference, plan, the final S11 audit, and the current manifest,
graph, transform, and rehearsal contracts. The review covered exact dirty-tree capture,
tracked deletion and exclusion behavior, disposable-copy fidelity, component authority,
generated-owner execution, command isolation and failure behavior, receipt identity,
retained evidence, source immutability, and pre- and post-command allowlists. No production
or test code was modified by the review.

## Findings

### receipt-identity-teeth | medium | Constant or incompletely bound receipt identities would pass

The determinism test repeats an identical silent rehearsal and checks equality, while the
main success test checks only that receipt and evidence identifiers resemble non-empty
SHA-256 values. A constant identifier would satisfy both tests. No mutation test proves that
manifest, inventory, baseline/input/proposed bytes, tool versions, operation/component,
changed paths, finding delta, argv, or return code changes the stable receipt identity; nor
does a volatile-output test prove equal stable identity but distinct evidence identity.
This leaves the immutable authorization binding without non-tautological regression teeth.

### copy-verification-teeth | medium | Copy hash verification can be removed without failing the suite

The success fixture confirms that an ordinary copy contains expected dirty and untracked
bytes, and injected copy failure confirms retention. It does not corrupt one copied byte
between transfer and verification and require refusal. An implementation that still copies
normally but drops its source-to-target digest comparison would pass all current assertions,
so the exact verified-copy precondition is not protected.

### no-shell-teeth | medium | Command tests do not prove shell metacharacters remain inert argv

The suite verifies command argv in receipts, temporary working directory, installed-runtime
environment, timeout, non-zero output evidence, and retained failure state. It never passes a
metacharacter-bearing argument with a sentinel file that would be created only by shell
interpretation. Receipt argv equality is independent of how the subprocess was launched, so
joining or shell-enabling the command could evade the present tests.

### indivisible-component-teeth | medium | No shared hard-edge fixture rejects a partial component

The multi-component test proves that one independent component can be rehearsed while a
second is left unchanged, and component-field and generated-owner forgeries are rejected.
It does not create two operations coupled through one shared consumer or generated surface
and then submit only one operation. The central connected-component indivisibility contract
could regress while these independent-component and single-operation forgery tests remain
green.

## Recommendations

Add exact sensitivity tests that independently perturb every stable receipt binding, plus a
random-output command proving stable `receipt_id` and changed `evidence_digest`. Inject a
post-copy byte corruption and assert refusal before transformation. Pass shell metacharacters
as one literal argv item and assert that no sentinel side effect occurs. Build a two-operation
fixture with a real shared hard edge, prove the canonical component contains both operations,
and prove a forged one-operation subset is rejected. Preserve the existing strong coverage:
dirty, untracked, and tracked-deleted bytes; metadata/cache/link exclusions; generated-owner
success and forged ownership; cwd/environment/timeout/failure evidence; retained temporary
roots; write guards and concurrent live mutation refusal; and exact projected and final
allowlists.

## Validation

The focused suite passed 23 tests. Ruff, Ruff-format, and ty checks passed. Final review
status is four medium findings and no critical, high, or low findings.

## Re-review status

Resolved: `receipt-identity-teeth` now independently recomputes both receipt hashes from the
serialized production payload, first proving the emitted values are exact and then mutating
manifest, inventory, component, operation, baseline, input, proposal, path, finding, tool,
gate, and source-immutability fields one at a time. Every stable mutation changes
`receipt_id`, while a stdout digest/size mutation preserves `receipt_id` and changes
`evidence_digest`. A constant ID or omitted stable field therefore fails the test.

Resolved: `copy-verification-teeth` replaces the real copy primitive with a wrapper that
corrupts the copied declaration immediately after transfer. The public rehearsal entry point
must refuse the mismatched target hash and retain the disposable root, so ordinary successful
copy behavior cannot make the test pass after digest verification is removed.

Resolved: `no-shell-teeth` passes a shell-metacharacter expression as a literal child-process
argument, has the child assert exact argv preservation, verifies the receipt records that
exact vector, and proves the shell-only sentinel path was not created. This protects the
argv/no-shell execution contract without mocking the command runner.

Resolved: `indivisible-component-teeth` creates two real declarations and one real importer
that statically imports both names. The reviewed graph contains both operations joined at the
shared consumer, and the public rehearsal boundary rejects a component forged down to one
operation. The test therefore distinguishes independent multi-component selection from an
invalid subset of one connected component.

The amended focused suite passed 27 tests in 59.10 seconds. Ruff, Ruff-format, and ty checks
passed. Final S12 status is no open critical, high, medium, or low findings.

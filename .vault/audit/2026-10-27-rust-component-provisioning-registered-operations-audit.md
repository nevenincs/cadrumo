---
tags:
  - '#audit'
  - '#rust-component-provisioning'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:3a74962f777bb858af50c6e86974507dd777a6446e1a6a655836fbd93717a284'
related:
  - "[[2026-10-26-rust-component-provisioning-plan]]"
  - "[[2026-10-27-rust-component-provisioning-human-review-authority-adr]]"
---
# `rust-component-provisioning` audit: `Registered component operations backend checkpoint review`

## Scope

Terra 6.1 xhigh reviewed the implemented backend portion of S01 at checkpoint `8679cc2016`, including the four registered component operations, the sole native client composition gateway, development-only role-image forwarding, cancellation, process ownership, reviewed plan digests, effects and recovery. The owner selected this reviewer in place of unavailable Opus. Verdict: PASS for this bounded backend checkpoint. S01 remains open: the accepted human-review claim authority is not implemented at this checkpoint, and CLI, TUI, MCP and desktop migration remain subsequent work.

This review does not claim full-suite, conformance-wide or native-package gates. Native behavior was exercised against the existing CMake-built role image and actual Windows-contained Python wire processes. No model was pulled and the real setup review test used a counting proxy with zero CONNECT requests.

## Findings

### full-status | high | Corrected full checks preserve network-read admission

The first implementation could only issue quick status. The reviewed implementation keeps `config.provision.status` local and maps the full-check `config.provision.verify` admission to native `status --full`, with no quick timeout. The accepted registered-operations ADR clarifies this mapping. Supervisor and role-argv tests cover selected local_ai and quick/full distinctions. Frontend probe and verify retain their different exit/render behavior during S02.

### reviewed-digest | high | Corrected foreign followers preserve UNKNOWN and request a new review

The native engine can follow a busy browser before comparing approval. The gateway now checks the FOLLOWING plan digest against the reviewed approval and refuses a foreign plan. Both an immediate follower result and an unresponsive follower retain UNKNOWN and return typed `followed_plan_mismatch` with `new_setup_required=true`. Truthful text in all four locales asks for a new setup/review without claiming that another process downloaded nothing. Safe native item, items, rows and failure-category facts survive in the encrypted public refusal detail. See `src/cadrumo/entrypoints/components_operation_composition.py:91` and `src/cadrumo/application/components_operations.py:279`.

### consumed-recovery | high | Corrected continuation cannot replay an apply with a recorded effect

Recovery previously blocked only UNKNOWN, leaving an UPDATED-before-result crash window. The continuation now refuses every retained effect other than NONE before either applying or rejecting a consumed review. Tests cover UNKNOWN and UPDATED recovery. See `src/cadrumo/application/components_operations.py:372`.

### bounded-cancellation | high | Corrected cancellation cannot block on an unread role pipe

Cancellation delivery is idempotent and runs off the event loop. A fixed grace period from the first cancellation bounds a role that ignores it, and contained termination owns the exit proof before releasing native handles. Faithful fixtures invalidate wait-after-close; actual Windows job-contained Python wire tests cover clean CANCELLED and an unresponsive process without a closed-handle refusal overriding the result. See `src/cadrumo/adapters/outbound/components/client.py:164` and `src/cadrumo/adapters/outbound/components/client.py:515`.

### retained-cleanup | high | Corrected failed containment retains the exact launch and prevents settlement

A containment failure must not become a normal execution refusal or foreign-plan mismatch. The client retains the complete launch in canonical asynchronous cleanup resources, including streams and the failed native scope, and the gateway enrolls those resources under the supervisor. The lifecycle test proves persistent failure leaves UNKNOWN, no terminal receipt and the exact retained launch; opening the explicit release gate and using canonical retry releases that launch. See `src/cadrumo/adapters/outbound/components/client.py:305` and `src/cadrumo/entrypoints/components_operation_composition.py:66`.

### cached-cleanup | medium | Existing failed cleanup task prevents automatic settlement after release

The generic supervisor caches its failed cleanup task. Canonical resource retry can release the process, but does not clear that cached failure or create a terminal receipt in the same resumed supervisor. The lifecycle test records the resulting nonterminal UNKNOWN state. This pre-existing framework limitation was not changed in the checkpoint. See `src/cadrumo/application/operations/_supervisor_settlement.py:359` at `8679cc2016`.

### cancellation-revision-race | medium | Static event and cancellation revision concern remains unproved

The reviewer identified a possible stale-revision overlap between an event and cancellation, rather than a reproduced defect established as introduced by this patch. No speculative supervisor change was made. The implemented event change preserves CANCELLATION_REQUESTED when writing safe-stop progress or notices; independent runtime concurrency work remains outside this checkpoint.

## Recommendations

Continue S01 with the accepted explicit human-claim authority. Preserve the original MCP invocation, verify the separate person session, journal the successor checkpoint, and retain the current single-use broker response fences. Do not close S01 from this partial PASS or claim frontend migration is complete.

Passing evidence for this checkpoint:

- Focused native client and registered supervisor files: 47 passed in 134.05 seconds, log `20261027T091239.155395Z-pytest-48124-16923e78`.
- Relocated model-selection and native review acceptance cases: 8 passed in 200.97 seconds, log `20261027T090900.625958Z-pytest-66480-918978c5`.
- Development role-image environment/declaration boundary: 13 passed.
- Configured `just check-types`, `just check-style`, `just check-format` and `just check-operation-contract-manifest` passed. The type gate's two unrelated provider-auth test-tool diagnostics were corrected; five affected admin ingress cases passed.
- Configured `just check-import-boundaries` passed in 288.328 seconds with an unchanged authoritative source snapshot, all 4,948 governed modules loaded, zero hard findings and zero architectural debt. Log `20261027T090105.431503Z-check-import-boundaries-66972-28c62482`. This whole-tree run preceded the final retained-cleanup correction; focused type, lint and behavioral checks passed afterward. It is not evidence for the forthcoming claim implementation.

The bounded checkpoint review is complete. Review the claim authority and later surface integration separately, and rerun required configured gates on their final source.

---
tags:
  - '#audit'
  - '#rust-component-provisioning'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:9676ab18da2b8601a5653d26d3ef360839b9acf018dc4db9e2c4f07c2fa5adea'
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

## S01 human-claim backend re-review

Terra 6.1 xhigh reviewed the integrated backend subsequently committed as `ec51298ef8`. Verdict: PASS for S01 backend, with no remaining high-severity source finding. All setup responders, including the original human submitter, explicitly claim the displayed current review. The generic response guards of other operations remain unchanged. CLI, TUI, MCP frontend migration and the desktop claim relay remain S02 through S05 work.

### claimant-scope | high | Corrected claim holds REVIEW and RESPOND with original START

The initial claim fence checked claimant RESPOND alone. The accepted decision requires current REVIEW as well. The final request resolves and holds the claimant's fresh REVIEW and RESPOND scope and the original invocation's START scope through the protected decision. Independent human disclosure authority is resolved freshly rather than copied from the MCP admission. Explicit original-submission session binding prevents generic reentry from substituting a later live human for a retired MCP invocation. Original execution provenance and COMMIT admission remain unchanged.

### decision-time | medium | Corrected setup decision time is stamped by the runtime

A client-declared response timestamp previously entered the consumed proof and could cause a one-shot refusal after consumption. Setup responses now receive the runtime's decision time under the verified fence before consumption. The application no longer infers authority from client clock ordering. Future and past client timestamps are tested against the real persisted server consumption timestamp; other operation timestamp contracts are unchanged.

### claim-lifetime | medium | Corrected state and handles retire with their authority

Unknown operation ids do not allocate persistent review locks. Refcounted transient lock contexts retain waiting callers safely and disappear when unused. Terminal state, session retirement, expiry and close discard claimant state and zero the retained broker handle. A current holder's identical original-reference retry is idempotent only while its exact authority and checkpoint remain current; it creates no second journal revision.

### retirement-overlap | high | Verified production permit keeps both retirement guards held

The synchronized tests execute the production worker authorization permit exchange and release handshake with the new typed human-review scope. In-memory admission and channel ports expose exact event handshakes: neither test principal can retire while the protected decision is held, retirement proceeds after explicit release, and a fresh request is then refused. These are not described as an actual native-session race. Real runtime tests separately cover refusal after each principal retires. Source review of the nested production guards plus both forms of evidence closes the bounded fence finding.

Passing evidence on the frozen shared-worktree source:

- 25 focused authority cases passed in 67.05 seconds, including four real-runtime/native-role variants, parent proof refusal, independent legacy proof reconstruction, closed public wire parsing and unchanged response-scope regressions. Log `20261027T094730.001531Z-pytest-58724-e015ca09`.
- 50 updated component/client cases passed in 75.32 seconds, including claim, no-replay, cleanup and recovery fixtures. Log `20261027T095120.509421Z-pytest-16128-96c277fc`.
- 50 focused permit/custody-expiry cases passed in 4.31 seconds, including both synchronized retirement guards and recording operation-owner fixtures. Log `20261027T095900.444713Z-pytest-44052-cdb1c829`.
- The configured type, style, format and operation-manifest checks passed after the fixture corrections. The final configured import gate passed in 344.038 seconds with identical before/after snapshot `74e097d3073ae736fec2ee696f33cf70318896d7ec6159411e77fda79e92368c`, all 4,948 governed modules loaded, and zero hard findings or architectural debt. Log `20261027T101035.705132Z-check-import-boundaries-55844-3d5218e6`.

There is no new end-to-end API-key-origin claim test. Coverage combines the new parent key-method refusal with existing native key admission and response-scope regressions; this limit is explicit. The pre-existing cached failed cleanup-task limitation recorded above remains unchanged. No full or conformance-wide suite was run.

The code commit isolates only provisioning hunks in the three shared worker files. Unrelated executor, human-proof offload and Windows transport changes remain in the working tree. The tests and gates describe the shared source snapshot, not an isolated export of the commit. S01 is ready to close; S02, S03 and S04 then proceed in parallel, followed by S05 and the integrated plan-close review.

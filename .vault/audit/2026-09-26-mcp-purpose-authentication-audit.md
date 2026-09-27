---
tags:
  - '#audit'
  - '#mcp-purpose-authentication'
date: '2026-09-26'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:ac174f37febdd5d40aac5501a7a3d701a39af49fdb3f61811d16947f8eb362ce'
related:
  - "[[2026-09-26-mcp-purpose-authentication-plan]]"
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-reference]]"
  - "[[2026-09-26-mcp-purpose-authentication-research]]"
---

# `mcp-purpose-authentication` audit: profile authorization and custody

## Scope

Review of P01.S01 on 2026-09-26: both feature ADRs, the five focused predecessor amendments, the TUI platform's MCP ownership row, supporting evidence and the plan's authorization boundary. This is a design-contract review, not product-code or native-platform acceptance. No product source changed.

Traced enrollment and failed delivery, fresh autonomous connection, human expiry, current-session lock, profile-wide suspension, key/grant revocation, password/recovery transition, restart, authority/provider separation and all CLI/TUI parity rows. Compared the custody design with the existing AEAD, receipt and session-admission owners, and the runtime design with existing operation submission, response authority and journal ownership.

Result: PASS for P01.S01. No critical or high finding remains in this reviewed scope. Product implementation and its platform validation remain open.

Phase 1 review on 2026-09-26: P01.S02 is complete under the operator's explicit single-agent assignment. Reviewed the four new `access_*` application modules, their owning `test_access_policy.py`, the four generated import-load targets, and the Plan/Reference updates named in the S02 ledger. Re-read both accepted feature decisions and their governing custody, session, operation, TUI, CLI-envelope and published-authority boundaries. The earlier P01.S01 review remains historical; this review covers its interaction with the new contracts.

Traced exact-profile and custody binding, connection/client identity, live grant/key/session validity, narrowed descendants, expiry and rollback, period/disclosure intersection, current definition digest/frontend checks, fresh administration consent, session versus global lock, independent readiness, and lost response authority. Reused the existing operation registry, strict model and UTC owners. No new executor or mutable authorization singleton is registered.

Result: PASS for Phase 1. No critical or high finding remains in the reviewed S02 scope. All 327 owning profile tests pass, including 43 new policy cases; the existing catalogue's nine tests pass with their limits recorded in the Reference. Ruff, format, ty, pyrefly, basedpyright and the complete import gate pass. The import gate kept 15 contracts and loaded 2,890 modules without failure. No durable custody, runtime, frontend or platform acceptance is implied.

Lifecycle follow-up and P02.S03 review on 2026-09-26: the continuity assignment explicitly authorizes the focused amendments, contract follow-up and custody implementation. Reviewed the three changed access modules, their tests, the new application custody port, four automation custody adapter modules, owning custody tests and narrowly merged import inventory. These surfaces are named in the S02/S03 ledger. Historical findings below are preserved.

Result: PASS for the focused lifecycle-contract and S03 custody/port implementation review, with native readiness and concurrent-tree gate limitations recorded below. No critical or high source finding remains in this scope. The final focused run passes 81 cases; the broader profile/custody run passes 971 with 14 excluded by its marker expression. The later port ownership correction is covered by the final focused run. Ruff/format and ty/pyrefly/basedpyright pass. A final standalone architecture check keeps all 15 contracts. Phase 2 and installed autonomous access remain open.

P02.S04 handoff review on 2026-09-26: the operator's continuation authorizes enrollment implementation as a single agent, ending before P02.S05. Reviewed the new consent/service/operation modules, custody/control and client-delivery changes, password-proof classification, error-registry and production-composition enrollment, owning tests and narrow generated inventory updates listed in the S04 ledger. The Reference owns current implementation facts and the refreshed operation census; historical review findings remain intact.

Result: PASS for the S04 application/custody protocol scope, with no remaining critical or high finding in the owned changes. The broad profile/custody/catalogue/executor run passed 1,069 tests with 14 deselected. After review corrections, the final run passed all 100 selected feature tests plus 44 core-error tests; one core source census failed solely on the separately owned runtime exception and one native test was excluded. Ruff/format (19 Python files), ty, pyrefly and basedpyright pass. The final import graph keeps all 15 contracts with zero hard subordinate findings; complete loadability remains unavailable because unrelated runtime inventory and source changes invalidate the gate. Native and installed acceptance remain open.

Phase 2 close review on 2026-09-27: inspected the S05/S06 ledger surfaces and their interaction with completed enrollment, exact custody, admission, protected publication and profile lifecycle transitions. Traced password/key admission, child narrowing and cascade, two-login provenance, concurrent unwrap versus revocation, current-session lock versus global suspension, password-only unlock with native custody unavailable, selected grant resume, password/recovery/delete and same-root restore. Reviewed defining services and tests directly; no subagent or native-platform success is inferred.

Result: PASS for the Phase 2 application/custody implementation. No unresolved critical or high finding remains in this scope. The broad owning run passed 1,129 tests (14 deselected). After the final human-unlock change, 92 focused cases passed; the sole failed new assertion used the canonical error code where the custody reason was intended, and its corrected rerun passed. Ruff/format, ty, pyrefly, basedpyright and the stable full import gate pass (15 contracts, 2,916 modules loaded, zero failures). Native credential-store success and installed runtime/frontend enforcement remain the explicit later acceptance obligations.

## Findings

### execution-scope | low | Product execution remains separate from design acceptance

The user's original request explicitly scoped this session to purpose/design. Their post-handoff continuation authorizes completing the design prerequisite, but should not silently erase that original boundary. The plan now records scoped P01.S01 authorization and a pending clarification before P01.S02 product edits. The ADR acceptance statements no longer claim that their status alone authorizes implementation. No source edits occurred during the review.

### native-store-contract | low | Native behavior requires later implementation evidence

The settled contract selects native credential stores and refuses arbitrary positive-priority keyring backends. Its revision/digest witness, staged publication, verified delivery and persistent denial behavior are explicit. No native read/write, crash injection, platform service install or descendant-cleanup test ran here. P02.S03-S06 and P03.S10-S11 retain those obligations; documentation PASS cannot be used as their result.

### shared-operation-owner | low | MCP integration has one assigned owner and an open conformance obligation

The accepted runtime decision composes the existing application operation services. TUI architecture W07.P17.S339 now consumes this feature's future MCP integration evidence and remains open. It does not independently implement another MCP or supervisor, and historical operation counts are not used as a live census. P01.S02 supplies the current census and P05 proves actual reachability.

### phase-one-authority-intersection | low | Contract invariants verified; effect enforcement remains with later owners

The policy refuses cross-profile requests, stale authority and privilege expansion, and requires scoped output disclosure and exact period coverage. Review corrections added persistent profile-lock generation checking on grants, operation-specific period restrictions and observation consent coverage. The pure result is intentionally not a credential, apply/reject response bearer or commit capability. Later lifecycle/operation integration must fetch authoritative facts and repeat evaluation under the accepted denial fence at each relevant boundary.

### phase-one-exposure-coverage | medium | Existing entry-point bypasses and incomplete enrollment remain migration work

The new Reference census establishes actual application definitions, operator actions, declarations and dispatch paths. Its observed bypasses and missing joins cannot be credited as authentication or parity acceptance by passing catalogue tests. Carry the recorded inventory through the already planned operation-administration enrollment and private-entrypoint convergence Steps, then prove installed reachability in Phase 5. No placeholder administration executor was introduced.

### phase-one-verification-environment | low | Two discovery checks remain environment-limited

Semantic discovery could not use the mismatched shared service; focused defining-source reads supplied the grounding. Full installed surface reconciliation requires the absent published authority descriptor. These limits do not block pure contract acceptance, but later installed/runtime acceptance must rerun the applicable checks against a configured published authority and matching discovery service. The exact evidence and census limits live in the Reference and ledger.

### phase-one-vault-baseline | low | Global vault findings remain outside this change

The current complete scan reports 26 errors, 517 warnings and six informational findings, with no diagnostic referring to this feature. This differs from the historical S01 warning total in the already dirty workspace. Preserve that distinction; do not claim the complete vault is clean or repair unrelated records under this assignment.

### phase-one-authorized-stop | low | P01.S02 and the Phase 1 review close this assignment

The explicit current assignment supersedes the pending-authorization wording described in the historical execution-scope finding. S02 is checked through the owning progress tool; P02.S03 remains open. The next session starts with protected grant/control persistence and custody ports, using these public contracts. No commit was requested or created.

### originating-login-follow-up | low | Typed provenance resolves the ambiguous OS availability input

The former booleans could not distinguish origin-dependent sessions from independent API authority. The authorized amendment and typed replacement now express the reviewed distinction, with negative cases for unknown eligibility, different owner, original-login loss and private-work fencing. Permanent dependent-session invalidation and fresh native observations remain the lifecycle owner's obligation. No native event adapter or platform containment acceptance was inferred from policy tests.

### custody-publication-review | low | Recovery follows the protected witness and preserves denial on ambiguity

Review traced every filesystem and native-store publication boundary, including a write that commits before reporting failure. Fault injection, profile sentinel proof and independent wrap-key tests exercise the actual crypto/filesystem paths. Missing anchors, stale pointers, mismatched bindings, malformed records and cleanup failure refuse. The new application port avoids forcing future enrollment operations to import adapter-owned write contracts. Workflow consent/delivery, admission and ordered revocation remain with S04-S06; the custody primitive does not manufacture that authority.

### native-custody-readiness | medium | Native success remains unproven and unsupported platforms refuse

The separately selected Windows native test failed before its first automation credential write because the current process's credential logon session is unavailable; the measured Win32 error is 1312. Do not count this failure, a deselection, or fault-injection success as a native round trip. macOS/Linux concrete non-prompting adapters remain absent and composition refuses them. The S03 store/port acceptance does not close platform support: the affected platform Steps explicitly retain adapter composition, native replacement/deletion and installed lifecycle acceptance. Enrollment must surface unavailable/unsupported custody until the relevant backend is proven.

### concurrent-tree-import-gate | low | Complete import health could not finish against the changing shared tree

The full gate kept all 15 graph contracts and found zero hard subordinate violations, but exited 7 because unrelated new runtime modules were missing from the shared load inventory and the source snapshot changed during the run. Only the five generator-verified targets owned by this assignment were merged. A subsequent architecture-only check passes all 15 contracts; owned modules import successfully. This is not a passing complete import/loadability gate. The exact missing unowned targets and commands are recorded in the Reference/ledger.

### scoped-custody-closeout | low | Enrollment and platform acceptance remain separate open work

S02 was reopened and reclosed with focused follow-up evidence. S03 delivers the protected control store, cryptographic primitives and OS-secret-store ports; native platform success and installed runtime access are not claimed. The next authorized implementation boundary is S04 only in a later assignment. No administration executor, endpoint, commit or change to the separately owned MCP timeout files was introduced.

### custody-multigrant-recovery-regressions | low | Interrupted multi-grant updates and replayed state retain the protected authority

Additional S03 verification on 2026-09-26, under the operator's request to take independent work while implementation continues: `src/cadrumo/adapters/persistence/storage/custody/tests/test_automation_publication_recovery.py:75` adds twelve cases covering first publication and subsequent updates, failure before/after each of two wrapping-key writes and the control-anchor write, recovery of both credentials, exact retained native-key inventory, and retry after an uncommitted initial publication. The tests use real synthetic encrypted profiles, filesystem records, AEAD and sentinel validation with an explicitly injected in-memory native port. They are not native keychain tests.

`src/cadrumo/adapters/persistence/storage/custody/tests/test_automation_publication_recovery.py:137` replays an actually emitted pending publication after a later grant removal and verifies refusal without changing protected state. The case at line 164 verifies stale-revision and decreasing-lock-generation writers cannot replace the authoritative store or restore key access. No production implementation or another test file was changed for this follow-up.

Result: PASS for the fourteen added regression cases. The combined owning run passed 45 tests, with one native credential-store test deliberately deselected, exit 0. Ruff, formatting, ty, pyrefly and basedpyright passed for the added file. No defect was reproduced in these covered protocol paths. S04 enrollment changes began modifying the shared custody module during verification; this is additional recovery coverage, not a final review or acceptance of those in-flight changes. Existing native credential-store and platform acceptance gaps remain open. Exact commands are recorded against S03 in the execution ledger.

### enrollment-publication-and-possession | low | Current authority is rechecked after protected delivery

Reviewed request creation, exact review digest and password proof, inactive candidate publication, protected client handoff, client possession, activation, rotation, renewal/scope generation changes, decline and inventory through the existing supervisor. Tests exercise writes failing before/after commitment, replacement of an absent candidate, recovery of a delivered candidate, displaced concurrent candidates, unchanged predecessor validity on failure, sixty-second overlap, fresh binding/fence/scope checks after delivery, secret-channel zeroization and non-disclosure. A client reference survives connection replacement while its durable custody/client/destination binding remains mandatory. Separate response capabilities remain untouched. Result: PASS for these implemented protocol paths.

### enrollment-review-corrections | medium | Integration placement, error ownership and decline retry corrected

Resolved before closing S04: real-profile tests and their outer-adapter fixture moved from the application layer into custody's owning tests; pure consent tests remain inward. The earlier bare AutomationCustodyError now derives from the canonical registered root, retaining its enum as reason while code belongs to the central registry. All known callers were updated without a compatibility alias. Repeated decline now returns the durable receipt without a new publication. Renewal/scope contracts exclude key expiry, preventing a review operand from suggesting an unimplemented key extension. The final focused suite covers these corrections; no finding remains open in this entry.

### enrollment-runtime-and-native-evidence | low | Registered executors do not yet establish installed autonomous access

All seven new definitions have real service-backed executors. The default production graph refuses them without an explicit trusted runtime authority/recipient factory. Public registrations remain request-only; private inventory uses the encrypted result owner and authority-checked service. CLI/TUI/MCP enrollment journeys and runtime delivery transport have not been wired. Protocol tests use native-store and lifecycle/transport doubles. The Windows native test again refused at its first unique test-owned read before a credential write; macOS/Linux adapters and positive native replacement/deletion/delivery remain unproven. P03 platform and P04/P05 integration obligations stay open, as does Phase 2.

### enrollment-shared-tree-checks | low | Remaining failures belong to concurrent source and existing vault baseline

The final core-error failure names only cadrumo.application.runtime.contracts.RuntimeRefusalError(RuntimeError), outside this assignment's ownership. The final import gate exits 7: all 15 graph contracts are kept and hard findings are zero, but thirteen unrelated runtime targets were absent from the shared load inventory and the governed source changed during the run. Only four compiler-verified owned targets were merged; no unowned target was added or removed. Owned automation modules import successfully. The full vault remains at 26 errors, 517 warnings and 6 informational findings, none naming this feature. No unrelated runtime, MCP timeout, tooling or governance source was repaired.

### phase-two-human-unlock | medium | Optional automation custody no longer blocks password unlock

Resolved during cohesive review: global resume formerly required the optional native store even when no grant was selected. The current local human fence can be unlocked after fresh exact-request password proof while durable automation denial remains intact. Protected grant resume still requires native cleanup and explicit fresh-password selection. A separate correction preserves already suspended grants across repeated global locks. The real encrypted-profile regressions exercise both paths; scope and expiry remain unchanged.

### phase-two-denial-and-recovery | low | Acknowledged denial survives cleanup failure and restore

The shared lifecycle guard serializes admission/material release against denial. Live descendants are removed before durable denial acknowledgement, and physical retirement failures remain pending. Custody tests inject native failure before/after anchor commitment and during deletion, reopen through fresh store instances, and exercise password rotation, recovery and deletion with unavailable native facilities. A pre-delete portable backup restored into the same root does not resurrect the old key. Current-session locking leaves independent root-key admission available.

### phase-two-installed-boundary | medium | Runtime enforcement and native acceptance remain open

ProfileSessionAuthority and AutomationLifecycleService consume explicit trusted host observations; their test host/native backends are declared doubles. Existing private entrypoints still need S08/S09 convergence and CLI/TUI/MCP projection wiring. S10/S11/S20 must prove native facilities, login events, abrupt-death containment and installed parity on every platform. This Phase 2 PASS is not an unattended-readiness claim.

### Runtime execution checkpoint, 2026-09-27

P03 remains in progress. The installed native transport now dispatches exact-profile authentication/status/refresh/lock to the existing session authority and immutable profile workers. Real encrypted-profile/native-pipe/installed-worker integration passes with explicit OS-login and native-store fault ports. The actual runner is a Windows network logon in session 0; positive interactive-login, Credential Manager and full platform lifecycle acceptance remain unproven. Detailed current code ownership is recorded in the Reference and actual commands in the execution ledger.

The authorization prerequisites now enter the existing supervisor at submit, actual executor entry, checkpoint re-entry and irreversible sections. Integrated review caught and fixed a potential authority inheritance path between concurrent async tasks: effect sections now serialize by task, with reentrancy only for nesting in the same task. Dedicated tests prove denial before protected execution and preserve the original journal when checkpoint admission refuses; the broader durable supervisor regression passed. The profile denial guard remains synchronous/thread-affine and is not held across event-loop tasks.

Open acceptance boundaries: cross-process authority/effect handshake, owner-resolved operation periods/readiness, private result release, CLI/TUI census convergence, full parity and replacement MCP wiring. Until those land, existing private entrypoint bypasses persist and the new runtime must not expose arbitrary private dispatch. These are unfinished approved Steps, not a Phase-3 PASS or a platform-completion claim.

### worker-operation-boundaries | medium | Native execution now exercises canonical encrypted effects; public convergence is unfinished

Checkpoint review traced real installed worker submission through the canonical registry and supervisor, native runtime permits and the existing profile fact writer. Tests prove successful encrypted mutation, final commit refusal without that fact changing, exact-session invocation ownership, and independent custody control while submission is awaiting authority. Profile mutation threads settle before the effect permit releases. Worker service cleanup now precedes key custody release. Registered owner resolution refuses unsupported definitions rather than guessing period/readiness facts. The broad runtime integration lane passed 61 cases; 25 platform skips and 19 deselected unit cases are not additional passing evidence.

Public private-output guards, durable authorization provenance/idempotent reattachment, the private CLI/TUI census and full host drain remain unfinished. Current internal submission refuses durable idempotency rather than adopting an invocation by its ID. The authorization owner in the native effect tests remains an explicit fault port. Actual native interactive-login/credential-store and non-Windows platform acceptance are separate open obligations. S08/S09 and Phase 3 remain open.

The complete import gate kept all 15 architectural contracts and loaded all 2,947 modules, but found an earlier installation import through a re-export. That import now names filesystem_primitives directly; the complete rerun is in progress. No unrelated code or user state was altered.


### S09 continuation checkpoint: retry and stored invocation (2026-09-27)

Canonical composed-service retries previously attempted a second response-capability reservation. Corrected so replay returns its existing receipt without issuing a capability, including on a replacement host. Native worker tests exercise real encrypted mutation, denied commit, fresh-session retry, changed-operand refusal, replacement-worker observation and foreign-profile refusal. The authorization owner in those native mutation tests is an explicit fault port; this does not establish the live grant-to-effect integration or positive native login eligibility.

Verification: 16 composition/native integration cases passed in `20260927T111329.950895Z-pytest-43324-2aec7cfb`; 13 continuation/authority/native cases passed in `20260927T111659.790913Z-pytest-48152-5b1a2cd4`. Fresh continuation excludes another active owner and live local work, refuses denied entry, and lets canonical lease recovery preserve interrupted/uncertain outcomes. S08/S09 remain open and Phase 3 is not accepted. Current Windows runner and other-platform acceptance limits are unchanged.


### S09 public transport and effect/output integration (2026-09-27)

Three native connection cases passed in `20260927T113236.987952Z-pytest-39148-f1b58ba9`. The two new cases use real enrollment/control crypto, API verification/unwrap, ProfileSessionAuthority, installed workers, canonical supervision and encrypted profile writes. Only native login and optional OS secret-store facilities are explicit fault ports. They prove fresh root-key admission after current-session lock, idempotent reattachment, continuation, separate observation consent, durable grant denial and an independent password read of the committed profile fact. The consented case holds a bounded barrier immediately before the real public native projection write: the profile guard remains owned, concurrent human selected-session lock waits, and subsequent agent output is refused. This closes the previously separate grant-to-effect integration gap for the enrolled profile mutation; it does not validate tax/filing or all domain definitions.

Final framing review found idle peers shared the five-second incomplete-frame deadline. The server now polls native readiness while idle; incomplete frames remain bounded and stop wakes idle connections. Broader runtime/regression and import gates are running for this correction; no pass is inferred before completion.

Owned S09 files pass Ruff, ty, pyrefly and basedpyright with explicit Windows targeting. Broader ad hoc Windows-target directory checks surfaced unresolved existing platform typing (41 pyrefly diagnostics; 70 basedpyright errors and one warning) in POSIX/Linux/native process/manager modules. The POSIX readiness module passes its native Linux-target pyrefly/basedpyright checks. Full platform typing remains an S10/S11/S20 obligation; these broader results are not a successful global type gate. S08/S09 and Phase 3 remain open.


## Recommendations

Continue the authorized plan at P03.S07. Host the completed custody/admission services behind authenticated local transport and immutable profile workers, retaining the existing operation supervisor, journals and response authority. Resolve the phase-two-installed-boundary finding through S08-S11 and P04/P05, using fresh native observations and real installed acceptance. Preserve the current entrypoint census and its migration obligations.

Native credential-store success is still required on eligible Windows, macOS and Linux hosts. Feature checks remain distinct from the full vault's unrelated baseline. The latest complete import gate is clean; older concurrent-tree failures above remain historical evidence. No subagent, commit, live taxpayer access or filing was used.

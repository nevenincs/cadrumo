---
tags:
  - '#audit'
  - '#startup-service-repair'
date: '2026-10-14'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:59b94fbf7b32bea8724f53bfe35933ad887f33827f69450331136a8f93b0cecb'
related:
  - "[[2026-10-14-startup-service-repair-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace startup-service-repair with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

# `startup-service-repair` audit: startup diagnosis and supervision

## Scope

Integrated review of the uncommitted startup-service-repair implementation against the accepted canonical environment and desktop shell decisions. Reviewed diagnostic forwarding and containment, worker exchange fencing, KDF cleanup, shared status observations, retry supervision, and user retry integration. Other concurrent work is outside this repair except where it interacts with these workflows.

<!-- What was audited and why -->

## Findings

### retry-budget | medium | Observation failures must preserve exhausted retries

Initial review found that transient runtime/status failures reset the retry budget in `native/desktop/src-tauri/src/agent/supervisor.rs`. This could restart endless automatic launches for the same broken service. Corrected to preserve the budget and original refusal through transient failures; only verified sign-out, profile changes, and explicit retry reset it. A regression covers exhaustion followed by read failure and runtime unavailability. Updated native verification remains pending.

### live-timeouts | low | Historical timeout attribution remains incomplete

The first 10-second worker exchange and the 30.783-second KDF cleanup cannot be assigned a precise internal cause from the historical logs. Request/action fields and cleanup process/pipe/directory spans now survive diagnostic filtering. Worker cascades and unbounded queue waits are repaired, but original live causes require packaged reproduction.

### verification | low | Package acceptance remains pending

Review verdict PENDING. Reused passing focused Python diagnostics, lifecycle, transport and KDF checks; 52 native sign-in tests; nine earlier supervisor tests; frontend check; and browser refusal/retry scenario. Registry gate and diagnostic privacy regressions pass. Root owns remaining shared checks, refreshed supervisor verification, and rebuilt package acceptance. No critical or high code findings identified.

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### {topic} | {level} | {summary}

     followed by a paragraph carrying the detail. {topic} is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### final-native-review | low | Native corrections verified

Follow-up review found no defects in the preserved retry budget or nonzero helper outcome. All 10 supervisor tests pass, including pending-read responsiveness and exhaustion across observation failures. The real nonzero-exit regression passes and retains the typed refusal envelope. Frontend checks pass after the contract change. Three initial supervisor failures were obsolete expectations for the intentional `agent_root_unmarked` mapping; corrected fixtures pass without timeout changes.

### repository-gate | low | Unrelated registry collection error prevents full-suite success

The configured `just test-gate` found a collection failure at `dev/registry/tests/test_record_design_source_selection.py:111`: one expected exercise unpacked multiple values. The run was stopped after establishing this failure to release resources for package acceptance. It is not passing evidence. `just check-registry-gate` passes. Package and remaining code-quality verification are still pending.

### service-start-reply | medium | Asynchronous startup acknowledgement was rejected as unreadable

Direct inspection found `AgentService.admin("start")` returns `kind=starting` while `native/desktop/src-tauri/src/agent/supervisor.rs:262` expected an immediate lifecycle `event`. Corrected the caller to accept the administration acknowledgement and leave readiness/refusal to the existing service event stream. The rebuilt package's manual admin start acknowledged in 0.001 seconds and subsequently emitted the agent refusal, independently of a GUI.

### startup-refusal-cause | medium | Typed startup causes were lost at the service boundary

`src/cadrumo_agent_service/main.py` and `service.py` reduced preflight exceptions to generic failure and discarded the inner agent refusal detail. Corrected both paths to use the existing launcher categories and log the agent's validated refusal code without serializing exception payloads. Six focused regression cases pass. In the rebuilt package, `build/acceptance/agent-manual-fecjpz6t/storage/logs/cadrumo.log:31` now states `hosted_lane_unproven`, including on asynchronous retry at line 33. Runtime readiness, password-authenticated CLI holder, exact service admission, twelve-provider catalog/status, protected credential set/remove/reset with CAS, and contained close all completed without a GUI.

### cli-auth-homes | medium | Ordinary CLI sign-in is not hosted provider sign-in

Two user-requested Luna max investigations traced the service and agent separately. A packaged-interpreter composer probe confirms custom `CODEX_HOME` and `CADRUMO_AGENT_CODEX_HOME` are absent, while OS home variables remain. The agent seats hosted Codex at `providers/codex`, then creates a fresh per-turn home and copies only that provider home's `auth.json`; a synthetic production-helper probe confirmed present/absent source behavior. Hosted Claude uses a persistent per-provider `CLAUDE_CONFIG_DIR`, with no automatic import from the user's home. The real Codex CLI reports login status exit 0 in the selected account, but exit 1 with no auth file in the manual hosted provider home. Provider settings' sign-in mode is not credential provisioning. No credentials were imported as a workaround. Hosted authentication provisioning and recorded hosted-package proof remain separate requirements; no working hosted conversation is claimed.

### external-cli-resolution | medium | Native gateway and worker discarded the runner's CLI search directories

The real one-time package proof reached a gateway but failed before a turn: `build/acceptance/agent-live-jsygxbgn/exchange/runner-console.log` records `binary_version_unavailable` and no selectable provider. The runner resolved Codex on the operator PATH, but the native host recomposed PATH and neither agent profile admitted the already-declared external-directory variable. The service composer also dropped that setting despite its own native profile admitting it. S05 forwards only that public package setting, admits it to both gateway and worker, and recognizes declared pass-through names in conformance. No credential/home forwarding or PATH-policy bypass is added. Native `platform.resolver` passes the new two-stage regression; environment/composer conformance checks pass. Refreshed packaged live proof remains pending.

### repository-gates-2026-10-15 | low | Shared gates fail outside the changed service paths

`just check-registry-gate` passes. The change-scoped `just test-gate .tmp/agent-service-changed-paths.txt` uses the fixed contract set because the service composition files have no enclosing root tests directory; that population passed before CI-contract verification failed with six failures and 1131 passing tests. Five overview cases report runtime unavailable and a fixture-root coverage case retains a temporary directory outside its isolated root. `just check-code` fails project-wide checks, including unconsumed exports and an operation-contract manifest drift; style, format, types, dependency declarations, secure-store and persistence write paths, and docstring references pass. Changed-file Ruff, Rust formatting, focused ty and all 24 Import Linter contracts pass. These aggregate failures are not attributed to the agent repair and are not passing completion evidence.

### luna-max-integrated-review | low | Repairs pass code review while package proof remains pending

Independent Luna max review found no high or medium code defects in S01, S02, S03 or S05. Refusal diagnostics remain bounded, the CLI holder preserves person-session authority, and the public external-directory value is validated by each native launch. Manual retry can retain the old visible refusal until the next ready/refused event. Publishing Starting after its asynchronous acknowledgement could overwrite a result that arrived first; this minor progress limitation is retained without adding a new lifecycle protocol. Review verdict PENDING until refreshed packaged live-provider/tool-access evidence and the unresolved shared checks are accounted for. The user subsequently confirmed separate sign-in in each profile-owned provider CLI home, rather than importing an external account.

## Recommendations

### profile-cli-sign-in-review | low | Operator preparation passes review; interactive package proof remains pending

The service now prepares a foreground login through the separately packaged agent, using the profile-owned hosted root and public external binary directories. The agent owns the provider-specific native login command and home override. Its offline auth-capability response comes from the same handler mapping as login dispatch. An independent corrective review confirmed unsupported providers are refused before auth-mode mutation or root creation; no remaining high-confidence credential-boundary defect was identified. The current service and holder suite passes 289 tests, and runtime diagnostic/cleanup coverage passes 110 tests. A separate admin deadline mismatch remains: catalog subprocesses permit 30 seconds while the frame deadline is five seconds and checked before synchronous dispatch. This broader timeout contract needs follow-up. The user selected Claude; the final rebuilt package, interactive isolated login, runtime shutdown and model/tool proof remain pending. An empty Claude config directory reports auth status exit 1 without capturing provider output or reading credentials.

### buffered-stdin-shutdown | medium | Daemon readers could abort the Python process during shutdown

Direct manual package evidence found fatal buffered-stdin finalization in both the service and held-session helper while the parent retained the input pipe. Both now read the bounded protocol through raw file-descriptor operations. Subprocess regressions exercise authority loss with the parent input pipe left open. Fresh package verification must confirm clean exits; unit success alone does not establish that the separate historical retirement/containment timeout is fixed.

The final immutable package now passes the direct refusal-state authority-loss case at `agent-authority-k62iosvi`: a real held CLI person admits the real service, then closes the person session through its public control command while the parent keeps both input pipes open. Holder and service both exit 0; holder, service and runtime stderr remain empty. The outer retained-handle job owner observes zero members after a bounded two-second natural reap grace and exits 0 without forced cleanup. An earlier attempt queried membership immediately after coordinator exit and forced one remaining member; that is not clean-tree evidence. The fresh passing case demonstrates the buffered-reader repair in this state. It does not establish active-model worker retirement or resolve the separate historical containment timeout.

### claude-runtime-assets | medium | Packaged Claude adapter dependencies repaired; live proof pending

Luna's read-only inspection of the verified package copy found neither Node nor the Claude ACP adapter expected by the default agent backend. The agent's accepted shipping/versioning decision requires those assets in the agent install; only the provider CLI is user-supplied. The agent wheel does not contain the top-level npm runtime closure. Its development npm tree also includes an SDK-supplied Claude executable that must be excluded from delivery, so copying that tree wholesale is unsuitable. This is a packaged dependency gap. A successful isolated login will not establish Claude model execution. Preserve the hosted proof gate and package the pinned runtime closure through CMake before claiming that behavior.

The repaired Release payload now contains pinned Node 26.10.0 and Claude ACP 0.85.1 with an exact runtime receipt, package manifest coverage and no SDK platform Claude CLI. The actual shipped interpreter's smoke check runs both shipped executables and passes; the packaged environment probe passes stores lifecycle, worker binding and credential/path sanitation. The verified immutable copy has manifest digest `fd8f2dc987159da9516245819ff661bb95e4449b94fd8fd56c280d7cb38b3541` and 38171 files. Offline auth-provider enumeration passes, and login without a hosted root refuses with native exit 125. None of these checks establishes a model or relay turn.

The first live attempt against this copy reached runtime readiness, held-person admission and exchange handoff, then refused before model startup because the external proof runner included a stale dotenv-declared program outside the verified package. Its Windows job owner reaped all remaining owned processes. The runner's unconditional fresh-profile replacement also conflicts with the existing person driver's handed-off profile and scenario; investigation is pending. A further independent review establishes a hosted-certification cycle: the accepted external capability-proofs decision requires a completed hosted-layout turn while production hosted startup rejects every lane lacking that certification. The non-host tool bootstrap cannot truthfully supply a hosted-turn claim. No proof declaration or admission bypass has been added.

The final aggregate code gate passes style, format, data format, types, dependency declarations, secure/persistence write paths, docstring references and operation manifest. It fails the broader import/reachability/symbol/export gates; the export scan observed a concurrently edited custody module with an indentation error. These aggregate failures remain disclosed; focused agent/service results do not make the full gate green.

The user explicitly approved the scoped hosted-startup amendment on 2026-10-15. The agent owner accepted and reconciled `Y:/code/cadrumo-agent-worktrees/main/.vault/adr/2026-10-15-cadrumo-integration-hosted-certification-bootstrap-adr.md`. Production startup and per-lane selection retain ordinary current-runtime turn evidence, credentials and other admission controls. Hosted-package certification is a separate `unknown`, `pending` or `proven` catalog/frozen-selection disclosure; hosted tool-capability proofs still require package-backed evidence. No hosted-proof record has been fabricated. The agent's 188 focused tests and scoped Ruff/format/type checks pass, and integrated source review finds no must-fix defect. The Cadrumo service projects only an authenticated live catalog observation into an immutable five-second snapshot; status performs no extra HTTP request and returns unknown/empty for unobserved, expired or stale generations. All 285 service tests pass after this latency correction. The Release payload rebuild is running; these source results do not establish a successful hosted turn.

The handoff compatibility repair preserves the person's exact disposable root, profile and scenario, with distinct nonsecret provenance from the actual held session. Standalone runs retain runner-created profiles. Root review caught and corrected source-client imports of unavailable Cadrumo dependencies: marker verification now uses the manifest-inventoried packaged interpreter in an isolated, credential-free bounded process. Unit boundary checks and all 17 person-driver tests pass; the actual packaged marker/relay run remains pending.

The actual package service admitted a held CLI person and completed catalog, status and Claude sign-in preparation. Claude reported the new profile-owned home signed out. A separate Debug bundle build subsequently quiesced that held session before interactive login completed. The generated login script was invalidated, and the user observed its stale-session guard. No successful sign-in is claimed. A fresh login must be prepared against the rebuilt package after native build quiescence ends; then verify the same home signs in and a second fresh home remains signed out before attempting the hosted model turn.

Fresh manual package evidence at `build/acceptance/agent-manual-ob5uo5er` passes runtime readiness, person-held service admission, provider administration and asynchronous start, but fails runtime shutdown: `ProfileWorkerRetireRequest` exhausts its 10-second wire deadline, then native containment cannot acquire its guard within two seconds. The coordinator's exit 0 is insufficient; runtime stderr establishes failed cleanup. Luna traced job membership enumeration under the native guard as a possible long holder, but the actual holder and the worker-side retirement delay are unproven. Do not change authorization semantics or claim containment repaired from that hypothesis.

The live package run `build/acceptance/agent-live-l2a5ehrv` verifies the external-directory repair through actual provider selection and packaged worker dispatch. It fails before a model response because Codex rejects its isolated tool runtime under a repository; the relay also exceeds its start/list deadline. The manual driver now accepts an explicit `--scratch-parent` while preserving its existing default. Development tooling redirects standard temp into the repository, so the initial temp-only attempt was ineffective and cancelled with all owned processes reaped. The explicit external-root retry at `[redacted]/AppData/Local/Temp/cadrumo-agent-acceptance/agent-live-jzgehw20` reaches runtime readiness but fails synthetic profile editing (`exit 1`, empty envelope). No successful provider turn is established. Independent incremental review finds no destructive path issue: cleanup owns only the unique scratch child. Its verdict remains PENDING on live proof and runtime cleanup evidence.

The owner confirmed on 2026-10-15 that provider CLI authentication must be performed separately in each profile-owned CLI home. Preserve provider-owned credentials there; do not import the ordinary user's account. The declared agent catalog currently supplies authentication kind and CLI program metadata, but no host-callable login operation or login/probe command descriptors. A saved `provider_sign_in` choice therefore cannot establish authentication. Complete the agent-owned authentication contract and its authenticated service integration before presenting provider sign-in as functional. Keep provider-specific login commands out of a Cadrumo-maintained provider list.

The refreshed Release payload built successfully and its direct environment launch probe passes stores setup, standalone worker launch and sanitation. Its hosted gateway still explicitly refuses `hosted_lane_unproven`. The subsequent live proof at `build/acceptance/agent-live-5hu58oe3` stopped before agent launch because runtime readiness was not received within the existing deadline; it is failed evidence, not a model turn. Installed service source text matches the repair (wheel newline normalization explains differing byte hashes).

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->

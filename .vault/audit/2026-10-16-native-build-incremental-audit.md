---
tags:
  - '#audit'
  - '#native-build-incremental'
date: '2026-10-16'
modified: '2026-10-16'
body_schema: 'body-v2'
body_hash: 'sha256:ce81b2f91561806862d7a7b6aa3bfddf70ce6f7f78883cfbbf03e8d64b7deefb'
related:
  - "[[2026-10-16-native-build-incremental-plan]]"
---
# `native-build-incremental` audit: incremental packaging and single-MSI integration

## Scope

Rolling integrated review against the approved native-build-incremental plan and accepted decision. S01-S04 are committed and pushed at 01b2e2ff76, ed5a0b44b9, 114d0a3a04 and 0e08b66e4b respectively. The installer worker owns S05 staging integration, independently reviewed by the assembly worker; the Python worker owns the new behavioral currency tests. Parent owns native build integration and shared verification. Unrelated concurrent source edits remain outside the commit scope.

## Findings

### compiler-version | medium | Compatible developer interpreter initially conflicted with exact bytecode gates

Resolved: both bytecode gates admit the pinned runtime major/minor and a developer patch at least as new, preserving actual compiler identity in cache currency. A real developer CPython3.13.15 produced checked-hash bytecode executed successfully by the existing SDK CPython3.13.11. The packaged runtime/SDK pins are unchanged.

### assembly-ownership | medium | Missing helper inputs and temporary cleanup ownership could leave stale outputs

Resolved: the CMake assembly input list includes assembly_transaction, and temporary work has a BuildPaths/cleanup owner. app-payload owns its assembly receipt and clean paths; bundle/app-distro cleanup delegates to it. The unshipped test-consumer application rlib is no longer an explicit app-payload prerequisite; native verification retains it.

### authority-reuse | medium | Relocated authority files were copied again on native-only changes

Resolved: verified reuse maps the exact layout-declared authority subtree to its final package location. Windows/POSIX regression tests confirm prior immutable bytes are reused without sharing mutable source inputs. The persistent product snapshot publishes a coherently captured authority pair before pruning obsolete snapshot-owned generations, retaining the authoring authority untouched.

### obsolete-base-members | medium | Changed obsolete base members could remain orphaned

Resolved: base closure synchronization refuses an obsolete member that no longer matches its prior owner's bytes, and preserves its receipt on refusal. Unchanged owned members retain timestamps; separately owned application files survive normal base refresh.

### deleted-wheel-members | high | New-wheel hashes alone failed to detect deleted installed members

Resolved: installed wheel currency now checks installed RECORD ownership membership against the new wheel as well as member bytes. Only exact installer metadata additions and wrappers declared by the new wheel are admitted. Three real uv tests prove deletion-only module/corpus edits trigger reinstall and remove old members, while legitimate installer additions remain reusable.

### snapshot-links | high | Persistent snapshot links could redirect changed writes outside ownership

Resolved: retained snapshot roots, ancestors and members reject symlinks/junctions before mutation; build_product preserves lexical output ownership for that admission. Two regressions prove refusal occurs before changing an earlier ordinary member.

### build-and-native-acceptance | medium | Final integration evidence remains pending

PENDING final integration: focused producer, rollback, authority, bytecode, native platform, Node and content-currency checks pass, along with changed-file style/type checks. Debug and Release app-payload builds pass, and the first full Release MSI/kit compiled exactly once. Current-source full packages and unchanged-repeat verification follow the S05 preparation-currency corrections. Independent installer source review and rebuilt-adapter tests pass; genuine disposable installed lifecycle acceptance is not established by source/unit/compiler evidence.

### public-candidate-acl | medium | Private temporary-directory ACL could survive application publication

Resolved: assembly candidates use collision-resistant UUID names and normal mkdir with mode0755, preserving inherited stage access rules instead of Python3.13 Windows mkdtemp's protected private DACL. The final13 transaction tests pass after this change, and a real published test directory reports AreAccessRulesProtected=False. The installer reviewer routed the equivalent installation candidate concern to its owner.

### services-kit-currency | medium | Uncached delivery repeated payload authoring checks

Resolved in S05 integration: services-kit delivery now uses the existing action cache, binding admitted installation, authoring and compilation receipts, actual MSI, compiler, runner/adapter, helper and payload-manifest identities. The outer enrolled source build owns the exact services output, cache marker/lock and cleanup; distribution output containment remains intact. Independent review caught and resolved the initial incorrect distribution-root cache ownership before the new cache was used for production delivery. Real nested-topology checks pass unchanged reuse, corrupted-kit repair without MSI recompilation, original-payload tamper refusal, and both explicit and built-in cleanup containment. Both guarded CLI admission checks pass. Revised source review passes with no remaining confirmed findings.

### source-drift-during-verification | informational | A later traversal incorporated genuine source edits

The first full Release MSI/kit was valid for its admitted payload. A later cache-seeding traversal encountered five changed source files under cadrumo/entrypoints/cli/config: _google_command_specs.py, _repair_command_specs.py, archive_reconcile.py, google.py and profile_command_specs.py. The main wheel changed d6deb7dd... to e020494c...; companion wheels stayed identical. These concurrent edits were preserved. This traversal is a new payload build, not an unchanged repeat; one MSI compilation for it is expected. Stable-repeat and final artifact evidence must follow that generation. The earlier live-model proof evidence remains explicitly associated with the first Release generation.

## Recommendations

### Windows staging input isolation and existing-stage verification

The changed Release staging producer completed successfully, but its outer cache refused completion after an unrelated native/application/Cargo.toml test-target edit changed a Linux-only enrolled input. The current stage exactly matches the admitted Release payload manifest. The failed wrapper is not recorded as a successful build, and no MSI compilation occurred in that traversal. Windows/macOS input enrollment is being corrected to exclude Linux-only dependency evidence while Linux retains the fail-closed evidence guard. The external Cargo change also invalidates Linux's pinned dependency evidence; that evidence is not silently rewritten.

The extended staging review found a remaining full scratch copy in installation.prepare(existing-stage) used solely to compare receipts, and unconditional refresh publication even for an already matching admitted stage. S05 replaces both with preparation currency: one current-input projection independently derives expected files, manager bytes, controls, modes and metadata; full source/staged-payload and stage-membership validation admits reuse. Editable receipt self-consistency is insufficient. All 40 behavioral cases pass in two focused runs: the initial 36 cover forged controls/receipts, links, permissions, changed inputs and unchanged file identity/mtime preservation with copying and candidate publication forbidden; four additional cases cover receipt-only application identity/generation tampering. The independently approved prior-file digest removal retains the callback source hash, candidate validation and final old-stage admission. The Linux desktop Version field is preserved. Final independent integrated source review passes with no remaining confirmed findings. Eighteen staging/CMake cases pass, including race, rollback, kit reuse, tamper and cleanup checks; corrected overlay and installation compatibility checks pass 23 cases with two skips. The external Linux evidence refusal remains explicit.

The full versioned Windows MSI path no longer generates the unused Desktop.wxs and DesktopPatch.xml overlays. Its sole WiX authoring output is application.wxs; legacy desktop-only CPack retains the overlays it consumes. MSI post-compilation verification uses wix msi decompile without extraction, plus read-only native MSI table queries; no whole-CAB extraction or administrative installation is performed.

### Final configured output ownership

The configured build-path manifests for build/windows-x64 and build/distribution-windows-x64 contain no _deps member or output escaping their selected binary directory. Final application destinations remain stage/Debug/app and stage/Release/app. The following defaults are relative to each enrolled binary directory; declaration does not mean every project produces every directory.

| Owner | Default directory |
| --- | --- |
| Generated contracts and metadata | generated |
| Temporary build work | temporary |
| Embedded runtime and pinned wheels | inputs/runtime |
| Embedded Python SDK | inputs/python-sdk |
| Build tool payloads | inputs/build-tools |
| Agent wheel and Node runtime | inputs/agent |
| Product wheels and source snapshots | product |
| Native executables, libraries and symbols | bin, lib, symbols |
| Cargo outputs | cargo/native, cargo/desktop |
| Application and services-kit publication | stage |
| Distribution archives and MSI | packages |
| Test and verification work | testing, verification |
| Desktop frontend and generated sources | desktop/frontend, desktop/frontend-generated |
| Desktop cache and icons | desktop/vite-cache, desktop/icons |
| Desktop host snapshot | desktop/host |
| Desktop test work and results | desktop/testing, desktop/test-results |
| Existing documentation producers | user-docs/build, user-docs/work, user-docs/stage |
| Installation candidate and published tree | installation/work, installation/stage |
| Installation metadata and retained receipts | installation/metadata, installation/receipts |

The Windows distribution publishes one packages/msi/application.msi and one installation/metadata/wix/application.wxs. Each completed configuration publishes its matching sibling stage/<Config>/services kit. Machine uv configuration remains authoritative; the observed machine cache is C:/Users/hello/scoop/persist/uv/cache. The removed var/storage/development/cache/uv root remains absent. Legacy unused _deps contents are not claimed to have been deleted by this cache cleanup.

### Installer integration review, S04

Independent review traced single-artifact authoring, feature-qualified native ownership, scope authentication, transaction rollback and services-kit admission together. Resolved findings include machine registration incorrectly retaining user startup, duplicate admission/hash passes, overlapping metadata output ownership, protected candidate ACL inheritance, and a staged CLI regression referring to an unstaged verifier option. The regression now invokes the staged guarded MSI CLI; all 14 build-directory tests pass. New helper imports and schema 2 kit consumers are present in the staged change. No confirmed high source finding remains.

Evidence: Debug/Release rust_installer builds pass; installer.rust and application.rust CTest pass 2/2; focused Python checks pass 156 with 2 skips; the actual rebuilt Release adapter/runner admission fixture passes; real WiX fixtures compile once initially and zero times unchanged. Six desktop-path tests pass through the corrected CMake environment argument expansion. Genuine disposable Windows installation, upgrade, rollback and removal acceptance remains unrun. Full application-payload builds pass for Debug and Release; full-payload MSI publication and unchanged integration repeats remain S05 work.

### Compiled MSI contents and cross-platform verification

The first full Release artifact (SHA256 616919ec02c9163b67e3d7fb31396430d3fb89170f6d8fca33cccbd4f80811ff) is 384,070,456 bytes (366.278 MiB), with 38,317 File rows totaling 1,394,174,137 uncompressed bytes. Python packages/corpus account for 950.509 MiB; Node/ACP 140.555 MiB; hosts, native libraries, stdlib, authority and metadata 233.606 MiB; shared registration rows 4.917 MiB. File receipts identify 617 duplicate-content groups and 7.535 MiB of extra uncompressed row bytes, including mutually exclusive manager scope alternatives. A selected scope installs one stable manager plus the versioned manager. The installer DLL is one 874,496-byte Binary stream shared by scope actions, with no shipped-file hash match. Physical compressed-cabinet duplication overhead was not measured.

Read-only MSI tables confirm automatic md.neve.cadrumo.manager service registration as LocalSystem, user/machine component conditions, and independent VersionFiles/SharedRegistration features. Source confirms user LocalAppData versus machine ProgramFiles destinations, UAC elevation for machine scope, user-token workers, and protected scope-specific publication ACLs. These are compiled/source facts, not executed installation acceptance.

The independent read-only contents audit binds the first MSI's embedded CadrumoPackage manifest identity to exactly one retained content-addressed installation receipt, rather than using the newer current stage. It records 7,901,246 logical duplicate bytes and explicitly distinguishes the MSI's authenticated native installation marker overlay from the portable stage marker. Actual MSI tables have no Environment table or PATH/environment registry mutation; authored installer callbacks perform admission, authentication and preparation, without uv, a dependency resolver or environment creation. Detailed table, membership and scope evidence is in .tmp/native-build-incremental-msi-current-contents.json, anchored to the first artifact SHA above. No CAB extraction or host installation was performed.

The compact first-artifact size census in .tmp/native-build-incremental-msi-size-summary.json identifies cadrumo_data at 404.757 MiB (corpus AEAT193.532, manuals158.196, normatives51.983), cadrumo at 372.079 MiB (including corpus233.063 and manual_corpus_text48.160), and Node runtime at 100.015 MiB. Most other individual Python dependencies are substantially smaller: SQLAlchemy17.276, OpenAI13.972 and Anthropic10.947 MiB. The exact-hash duplicate count does not include representation overlap: 12,640 matched Python source/bytecode pairs total 106.532 MiB source plus 115.577 MiB bytecode. Node includes 10.467 MiB declarations, 5.679 MiB TypeScript sources, 5.608 MiB maps and 477 matched ESM/CJS relative-path pairs. These differing representations are not automatically removable; runtime/resource-consumer safety and compressed savings were not established by this census.

The user asked whether names follow product_platform_version. They currently do not: the Windows artifact is application.msi; Linux/macOS use product-version-target; root ZIP additionally includes build number and configuration. This verification records the naming gap without claiming uniform naming. All platforms share CMake orchestration and staged-payload/package adapters, but lifecycle parity is not implemented: Linux manager installation is explicitly gated in linux_packages.py. Only Windows builds were executed here.

### Packaged KDF and live-model acceptance, evidence

The rebuilt Release application passed real disposable-profile creation, login, readback and gateway startup. The original packaged KDF environment-attestation failure did not recur. Packaged agent identity matched all 427 checked source files. Both saved proofs passed against claude/api with claude-haiku-4-5-20251001: test_real_provider_reads_unprompted_nonce (99.73s) and test_real_queued_followup_recalls_tool_result (24.36s). Runner exit status was 0; profile, receipt, runtime, attendance and gateway cleanup verified, and the disposable owner directory is absent. No ordinary user profile or workstation installation was used.

The first launch safely refused saved Debug tool declarations against the selected Release package before provisioning. Process-only overrides selected the matching Release tools for the successful fresh run; no saved configuration was modified. Evidence is summarized in .tmp/native-build-incremental-packaged-model-results.json, with hashes and the originating runner-receipt.json/profile-lifecycle.json under Y:/code/cadrumo-agent-worktrees/main/.tmp/kdf-attestation-haiku-30186e84b22a4be6a35f379302bf7b2e.

### Disposable Windows runner availability, investigation

The user suggested Docker Desktop. Read-only probes found active desktop-linux, a Linux/WSL2 server, and install-settings.json with noWindowsContainers=true. The Windows engine is unavailable despite installed Windows Containers/Hyper-V features and a retained context. No Docker configuration, feature, image or host installation was changed. Windows-enabled Docker integration or a remote Windows daemon would be needed for headless MSI/SCM checks; interactive desktop acceptance additionally needs a full Windows VM. Docker documents the disabling installer flag at https://docs.docker.com/desktop/setup/install/windows-install/#installer-flags and Microsoft documents the GUI/RDP limitation at https://learn.microsoft.com/en-us/virtualization/windowscontainers/quick-start/lift-shift-to-containers .

Retain the corrected content/membership and ownership refusal tests. S04's actual compilation/no-op and native owner/admission regression evidence is complete. Append S05's final full-payload build/no-op/package verification evidence before declaring the plan complete. The platform-specific installed release acceptance gate remains explicit while the required disposable host is unavailable.

### Shared-worktree verification limits

The broad project gates are not claimed green. An earlier just check-code run failed in unrelated concurrently edited CLI/TUI, import, type and reachability code. An observed broad just test-gate run reached 1,135 passing tests with two failures and one error in overview, runtime cleanup and storage containment checks outside this change. Current focused Linux installation fixtures additionally encounter the external Cargo dependency-evidence mismatch described above. Those failures are preserved rather than hidden by weakening guards or editing another session's work. The scoped packaging, installer, bytecode and native test evidence is reported separately.

### Concurrent packaged-harness publication blocker

At 09:51 UTC the final Debug traversal was blocked by another live session running dev.package_runner test all, observed as PID50428 with parent53884. It continuously spawned packaged Debug runtime/profile processes after the build's initial quiescence. The initial attempt stopped when an exact owner did not exit; that process subsequently exited without manual intervention. The retry prepared its candidate but correctly refused atomic old-stage rename with WinError5 after 209.3 seconds. Prior application publication and the first full Release MSI remain intact; neither failed attempt ran distribution preparation or the MSI compiler. The Debug retry reused the Python wheel inventory; its observed product input capture matched all 9,350 previously captured input hashes. An external linux_desktop_runtime.py edit legitimately invalidated helper metadata and SDK producer receipts, without silently changing pinned evidence.

Independent inspection confirmed both the CMake native-process-quiesce prerequisite and assembly's quiesce call cover the whole source build rather than just the requested configuration. Release therefore could not safely proceed alongside this Debug harness either. No launcher was terminated manually, no publication guard was bypassed and no proposed quiescence callback/retry code was written. The user chose to let the tests finish. At 09:59:44 UTC the exact launcher and all observed descendant identities were absent; suite exit was not treated as evidence of passing tests. Packaging resumed, and current Debug application publication passed with a 228.0-second producer. Final native-installer, ZIP and unchanged ZIP runs for Debug followed by Release remain in progress. S05 stays open; final-generation live-model reruns and the S05 commit/push also remain pending. The earlier successful full Release MSI and Haiku proofs retain their explicitly recorded generation identities.

### First current Debug MSI and subsequent external agent generation

The full Debug native-installer target passed: installation preparation923.7s (producer831.4s), MSI629.3s and services kit358.3s. Exactly one actual WiX build invocation produced application.msi at 405,979,960 bytes; the schema2 kit contains that MSI, the 4,000,256-byte maintenance runner and kit.json. Snapshot counts were 38,312 app files, 38,316 distinct installation files, five wheel outputs and three kit files. Historical unowned compile scratch is not counted as additional current MSI products. The changed staging producer reported 10,491,840,155 read bytes and 164,306,749 written bytes across33 write operations, preserving full integrity boundaries without rewriting the full application payload.

The next root traversal was held for newly active interactive desktop/TUI processes using normal Cadrumo storage; no manual termination occurred. After they exited, the parent ran only the registered non-installing bundle.installer-bootstrap CTest. It correctly refused KitRefused before installation: another publisher had replaced the Debug app at12:40:30 local time, after successful kit publication. Agent wheel8ff873b7... changed to16c26019...; the new agent input receipt and app are coherent. The changed source is anthropic_chat_model.py, with its bytecode, RECORD and installer bookkeeping. Build/layout and maintenance runner still match. The kit and distribution stage agree on manifest6ac4f026..., while the newly published outer app has05336a52.... Independent review confirmed the native digest guard is correct and no source fix or weakened authentication is warranted. Evidence is build/windows-x64/testing/installer-observation/debug-external-agent-generation-drift.json. A new admitted agent generation requires a new MSI build; it is not an unchanged repeat or duplicate compilation. Final package/no-op evidence must follow a stable current generation.

Two clean publisher/owner sweeps and stable agent/app observations preceded the next Debug ZIP attempt. A concurrent client contracts.py edit then invalidated native generation and product inputs, while two new staged owners appeared. The normal build quiescer reported one forced identity, but its log contains insufficient image/parent/profile detail to classify that historical process; no manual shared-owner termination was performed. To avoid further interference, only the exact owned CMake49088 process tree was stopped at12:49:59 local time (exit15), before app replacement, distribution or another MSI compile. All six owned process identities were confirmed absent. Existing wheel outputs/receipts, current outer app and prior MSI/kit publications were preserved; no scratch or receipt repair was attempted. Evidence is build/windows-x64/testing/installer-observation/stopped-build-artifact-state.json. S05 remains open and uncommitted: both ZIPs, current-generation MSI/kit refreshes, true unchanged repeats and final-generation model reruns require coordinated stable source/output ownership. The first Release and first Debug full MSI successes are retained as generation-specific evidence, not final current-package acceptance.

---
tags:
  - '#audit'
  - '#native-build-confinement'
date: '2026-10-16'
modified: '2026-10-16'
body_schema: 'body-v2'
body_hash: 'sha256:b8d4b8bfdcfa223707762b7b5eb85a1dd75c21bd9b3138e15b0d939ba7a625bb'
related:
  - "[[2026-10-16-native-build-confinement-plan]]"
  - "[[2026-10-16-native-build-confinement-writer-census-reference]]"
---

# `native-build-confinement` audit: `native writer boundaries`

## Scope

Integrated working-tree review of S01 and S02, under the accepted interpreter-foundation and canonical environment decisions. The user authorized removal of custom uv management and confinement of native build writes. Three gpt-6-luna agents at max reasoning independently reviewed uv, Python writers and CMake; the parent inspected integration paths and generator CLI admission. Concurrent incrementality and single-MSI changes belong to another session and were preserved. No immutable Git comparison or bundle rebuild is claimed.

## Findings

### custom-uv-management | high | Repository-managed uv cache and builder environment were unnecessary

Corrected during execution: tool-root exports, UV storage declarations and private builder synchronization were removed. Configure selects the installed uv and existing interpreter, and checks prerequisites. Root/test subprocess bootstrap no longer rewrites ambient XDG/tool homes, which indirectly redirected uv even after UV-specific variables were removed. Normal machine-managed uv caches remain legitimate tool effects.

### implicit-source-authoring | high | Build dependencies changed checkout-owned inputs

Corrected during execution: native authority targets now validate existing publications instead of generating checkout authority; frontend dependency targets check preinstalled node_modules instead of installing; transcript refresh refuses build-time source authoring. Agent lock compilation emits a validated candidate under testing rather than overwriting committed locks. Explicit authoring commands retain their purpose.

### python-writer-admission | high | Direct helper CLIs bypassed canonical build ownership

Corrected during execution: shared admission verifies visible configure presets, physical build roots, cache/source/manifest agreement and declared output containment before write operations. Configure-stage generators use declared outputs without requiring a not-yet-created cache. Cleanup, ordinary build drivers, output-only generators and verification CLIs now use admission. Tests exercise linked roots, traversal, mismatched sources and refused external destinations before writes.

### scratch-and-cache-placement | high | Documentation and verification scratch escaped the build owner

Corrected during execution: docs caches, product/index storage, probe temporary roots, trace evidence, package-smoke work and CTest lifecycle logs/cache/scratch are now build-owned. Windows verifier fallback to development storage and external absolute destinations were removed. Existing historical caches were preserved.

### integrated-verification | low | Scoped checks pass while repository-wide gates remain unresolved

Current verdict: PENDING. Native Python lint passes. The latest focused writer, generator, cleanup, cache, authority and docs run passed 67 tests. Scoped ty checks of 22 changed native entry modules passed. Earlier integration evidence includes 76 verification-helper tests, 34 bootstrap/recipe tests and 21 direct-generator admission tests. The broad native run passed 1028 and skipped 7 but failed 5: two storage parity cases subsequently fixed and passed, and three MSI tests interacting with concurrent single-product changes. The configured repository type check reports 65 diagnostics, concentrated in MSI and runtime frontend work; import-linter reports 24 contracts kept and one runtime-test-to-dev contract broken. Native format check currently reports two concurrently edited files, installation_reuse.py and test_distribution_prepare.py. These global gates are not represented as passing. Final desktop boundary review and focused evidence are appended below when available.

### desktop-and-cmake-review-corrections | high | Direct desktop and configure routes needed the same physical ownership checks

Corrected during integrated review: desktop JS admits both root and standalone visible presets against the expected source/cache/manifest, Cargo always uses desktop_cargo, and PowerShell admits the build and child outputs before scratch or kit-copy writes. CMake validates physical declared children and the manifest before configure output. Root CTest recursively pins inherited temporary/storage defaults while preserving specific per-test values; desktop test commands and direct backend wrappers carry build-owned temp/storage too. Passing evidence: Node frontend prerequisites 12 tests, Node root/desktop path admission 6 tests, CMake binary/child admission 19 tests, nested root/child/grandchild CTest behavior 1 test, and PowerShell parser/Ruff checks. No end-to-end backend wrapper run was claimed against the stale existing build manifest.

### assembly-and-authority-review-corrections | high | Assembly destinations and the ordinary distribution hook retained implicit write routes

Corrected during final review: assembly's destination and native image input require declared outputs beneath its admitted binary owner. Eight direct-generator boundary tests pass. Docs compile now pins both product/development storage aliases; seven environment tests, scoped ty and style checks pass. Ordinary wheel/sdist authority resolution is read-only and refuses missing/incomplete publications; editable setup alone may publish. Fifteen hook tests plus one synthetic wheel/sdist rebuild integration test pass. Scope source and tests pass Ruff. Related release-cohort path migration is implemented with focused final checks pending in the owning agent.

### final-native-checks-and-recovery | low | Combined native checks pass and migration-script corruption was repaired

The combined native run passed 88 tests across direct writer admission, generator destinations, cache/cleanup integration, physical CMake boundaries, nested CTest environments, authority and documentation. Run 20261016T080115.509722Z-pytest-33064-589d4835 kept its own storage/logs/scratch under build/windows-x64/testing/build-confinement-final. Native Ruff passes; 155 native files pass format checks when the two independently edited format failures are excluded. A PowerShell replacement-loop bug temporarily corrupted campaign.py, dev/docs/build.py and RELEASING.md. Those files were reconstructed from read-only repository baseline with only reviewed path changes reapplied. Independent Luna review of all five loop-touched files found no residual character corruption, and git diff --check plus scoped Ruff passed. No Git write/revert commands were used. The required repository-wide gates remain PENDING.

### build-library-and-process-boundaries | high | Related cohort libraries required build-owned application storage and lexical output admission

Corrected after transitive review: build_storage scopes application storage, logs, scratch, derived caches and temporary directories beneath admitted work, restores process state, and leaves UV/XDG/tool homes unchanged. Its CLI admits paths before writing, preserves child status, and disables automatic source bytecode without a private Python cache prefix. Five context/CLI tests plus scoped Ruff/format/ty pass. Cohort output guards validate the original lexical path before resolving links; release build-clean owns its output inside its clean snapshot build tree before parent publication. Release snapshots are build-owned and are retained/reported after unobserved orphan-child liveness rather than automatically deleted from a dead parent PID. Ordinary completion still removes them. Workflow and controlled campaign entrypoints suppress source bytecode before imports. Source snapshot retention needs manual operator review; no new cleanup CLI was added.

### current-verification-state | low | Complete native style checks pass and the fresh repository type gate remains pending

Final native Ruff passes and all 157 native files pass formatting. The fresh configured repository type sweep reports 10 diagnostics in CLI/runtime/docs/settings areas; scoped ty across the changed packaging cohort, release, storage and cleanup modules passes. The global settings finding at storage_environment.py:586 concerns Pydantic authority model_fields inference, outside removed tool-path declarations. The original broad native run and import-boundary failures remain recorded above; no claim is made that every repository gate is green. The final related packaging/storage/scratch/cohort/release/campaign/recipe run passed 144 tests; scoped Ruff, formatting and ty passed. Independent integrated Luna review passed for the implemented scope with no remaining confinement defect. The docs module collection blocker and required global repository gates keep the overall audit PENDING. Full commands and exception notes are recorded in the Step ledger.

## Recommendations

Retain the new ownership admission and system uv behavior. Reconfigure existing builds whose path manifests still describe obsolete layouts. Finish the independently owned MSI/type/import/format gates before closing the plan's required global verification. This audit does not establish a full native bundle build or OS-level containment of arbitrary external tool hooks; a privileged filesystem trace and target-platform bundle acceptance were not run. Explicit installation and opted-in service/tracing probes retain operator-authorized external system effects.


Final scope limitation: directly invoked development pytest itself follows configured development storage unless supplied build-owned overrides. Several audit invocations wrote runner logs/scratch beneath var/storage; later parent checks supplied build roots. This is distinct from controlled CMake build/CTest behavior, and the implementation does not claim a machine-wide filesystem sandbox. Global gate status remains PENDING; steps remain open and changes uncommitted in the shared, concurrently edited worktree.

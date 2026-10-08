---
tags:
  - '#audit'
  - '#runtime-file-access-performance'
date: '2026-10-07'
modified: '2026-10-08'
body_schema: 'body-v2'
body_hash: 'sha256:26870cdf7e0b057d111b35d89d44aa51f1ed154b180c23f058e100636522d98a'
related:
  - "[[2026-10-07-runtime-file-access-performance-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
---

# `runtime-file-access-performance` audit: `Runtime file access and deferred document engines`

## Scope

## Scope

Review of completed S01 and S02 under the approved runtime-file-access-performance plan, including the diagnostic guidance correction in a42e9f838a. S04 binary rebuilding and artifact verification remain pending and will be appended here. Reviewed committed production changes in 9df7d1079d and ce897fe317 against their parent states, plus the shared working-tree interactions covered by the recorded full quality gates.

Accepted TUI D6 requires canonical strict fixed-point operation bindings; the published-authority decision requires digest-bound, format/generation admission and selective hydration; interpreter-foundation and runtime-manager decisions retain package integrity, isolated startup and owned processes. Equivalent deferred imports introduce no new public contracts, persisted schema or cache.

## Findings

### operation-engine-loading | low | Registration imported engines that only document operations use

Resolved in S02. Registration reached openpyxl/numpy through local observations, XLSX provider imports and workbook materializer composition; PDF extraction/container imports reached pdfplumber/pdfminer, PDFium and pikepdf. The owning functions now import their existing engines when the operation executes. Optional-extra checks and malformed-file refusals remain in place. Tests exercise real PDF extraction, XLSX validation/formula refusal and summary generation/verification. A fresh isolated production-registry test proves engines are absent from sys.modules while the public contract set exists. Matched full public catalogues retain 266 definitions and digest 615d08f82346ec538ddd91e7290b2b561e6add21ab586c5f52710ab5be36bc10.

### io-measurement-coverage | low | File API counts must retain their measurement scope

Python traces report open attempts and canonical caller locations, not bytes or physical media activity. Native counts report successful ReadFile transfers separately from EOF and unsuccessful opens. Normal source-registry open attempts fell from 3121 to 2735. Observed native bytecode imports fell from 3156 to 2764 successful reads and 49446890 to 44258297 reported bytes. Captures lack process-exit records; they establish observed import/admission scope, not complete process-lifetime physical disk I/O. Incomplete comparison captures were excluded from the comparison. Five diagnostic tests cover real repeated reads and missing opens, native accounting/locale/PID filtering, malformed length refusal, audit-hook reuse and exclusion of private SystemExit text.

### authority-admission | low | The measured registry read is one integrity hash

The 117620736-byte authority required 1796 successful native ReadFile events and 117620836 transferred bytes during the observed admission. Multiple CreateFile events reflect metadata/opened SQLite connections, not repeated full scans. Publication remains the structural validation boundary; runtime retains digest, format and generation guards and selective indexed hydration. Six alternating samples per buffer size proved identical hashes: existing 64 KiB median 0.08752 wall seconds/0.08594 CPU seconds, 256 KiB 0.09639/0.09375, 1 MiB 0.10227/0.10938. Larger buffers reduce read calls but cost more time, so no buffer or cache change was made.

### capture-environment-exposure | high | A raw process-start record exposed credentials in diagnostic output

One tool output inadvertently included process-start environment records containing credentials. This is an actual exposure; deleting files cannot remove that transcript output. Raw PML/CSV exports and the process-record JSON were removed; retained evidence contains selected file operations only. The diagnostic instructions now require target file-operation filtering before exporting or inspecting. Rotation of exposed credentials remains outside this repository change. No credential values enter the tracked code or audit.

### completed-source-verification | low | Source corrections pass relevant integration and quality checks

PASS for the completed source changes, with the credential-rotation follow-up above retained separately. Real extraction/spreadsheet/PDF writer and verifier, schema parity, operation composition, fresh-process registration, runtime CLI and headless native startup/identity/interference checks passed across focused runs. The recorded full format/style/type checks passed. A complete import check against an unchanged before/after tree passed with 4522 loaded modules, 15 kept contracts and zero hard findings: var/storage/development/.logs/test-runs/2026-10-07/20261007T131850.700218Z-check-import-boundaries-32264-369c86d0/artifacts/import-health.json. A prior run was invalidated by source changes and was not used as passing evidence. The later diagnostic-only guidance change passes format and changes no import/type behavior. Installed-artifact verification is PENDING under S04.

### external-signature-verification | low | The external OpenSSL test was missing from the default selection

The 114-test explicit collection included one external_tool signature test omitted by the default selection. Its first explicit run failed because OpenSSL was absent from PATH. The existing Git OpenSSL 3.5.7 was admitted in the child test PATH without modifying product or machine configuration. The real generated PDF signature passed stock OpenSSL verification, and a flipped signature byte was refused. Passing log: var/storage/development/.logs/test-runs/2026-10-07/20261007T140425.371367Z-pytest-70480-be244d4c/run.log. This closes the identified test-selection gap; no assertion or golden was weakened.

### runtime-registry-readiness | low | Moving a factory import alone would only move required startup work

Further call-stack inspection found the registry factory imported by runtime/profile_connections.py before prepare_registry. The complete caller trace reaches main.py:_serve_runtime_endpoint, which deliberately calls prepare_registry inside the registry_prepare startup phase before serving transport. Its ownership/readiness tests require an idempotent valid public graph and reject failed/stopped construction. Deferring only the factory import cannot eliminate that startup work; advertising readiness before canonical graph validation would change the accepted readiness contract. This candidate was not changed or counted as a performance gain. Rebuilt phase logs should distinguish main_import, registry_prepare and listener readiness.

### broad-suite-failure-triage | low | Five shared roots were traced and repaired without suppressing the reports

S05 inventories the separate 157-case and 113-case broad unit batches, with every one of their 270 distinct cases and its last recorded status in the requested broad-test-failure-brief audit. Current scoped repairs cover inception JSON array normalization at the strict tagged-union boundary (all 13 reported persistence cases pass), the missing read-only sign-in observation family (17 related checks pass), historical closed-range and source-covered-frame inventory selection (collection and four source/enrollment/refusal checks pass), affiliate source-family/home enrollment and eight canonical four-language leaves (nine policy checks pass), and independently stated applied-rate facts omitted by the M390 worked-example fixture (all six original oracle/delta checks pass). No new cache, production arithmetic change, weak admission, omitted assertion or skip was introduced. Seven separately probed TUI finding-word checks remain failed: six share a finite conditional-key AST census limitation and one expects differing M349 human headings; other historical groups await owning fresh evidence. The brief is not a green full-suite claim. Focused Ruff/format, configured full type checks and data-format checks pass; the first S05 import aggregate had zero hard findings but source instability invalidated its verdict, and its stable-source retry remains pending.

### current-shared-source-import-gate | low | Loadability passes but concurrent edits invalidate the aggregate

S05 full format, style, type and data-format checks passed. Three later import checks each loaded all 4522 modules, kept 15 contracts and reported zero hard findings, but source identity changed during every run. The current aggregate is unavailable and review remains PENDING for this check. Latest completed report: 20261007T151810.433463Z-check-import-boundaries-58192-5c0a00ee/artifacts/import-health.json. Earlier stable S02 evidence remains historical; it is not asserted as a passing current S05 aggregate. A final current-source run is separately in progress.

### full-package-build-failure | medium | Bundled documentation prevents the complete package from assembling

The first owning Release bundle attempt failed after 5342.08 wall seconds and 7803.31 descendant CPU seconds. Its strict documentation compile consumed 5095 seconds and reported divergent goldens across 19 pages, four real sequence execution failures and endpoint/startup/cleanup refusals. Examples include the current authority generation versus the prior generation, newly computed M303 casilla 88 and M390 formula_count 26 versus the older expected 19. These are not automatically all stale expected outputs: failures to execute and timing-dependent completed_at require owning fixes before a sanctioned reviewed refresh. The full docs-enabled bundle, ZIP and installed acceptance remain unverified. A supported CADRUMO_PACKAGE_USER_DOCS=OFF runtime-only diagnostic package is being built separately to measure the actual runtime without altering the documentation verdict. Record its absence of desktop/docs and restore the default configuration afterward. Full attempt report: build/runtime-file-access/rebuild/build-timing.json.

### Verified native package and remaining startup root (2026-10-07)

The supported runtime-only Release pipeline passed all four owning recipe stages and all 13 CTest checks, including fresh extracted-ZIP verified runtime handshake and hostile argument/displacement refusals. It took 2079.562 wall seconds with existing managed toolchain/download caches; source changed in the shared tree. This is an incremental runtime-only result, not a clean complete docs/desktop build. The default docs-enabled configuration was restored. Timing and artifact identities are retained in `build/runtime-file-access/rebuild-runtime-only/build-timing.json`.

Five fresh actual EXE runs per command now return help in median 0.5044 seconds and syntax refusals in 0.3712–0.4222 seconds. Three isolated authenticated readiness runs still cost median 20.8797 wall / 14.9688 process CPU seconds. Logical process read counts are 6215, 6222, 6220 with 57,291,522 read-transfer bytes each; they include cached reads and process handles, not physical media I/O. The development session override was absent and manifest/runtime hashes were identical before and after these runs. The main-import phases cost 10.3288–15.5724 seconds and registry preparation 3.7397–4.4062 seconds; one listener outlier was 5.8169 seconds.

A separate packaged-Python main-import cProfile identifies 2673 source-module compilations costing 6.402803 seconds under profiling (of 19.296 total profiled seconds). Existing assembly discards dependency `__pycache__`, and isolated runtime startup disables bytecode writes, so every fresh process recompiles the bundled sources. Deferred heavy engine imports remain absent. This is a measured public-code bytecode opportunity after the call-stack corrections and refines, rather than erases, the earlier finding that registry/private-state caching was unjustified. The existing deterministic standard-library bytecode publication boundary is extended to bundled packages, retaining source-hash checks, the exact interpreter compiler pin, immutable manifest inventory, and disabled runtime writes. S06 native admission and paired measurements are pending.

### native-reader-fixture | low | Backpressure test now isolates queue disconnect from child startup

The first bytecode-enabled native verification passed 12 of 13 checks but failed the manager reader fixture's five-second child-exit assertion. Its unbounded whole-suite `--list` output can itself fill stdout while the reader intentionally blocks on a full input queue. An exact one-test listing passed twice, then still failed on child-start timing; that partial attempt is not accepted verification.

The final private reader entrypoint accepts a statically dispatched `Read + Send + 'static` stream, while production still supplies `ChildStdout`. The unit fixture uses one bounded announcement and signals its first read before checking that the reader remains active. Dropping the queue receiver must release the reader within the unchanged five-second deadline. Framing, queue capacity, send/disconnect handling, process ownership, supervisor timing and production launch sites are unchanged. Three complete manager Rust suites passed (27.23s, 2.25s, 2.14s); pinned Rust 1.96 formatting passes. Real-process supervision integration and extracted-package admission remain owned by the resumed native pipeline.

### integrated-review-progress | low | Completed scoped repairs preserve their refusal boundaries

Review covers the file-access observer and six operation-engine deferrals already checkpointed, the five earlier integration repairs, literal-key discovery and the published M349 heading expectation, the native reader fixture, and the package bytecode publication changes including uncommitted code. The inception decode retains strict frozen TOML values and malformed-ref refusal; historical export selection retains source coverage and ambiguity refusal; affiliate source policy matches its independent calendar provider; worked-example rate facts restore the stated inputs without changing arithmetic expectations. Finite catalogue-key branches now enter all-language token checks while dynamic keys remain refused. Bytecode is generated after backend source adaptations using the pinned compiler, checked source hashes and deterministic relative filenames, and enters the ordinary immutable file inventory. Runtime cache writes remain disabled.

Current coverage includes 23 TUI finding checks, 20 bytecode/assembly/refusal checks, three repeated manager suites, full configured format/style/type checks, and the previously recorded complete affected-group regressions. Verdict remains PENDING for S05's stable current import aggregate (4522 modules loaded, 15 kept contracts, zero hard findings, but shared-source identity changed) and S06's final native package admission/performance comparison. S04's full docs-enabled package still has its independently recorded documentation gate failure. These are evidence gaps and separate unresolved conformance issues, not reasons to disable checks or assert the entire suite is green.

### bootstrap-and-supervision-review | low | Final call-stack fixes retain path and process refusal contracts

Integrated review additionally covers the committed S07 path correction and both native supervision coordination fixes. Bootstrap compares existing directory identities through pathlib rather than mixed-separator strings, so one Windows package directory is no longer inserted twice; enrolled order, relative-path directives and package-containment checks remain in place. Seventy-one bootstrap/delegated-inventory cases pass, including separator/case equivalence and malformed, parent-escape and absolute directives. The owning extracted-package probe now rejects duplicate resolved search paths.

The heartbeat integration assertion admits early EffectsUnknown only when TerminationUnconfirmed was actually emitted, then still requires confirmed termination and a Hang restart. The owning real-process CTest target serializes its child fixtures while preserving all readiness, drain and quit-observation deadlines. All thirteen final native checks pass. This resolves the additional fixture/resource roots without changing production supervisor deadlines or weakening strict readiness. S06 bytecode freshness, exact compiler admission and deterministic relocation have twenty focused passing checks; its final artifact comparison and startup measurements are still pending. The current full import aggregate remains unavailable because the shared tree changed during its run.

### builder-cache-prefix | medium | First bytecode producer wrote outside the assembled image

Inspection of the extracted candidate's manifest found zero inventoried dependency .pyc files despite the earlier unit and native passes. The build-tool import path reaches dev._paths, which sets sys.pycache_prefix. importlib.util.cache_from_source therefore selected the managed developer cache, not source-adjacent package output. This is a producer-context defect in the new optimization, not evidence that bytecode shipped; previous candidate admission cannot close S06.

The producer now explicitly writes the pinned cache-tag filename under each source's package-local __pycache__ directory. The strengthened first test sets a separate builder cache prefix, proves no output is written there, then uses the isolated runtime's default source-adjacent lookup and refuses any recompilation. Same-size/same-timestamp source invalidation and deterministic relocated bytes remain checked. All 41 bytecode, assembly-tools and startup-presence checks pass in `20261007T175107.483884Z-pytest-84940-b146c00b/run.log` (10.30s), and scoped Ruff/ty/format passes. An actual inventoried bytecode count and zero module source compilations in the corrected delivered image remain required before closure.

### final-package-admission | low | Corrected delivered bytecode and import paths pass native verification

The final runtime-only Windows Release pipeline passes all 13 CTest checks (528.60s), ZIP assembly, extracted-package verification and the Python 3.13.11 application probe. Total wall time is 5131.02s (85m31.02s), descendant CPU 2072.11s: configure 10.92s, native verification 1635.30s, ZIP 1127.14s, extracted-package verification 2357.65s. This is incremental with existing managed caches and concurrent source changes, not a clean isolated build. Default CADRUMO_PACKAGE_USER_DOCS=ON was restored. Documentation and desktop content are excluded; the full documentation-enabled attempt previously failed after 5342.08s.

The artifact is `build/windows-x64/packages/Release/cadrumo-0.5.1-b2157-windows-x64-Release.zip`, 382374062 bytes, SHA-256 `b897e5fc1300d7c496107e075e69391958bc79ad295e9e9eae47bd1eb850328d`. Manifest SHA-256 `d0102f2b319a9af010a7fb81483ee87e07dcb2bb67943f4de1a27862759f5ef4` inventories 18466 files including 6582 dependency PYC files and 80 distributions. Fresh extraction into a space/non-ASCII path passes admission. Full inventory verification after benchmarks passes; manifest/runtime identities remain unchanged.

### final-cache-admission | low | Equivalent executable code is proven without a global bitwise reproducibility claim

The final main-import profile records zero source-module compilations versus 2673 costing 6.403s in the retained baseline. Profile totals are 9.660s final versus 19.196s baseline. Remaining compiler calls are typing, SQLAlchemy and AST expression generation. Heavy document engines remain absent. Main-import Python open attempts fall from 5791 to 5711: .py 2673, .pyc 2673, .zip 283, .txt 80 (formerly 160), one suffixless and one .toml. These are attempts, not successful reads or bytes. Registry observation records 5395 attempts: .py 2518, .pyc 2518, .zip 275, .txt 80, .toml 1, .json 1, suffixless 2.

All 6582 cache headers match the exact relocated Python 3.13.11 source-hash compiler, and executable code, filenames and execution metadata match fresh in-memory compilation at optimization zero. 6573 caches are byte-identical; nine differ in marshal serialization representation. The exact representation cause is unproven. This supports portable filenames, checked-hash freshness and equivalent code, not complete cross-process byte-for-byte reproducibility. Runtime cache writes remain disabled. The explicit package-local producer prevents developer cache-prefix escape and builder -O behavior.

Forty-two focused bytecode/assembly/startup checks pass in `20261007T190818.766825Z-pytest-62120-12615dfb` (30.26s), with scoped Ruff, type and format checks. Seventy-one bootstrap/delegated-inventory cases pass, including identity and hostile directives. Actual final native admission, immutable inventory and the 6582-file compiler comparison close S06/S07. Overall documentation/desktop, stable aggregate import and repository quality verification remain pending.

### final-startup-comparison | medium | CLI refusal is fast while readiness remains variable

Five fresh delivered runs per CLI scenario have median wall times: help 0.495s (exit 0), invalid command 0.470s, missing value 0.408s and missing required arguments 0.494s (all exit 2). CLI parsing returns before main import and registry construction.

Baseline three-sample readiness medians were wall 20.880s / CPU 14.969s; final medians are 14.960s / 11.313s. Final wall samples are 32.471s, 14.960s and 9.757s; CPU samples 11.844s, 11.313s and 9.547s. The slowest sample spent 27.252s in main import; registry construction took 3.761–4.446s and listener creation 0.0040–0.0043s. The waiting or scheduling cause is unproven. Readiness remains a performance issue.

Both packages have 6582 source paths, the same SDK and distribution versions, but 46 Python sources differ due to concurrent authorized repairs. The observed lower medians are not isolated causal percentages attributable to bytecode. Public contract count remains 266; the new digest is `db5c5d58a2d70380ad1429a093e785159db37c803dd4b812a9f7766817aeb5b9`. Earlier unchanged-digest evidence applies to its own snapshot.

Final retained-handle process counters record 11631–11635 logical read operations and 98570673–98586824 transferred bytes versus baseline 6215–6222 and 57291522 bytes. Logical I/O increased while source compilation disappeared. Source-hash admission reads source and bytecode; these counters also include cache and non-file activity and do not establish physical media traffic. Earlier filtered native file-type measurements retain their original capture scope.

### final-review-disposition | medium | Scoped work passes while complete repository gates remain open

Integrated review passes S06/S07 against compiler pinning, equal-size/equal-timestamp freshness refusal, relocated code identity, disabled runtime writes, bootstrap path containment, inventory and actual native admission. No private-request, authority or plugin-result cache is introduced. Full documentation/desktop admission and a stable current import aggregate remain pending; the last import check loaded all 4524 modules and retained 15 contracts with no hard violations, but concurrent source changes invalidated its aggregate.

Final recorded whole-repository checks: style PASS; format FAIL on one peer-owned custody startup fixture; types FAIL on two diagnostics in peer-owned `dev/ci/runtime_probe_artifacts.py`. Preserve owning edits. The broad-case brief records 258 PASSED and 12 last recorded FAILED of the original 270. Remaining repairs belong to the separately authorized broad-repair campaign; no whole-repository green verdict is claimed.

### rebuild-time-postmortem | high | The 85-minute figure includes three assemblies and two archives

Requested retrospective analysis on 2026-10-07. No new build, package assembly, compilation, native execution or verification run was launched. The analysis reads retained timings/logs/cache receipts and filesystem metadata only. Machine-readable detail is `build/runtime-file-access/rebuild-published/build-time-postmortem.json`; its standalone analysis helper is `build/runtime-file-access/explain_build_timing.py`. All durations below concern the final completed pipeline, excluding earlier attempts, later benchmarks, source fingerprinting and default documentation restoration outside its timer.

Directly measured stage totals:

| Stage | Wall seconds | Wall time | Descendant CPU seconds |
|---|---:|---:|---:|
| Explicit runtime-only configure | 10.922964 | 0m10.92s | 3.515625 |
| test-native-bundle: dependencies, bundle and CTest | 1635.301570 | 27m15.30s | 879.093750 |
| build-native-package: dependencies, another bundle and ZIP | 1127.144398 | 18m47.14s | 478.468750 |
| test-native-package: dependencies, third bundle, second ZIP and artifact acceptance | 2357.647365 | 39m17.65s | 711.031250 |
| Total | 5131.019406 | 85m31.02s | 2072.109375 |

Stage sums differ from the outer total by 0.003108s loop overhead. Calling this figure a single incremental compile was imprecise. The owning recipes each configure and request a dependency-complete target. CMake verify depends on bundle; zip depends on bundle; verify-package depends on zip. The driver explicitly invokes all three recipes in sequence. Logs confirm Built bundle three times, Built zip twice, and installation of the three product wheels three times. The first and third passes each reinstall 77 dependencies (the install commands themselves report only 6.86s and 7.89s). The authority is reused in all three passes, so this is not authority recompilation. No documentation or desktop build occurs in this run.

CTest accounts for 528.60s, leaving 1106.70s (18m26.70s) of the first verification recipe outside its tests. Logged Cargo release build summaries outside CTest total 97.76s in the first pass, 115.35s in the ZIP pass and 122.21s in the last pass: 335.32s (5m35.32s). This is not total native compilation time: C++ compilation is untimed, and test/probe compilation is included inside their own intervals. Successful nested command timing records are discarded rather than persisted.

Every native test is independently enumerated by the retained log:

| CTest | Seconds |
|---|---:|
| bundle.image.cadrumo-manager.exe | 0.06 |
| bundle.python | 17.20 |
| bundle.entrypoint.aeat | 1.26 |
| bundle.entrypoint.cadrumo-mcp | 0.34 |
| bundle.entrypoint.cadrumo-runtime | 0.36 |
| platform.static | 0.09 |
| platform.dll | 0.12 |
| platform.rust | 0.10 |
| platform.resolver | 19.86 |
| manager.rust | 100.75 |
| manager.supervision | 198.22 |
| application.rust | 131.69 |
| application.package | 58.07 |

These individual test durations total 528.22s; CTest reports 528.60s including its overhead.

The final pass retains filesystem checkpoints. The following intervals partition its 39m17.65s approximately; they are checkpoint observations, not newly instrumented function timings:

| Final-pass interval | Seconds | Observed operation boundary |
|---|---:|---|
| Recipe log creation to product ready receipt | 359.323656 | Configuration, preparation, dependency admission, fresh product snapshot/wheels |
| Product receipt to fresh app directory | 290.606856 | Native dependencies, manifest checks, assembly admission/reset |
| Fresh app directory to assembled ready receipt | 518.654789 | Stdlib ZIP, dependency copy, relocation/adaptation, bytecode and manifest |
| Assembly ready to bundle cache receipt | 11.715831 | Output inventory and cache receipt |
| Bundle receipt to ZIP cache receipt | 174.091689 | ZIP input inventory, CPack and output receipt |
| ZIP receipt to extraction directory | 104.405259 | Verifier startup, archive admission and old verification-tree reset |
| Extraction directory to external-bin sentinel | 305.052709 | ZIP validation/extraction |
| Post-extraction sentinel to acceptance directory | 21.291684 | Initial extracted-interpreter checks and acceptance setup |
| Acceptance directory to hostile working directory | 316.637141 | Second full package copy |
| Hostile working directory to Windows verification receipt | 156.831828 | Immutable before/after hashes, native imports, product and loader refusal probes |
| Windows verification receipt to final result | 98.743944 | Rust release probe, archive/manifest recheck and final receipt |

The timestamp intervals end at result publication; about 0.292s of final process/log completion remains. Fresh assembly's 518.65s includes stdlib ZIP emission observed over 7.81s, copy/relocation before dependency bytecode, and a 346.42s interval between first and last dependency PYC creation. All 6582 generated caches are 87,007,320 bytes; their source files are 76,889,263 bytes. This is an observed cache emission interval, not a measurement of compiler CPU alone.

The manifest inventories 18466 files totaling 1,127,590,725 bytes (about 1.13 GB expanded). Artifact acceptance extracts that tree and then Windows verification copies it again with sequential shutil.copytree. The second copy's checkpoint interval is 5m16.64s; extraction is 5m05.05s. Both preserve distinct relocation and hostile-loader checks; this report does not authorize removing acceptance coverage.

Confirmed call-stack and ownership findings:

- The explicit middle packaging recipe is redundant orchestration: final test-native-package already requests ZIP and bundle. Its observed 18m47.14s cannot be presented as an exact future saving because source and freshness conditions differed.
- The shared source changed during the pipeline. Repeated dependency-complete targets therefore rebuilt changing inputs rather than verifying one frozen artifact generation. This undermines an incremental/no-op interpretation.
- Assembly's input inventory includes the entire product build directory, although assembly consumes product dependencies and wheel provenance. The final receipt hashes 42455 input files; 35784 are under product, including 23867 scratch snapshot files under build/source. It then hashes 18468 output files. This couples final assembly freshness to scratch content and repeats full-tree metadata/hash work.
- Product construction snapshots the repository, rebuilds/install wheels and re-inventories product outputs. Bundle reconstruction discards and recreates the whole staged tree, then recompiles all dependency sources. No per-file reuse of already admitted bytecode is used during a changed bundle.
- Archive acceptance performs two complete tree materializations plus full immutable inventories and multiple subprocess probes. The copies are sequential at the Python call stack.
- Logs record Cargo rebuilding ring/rustls/application in each outer pass, but the exact invalidating input or feature transition was not retained. Do not diagnose a Cargo freshness bug from these summaries alone.
- The successful CommandResult durations for product-wheel construction, assembly/CPack and platform acceptance are not persisted. No MSBuild binary log or per-action lock/CPU/I/O timeline was retained. The first two passes' finer boundaries were overwritten by later cache receipts, so exact function-level allocation of those periods cannot be recovered.

The volume reports a local NTFS drive, not a mapped network filesystem. The 34m32.11s aggregate CPU against 85m31.02s wall suggests substantial time outside active computation, but it does not identify disk, antivirus, scheduler or lock waiting. None of those causes is claimed proven.

Next changes supported by this evidence are one stable input generation, one bundle/ZIP shared by verification, narrower assembly inputs excluding build scratch, proportionate reuse of admitted bytecode, efficient isolated relocation copies, and retained per-action timings including lock waits. This turn changes no production build logic and runs no new builds.

### release-single-generation | medium | Repeated graphs and scratch invalidation corrected

S08 now routes complete release verification through `just test-native-release Release` and `native/cmake/ReleaseVerification.cmake`. The real CMake/Ninja fixture counts one bundle, one archive and one acceptance call. Assembly consumes installed dependencies, wheel provenance and runtime provenance, excluding product build scratch, duplicate runtime dependencies and verification-only backend siblings. Retained-receipt membership accounting narrows 42455 payload input files to 13278 before helper-enrollment adjustments; this is not a new build timing.

Shared and cached producers refuse completion receipts when source bytes or selected producer configuration change during construction. Independent desktop configuration remains outside the selected action identity. Full output hashes, contained-link admission and same-size mutation recovery remain intact. New phase timings live outside payload inventories and retain total, lock waits, inventory, producer, snapshot/wheel, copy/relocation/bytecode and artifact phases, including failures. Own CPU is explicitly labeled and nested wall intervals overlap. No commands, environments, subprocess output or credentials are recorded. No new per-file/application cache was added. The ignored future driver now invokes one release graph and writes a separate report; the historical 85m31s evidence is preserved.

### artifact-single-extraction | medium | Acceptance verifies one extraction in place

S09 removes the second complete acceptance copy from `artifact_verify.check`. The extracted Unicode-path package now supplies both platform acceptance and application compatibility. Admission requires an existing absolute package beneath its explicit owning root and refuses root equality, outside paths and linked directory aliases. Fresh-copy standalone acceptance remains available. Windows and POSIX controlled fixtures prohibit another copy; POSIX also traverses hostile-loader and missing/damaged-runtime restoration branches. These fixtures do not claim new actual-native loader execution.

Production hostile-loader, ambient-import, executable-pth, child identity, entrypoint, product-cohort, KDF readiness, native-runtime refusal/restoration and before/after file inventories remain in their existing acceptance path. Real ZIP/application-child fixtures prove the same extracted root reaches acceptance and compatibility, compatibility failures prevent result publication, and changed manifest or expectation bytes remain refused.

### rebuild-fix-review | low | Scoped integrated PASS; release duration remains unmeasured

Integrated S08/S09 review: PASS for the explicitly authorized fixture-based repair scope under the accepted interpreter-foundation and distribution decisions. Regression cohort: 38 passed in 114.99s, run 20261008T043423.799522Z-pytest-51748-63a644d8. Expanded package-input/timing/Cargo/assembly/bytecode/platform cohort: 38 passed in 72.17s, run 20261008T044128.291844Z-pytest-5984-65301e01. Final shared-producer stable/source/producer/independent-change cohort: four passed in 2.10s, run 20261008T044333.822922Z-pytest-71472-db344cb7. Cases overlap; these are execution counts, not a summed unique census. Scoped Ruff format/lint and ty pass; owning import-target compilation and `just --show test-native-release` pass. Evidence is under `build/runtime-file-access/rebuild-fixes-*.log` and the owning test-run directories.

No full product/native release build or installed-loader campaign ran in this repair turn, as instructed. No replacement build duration or speedup is claimed. Timing records address the prior missing action detail without proving disk, antivirus, scheduling or lock causality for the historical wall/CPU gap. S03/S04/S05 remain open for their original stable aggregate and full docs/desktop verification gaps; closing S08/S09 does not close those gates.

## Recommendations

Keep published checked-hash dependency bytecode: it addresses measured repeated source compilation after call-stack fixes, uses public content, preserves source freshness and runtime immutability, and is admitted by the exact SDK. Preserve bootstrap path identity and operation-scoped optional engine loading. Do not claim complete cross-process byte-for-byte bytecode reproducibility.

Continue readiness measurement against stable source and controlled machine contention. CLI parsing is fixed in the delivered executable, but required main import and registry construction remain costly and variable. Logical I/O increased; filtered final native file-operation capture is needed before claiming physical disk improvement. No further application, private-request or authority cache is justified; preserve integrity admission and generation freshness.

Complete full documentation/desktop packaging and stable aggregate repository gates under their owning workstreams. The runtime-only artifact is verified for its recorded scope. Use the current broad-test brief and separately authorized broad-repair plan for the remaining cases.

Rotate credentials exposed by the earlier process-environment output. Raw captures were deleted; filtering must precede export and inspection, and no process-environment records should be retained.

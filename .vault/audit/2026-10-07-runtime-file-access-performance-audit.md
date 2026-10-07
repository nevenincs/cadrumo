---
tags:
  - '#audit'
  - '#runtime-file-access-performance'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:c6427db1612a23eb0cd7d7dcf379f52421ebc297df0a285bb5005e3fc7bac50b'
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

## Recommendations

Keep published checked-hash dependency bytecode: it addresses measured repeated source compilation after call-stack fixes, uses public content, preserves source freshness and runtime immutability, and is admitted by the exact SDK. Preserve bootstrap path identity and operation-scoped optional engine loading. Do not claim complete cross-process byte-for-byte bytecode reproducibility.

Continue readiness measurement against stable source and controlled machine contention. CLI parsing is fixed in the delivered executable, but required main import and registry construction remain costly and variable. Logical I/O increased; filtered final native file-operation capture is needed before claiming physical disk improvement. No further application, private-request or authority cache is justified; preserve integrity admission and generation freshness.

Complete full documentation/desktop packaging and stable aggregate repository gates under their owning workstreams. The runtime-only artifact is verified for its recorded scope. Use the current broad-test brief and separately authorized broad-repair plan for the remaining cases.

Rotate credentials exposed by the earlier process-environment output. Raw captures were deleted; filtering must precede export and inspection, and no process-environment records should be retained.

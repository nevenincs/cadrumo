---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:cfcff4b52476cb74bfc9ab588773ae568682ab609f91d656e66f752cca9cc2f9'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
---

# `cli-action-envelope-hardening` audit: `S05 live leaf identity and input schema review`

## Scope

Reviewed `src/cadrumo/entrypoints/mcp/_input_schema.py` and `src/cadrumo/entrypoints/mcp/tests/test_input_schema.py` against the accepted action-envelope ADR, research, fixed-point reference, and plan Step `W01.P02.S05`. The review exercised stable subject identity, canonical and alias paths, required argument and option metadata, callback classification, typed resolution evidence, compatibility posture, and real-test strength. Semantic RAG preceded source discovery. Ruff passed. The focused integration run reached two passes and eleven failures before foreign concurrent work prevented CLI-tree materialisation through an unrelated missing error-code registration; that broad integration boundary remains unverified rather than green.

## Findings

### root-callback-resolution-gap | high | The live-leaf model cannot resolve the three root callback identities

The governing live denominator contains three root callback schema identities in addition to callable command leaves. `build_verb_input_schemas` projects `root.status`, `root.app`, and `root.config` through the ordinary symbolic-path rule, producing attempted paths `app root status`, `app root app`, and `app root config`; a direct probe raised `SchemaResolutionError` for all three after resolving only `app`. The root status callback's canonical CLI path is empty, while both `VerbInputSchema.cli_path` and `ResolvedVerbLeaf.cli_path` require at least one token. The new callback test exercises only `config.repair`, so it cannot detect the missing root classifications. This prevents the ADR-required exact callback join.

### legacy-resolution-mapping-shim | high | Typed resolution evidence retains an unnecessary legacy mapping API

`assert_schema_coverage` now accepts either typed `VerbLeafResolutionFailure` records or the former `Mapping[str, str]` shape, explicitly converting the mapping into typed records for old direct callers. Exact search found only one such caller, an existing test in `src/cadrumo/entrypoints/mcp/tests/test_tools_and_dispatch.py`. The project is pre-release and its architecture rules require callers and tests to move atomically to the canonical typed API rather than preserving a compatibility branch.

### target-typing-gate-red | high | The focused strict typing boundary reports seven errors

`uv run --no-sync basedpyright src/cadrumo/entrypoints/mcp/_input_schema.py src/cadrumo/entrypoints/mcp/tests/test_input_schema.py` reported seven errors and zero warnings. The failures are in `src/cadrumo/entrypoints/mcp/_input_schema.py`: the inferred property-schema dictionary rejects non-string defaults at line 114, and collection-item types are unknown at lines 267, 536, 546, and 547. A Step that extends these public typed records and projections cannot close while its exact production boundary remains type-invalid.

### root-callback-resolution-remediation | low | Resolved in S05 with a foreign root-config proof boundary

The symbolic-path authority now maps `root.status` to the empty canonical path, `root.app` to `app`, and `root.config` to `config`; both live-leaf models now admit the empty root path. Focused real-tree tests for root status and root app passed two tests in 2.64 seconds. A direct root-config build attempted exactly `config`, proving the former `app root config` S05 defect is gone, but CLI subtree materialisation then stopped on the foreign missing `ErrorCode` registration for `ModeloPriorDomiciliationElectionRefusedError`. Root-config success therefore remains externally unverified while the S05 path defect is resolved.

### legacy-resolution-mapping-remediation | low | Resolved by the typed-only failure API and caller migration

`assert_schema_coverage` now accepts only `tuple[VerbLeafResolutionFailure, ...]`. Exact caller search found no remaining mapping-shaped invocation, and the former caller in `src/cadrumo/entrypoints/mcp/tests/test_tools_and_dispatch.py` now constructs a real typed failure. Its focused integration test passed in 2.71 seconds.

### target-typing-remediation | low | Resolved with a clean focused strict boundary

The property-schema dictionary and repeated-value sequences now carry explicit types. The exact focused basedpyright command completed with zero errors, zero warnings, and zero notes; Ruff also passed both S05 target files.

## Recommendations

- For `root-callback-resolution-gap`, model explicit canonical paths for all group callbacks, including the empty root path, and add real-tree assertions for `root.status`, `root.app`, and `root.config` alongside the non-root callback case.
- For `legacy-resolution-mapping-shim`, make `assert_schema_coverage` accept only typed failure records and migrate the sole mapping-shaped test caller in the same Step.
- For `target-typing-gate-red`, give property-schema construction and repeated argument values explicit types that satisfy the repository's strict basedpyright boundary, then rerun the exact focused command.

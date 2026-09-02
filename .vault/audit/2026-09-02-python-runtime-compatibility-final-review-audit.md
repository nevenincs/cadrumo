---
tags:
  - '#audit'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:bad528304bbd88b697dcf1c2f4838a78b9dae3ac99d8f886b6a7f8445e601ee1'
related:
  - "[[2026-09-02-python-runtime-compatibility-adr]]"
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
  - "[[2026-09-02-python-runtime-compatibility-research]]"
---

# `python-runtime-compatibility` audit: `Final implementation review`

## Scope

Reviewed the accepted runtime-compatibility ADR, research, L2 plan, execution records, and the implementation in `dev/` and `src/`, together with package metadata, lock handling, cohort/wheelhouse construction, CI, publish smoke, and the runtime documentation. The intended contract is an open `>=3.13` floor, blocking CPython 3.13/3.14 rows, an advisory 3.15 canary, separate source and binary evidence, one exact 3.13.11 release builder, and `from __future__ import annotations` as the sole future directive. The compatibility-focused tests passed (53 tests in the focused invocation); the API census, inventory command, lock check, and Ruff checks also passed. Supplied runtime evidence reports source passes on CPython 3.13.14, 3.14.6, and 3.15.0b4, binary passes on 3.13.14 and 3.14.6, and an attributable advisory 3.15 binary failure for the PyYAML wheel gap. No critical finding was identified.

## Findings

### sealed-dependency-closure | high | Binary probes validate the sealed wheelhouse but install dependencies from the package index

`_load_binary_artifacts` calls `load_python_cohort` and verifies the wheelhouse manifest, but returns only the three product wheels. `_install` then invokes `uv pip install` with those local wheels and `--only-binary :all:`; it never extracts the validated runtime wheelhouse, supplies `--find-links`, uses an offline/local index, or applies lock-derived hashes to third-party dependencies. The recorded `lock_sha256` is therefore observational metadata rather than an identity constraint on the bytes installed in the target venv. A binary pass can resolve newer or otherwise different dependencies, and the reported PyYAML missing-wheel result is an index-resolution result rather than proof against the sealed cohort requested by the ADR and the runner's own docstring. This is a HIGH release-evidence defect because binary support is not proven for the immutable dependency cohort.

### target-runtime-tests | high | Stable matrix rows do not execute focused tests under the selected interpreter

The runner performs venv creation, installation, import-origin checks, `aeat --version`, and dependency checking, but it never invokes pytest or another focused behavioral test command in that venv. The dedicated workflow contains no target-runtime test step. The focused annotation and compatibility tests run in the repository's tool environment (normally the pinned 3.13 builder), so they cannot detect a 3.14-specific or 3.15-specific behavioral regression. The accepted ADR and plan explicitly require each blocking row to exercise relevant focused tests; until those tests run with the selected runtime and their result is included in the row verdict, the stable support claim is incomplete.

### final-evidence-provenance | high | Supplied evidence is split across commits and is not bound to one final compatibility state

The source records identify different source commits (`edbd5f12…`, `94df0c823…`, and `7e92bc76…`), while both stable binary records and the sealed cohort identify `10154f14ae…`. At review time the checkout had advanced to `8f8790077c…`, and the live `uv.lock` digest was `d55919715ef023c783947a35e11e569243c367298045fb5681fab8d437a1b6ac`; later source, metadata, and lock changes are present after the cohort commit. The records are useful historical evidence, but they cannot serve as a final release claim until all matrix modes are rerun from one clean, immutable commit and the resulting source/binary/artifact digests are attached to that exact state.

### canary-selector-identity | medium | The declared 3.15 canary selector is not the selector/version exercised by the evidence

The inventory declares `3.15.0-rc.2`, while the supplied source evidence uses selector `3.15` and observes CPython 3.15.0b4. `_runtime_identity` accepts any interpreter with the same `3.N` minor, so a b4 interpreter can satisfy an rc2 declaration. In the review environment `uv python find --offline 3.15.0-rc.2` failed, while `uv python find --offline 3.15` selected the installed b4 interpreter. Reconcile the inventory with an actually provisionable canary or enforce and record exact release-channel identity before treating the row as evidence for the declared selector.

### future-directive-reachability | medium | The future-import policy is not part of the normal compatibility or per-push gate

`_future_directive_violations` in `dev/tests/test_import_hygiene_scan.py` correctly permits only `annotations`, and the live scan is green. However, `test-dev-ci` does not collect `dev/tests`, and the dedicated runtime workflow does not invoke this test or a future-statement scanner; the broader `test-dev-tooling` lane is dispatch-only and currently configured as non-blocking. A new unsupported `from __future__ import ...` directive can therefore evade the ordinary push/runtime compatibility verdict even though the policy exists. Wire the AST check into a blocking lane that runs on compatibility-relevant changes.

### mcp-surface-unprobed | medium | Dedicated source and binary rows do not smoke the declared `cadrumo-mcp` entry point

The accepted ADR names both `aeat` and `cadrumo-mcp` as artifact surfaces. The runtime runner's installed probe invokes only `aeat --version`; the MCP surface is exercised by the separate publish smoke script, not by the source/binary rows that carry the compatibility evidence. A dependency or import regression isolated to the MCP server can therefore leave a row green. Add the MCP help/import probe to both mode-specific target-runtime verdicts or explicitly bind the publish smoke result into the row evidence.

### failure-taxonomy | low | Missing-wheel detection matches any installer output containing the word wheel

The binary failure classifier treats a result as `missing-wheel` when lower-cased output contains the broad token `wheel`, in addition to more specific resolver phrases. Unrelated build, metadata, or verification failures that mention wheels can be misattributed as an upstream wheel gap, weakening the promised dependency evidence. Prefer structured resolver status or narrowly scoped diagnostic patterns.

## Recommendations

Resolve the three HIGH findings before marking the feature complete: install binary dependencies exclusively from the verified wheelhouse (or generate an equivalent lock/hash-enforced local requirements path), run the required focused behavioral tests with each selected stable interpreter, and publish target-runtime test results in the immutable evidence record.

After the final compatibility implementation and lock changes settle, perform one clean-commit matrix run for source, binary, and sealed-artifact smoke. Ensure the declared canary selector is the one provisioned and recorded, promote only evidence tied to that commit, and keep the advisory 3.15 binary wheel gap visible.

Move the future-directive and MCP probes into the blocking compatibility surface, then narrow the failure classifier. The existing `from __future__ import annotations` policy itself is correct for the supported runtimes; it is the reachability of its gate that needs hardening.

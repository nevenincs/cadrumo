---
tags:
  - '#reference'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:15774c06eb86d81bbcd63b4a664de029b4e5f863f1d78d640d14cc77b5577fbc'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
# `registry-authority-artifact-boundary` reference: `installed behavioral proof`

This reference grounds W03.P05.S07 in the accepted artifact-publication decision and the live publication, packaging, CLI, and MCP harnesses. The implementation epicentres were read directly because semantic RAG was unavailable from the current client/daemon version mismatch.

## Summary

The repository already proves most of the success path. Development publication compiles a real candidate and preserves a prior publication byte-for-byte on validation failure. A separately maintained packaging harness snapshots the enumerated repository, builds and installs one hashed wheel cohort into a fresh virtual environment, proves the installed package has no authored registry tree, and runs matching real CLI and stdio MCP tax workflows outside the checkout.

The remaining S07 proof is behavioral rather than structural: physically remove or corrupt the authority artifact inside a disposable installed cohort and demonstrate that real CLI and MCP work refuse before producing calculation output or durable work state. A second missing proof must mutate only the private source snapshot after the wheel is built and show that the already-installed CLI and MCP evidence remains identical until an explicit valid republish and rebuild.

## Existing publication proof

`dev/registry/tests/test_authority_publication.py:160` defines `_previous_publication`, a complete typed known-good artifact. `_stage_valid_candidate` at line 214 creates a minimal candidate that traverses the real compiler, evidence, runtime-catalogue, and publication path. The `isolated_provider_registration` fixture at line 209 keeps this candidate independent of unrelated provider corpora.

`test_staged_candidate_publishes_and_the_reader_consumes_it_as_current` at line 273 calls `publish_authority_candidate_workflow`, reads the result through `read_authority_artifact`, and proves the currency gate accepts the recorded candidate identity. `test_defective_candidate_refuses_before_replacing_the_previous_artifact` at line 343 is the direct reusable known-good-retention oracle: it writes the previous artifact, captures its bytes, invokes the real workflow on defective roots, and requires the destination bytes to remain identical. The provider omission, divergent record-design manifest, same-length evidence replacement with restored timestamps, and validation/publication race cases at lines 362, 380, 411, and 449 repeat that byte-preservation invariant at more specific transaction boundaries.

`dev/registry/pipeline/cli.py:79` owns `publish_authority_candidate_workflow`. `dev/registry/pipeline/authority_publication.py:208` validates a candidate and captures its input receipt; `publish_validated_authority_candidate` at line 576 and `_publish_candidate` at line 641 own the guarded atomic replacement. S07 should call these surfaces rather than reproduce compiler or atomic-write behavior.

`dev/registry/tests/test_authority_artifact_currency.py:59` provides `_fresh_publication`. Its registry and source-evidence mutation cases at lines 84, 95, and 107 prove that content changes make a development publication stale, including stat-preserving edits. The real conformance CLI refusal at line 167 proves a stale artifact exits with status 1, writes no stdout, and reports the republish command on stderr before compiling.

## Existing installed-cohort proof

`dev/packaging/tests/test_installed_oracles.py:93` defines `InstalledCohort`; its module-scoped `installed_cohort` fixture at line 150 is the primary reusable harness. It copies `repository_files` through `snapshot` from `dev/source_tree.py:111` and `dev/source_tree.py:279`, builds one closed-world cohort with `build_python_cohort` from `dev/packaging/python_cohort.py:1041`, creates a clean pip virtual environment, installs the exact root and companion wheels, runs the dependency check, resolves the installed `aeat` and `cadrumo-mcp` scripts, and retains source and artifact digests.

`test_installed_runtime_imports_authority_without_authoring_sources` at line 278 already runs an isolated `python -I` probe outside the checkout. It calls `bundled_authority`, requires `cadrumo/_data/registry/aeat` to be absent, verifies the artifact frame contains only `payload` and `payload_sha256`, and requires a non-empty authority.

`test_cli_and_mcp_complete_the_same_grounded_oracle_from_that_cohort` at line 312 already runs the actual installed workflows. It calls `run_installed_tax_oracle` from `dev/packaging/installed_tax_oracle.py:458` and `run_installed_mcp_oracle` from `dev/packaging/installed_mcp_oracle.py:515`. The two oracles use the public CLI and MCP protocol, persist real work and observations, compare casilla value, formula, legal references, source references, and notices, and attest that MCP invoked the installed CLI from the same cohort.

Reusable low-level helpers are `run_checked` at `dev/packaging/lane_verification_core.py:260`, `venv_python_path` at line 790, `create_pip_venv` at line 916, and `installed_product_env` at line 1017. The last helper removes checkout import paths, selects only the tested virtual environment on `PATH`, and assigns disposable product storage.

## Existing runtime refusal proof

`src/cadrumo/domain/calculations/registry/tests/test_bundled_authority_artifact_runtime.py:58` defines `_stage_runtime_publication`, while `_use_staged_package` at line 105 redirects only the package-resource seam. The tests at lines 182, 280, and 293 prove repeated corruption refusal after a good read and missing or corrupt publication refusal without an authoring fallback. These are strong domain tests but remain in-process and do not exercise installed CLI or MCP behavior.

Wire-level hostile cases are available in `src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py`: `_publish` creates a valid framed artifact, `_write_frame` recomputes a frame digest for typed-payload attacks, the line-195 case changes payload under the old digest, and the malformed and missing cases at lines 278, 307, and 313 establish the expected error classes.

## Coverage gaps

- No installed test physically removes `cadrumo/_data/registry/authority/authority.json` and invokes an authority-dependent public CLI or MCP workflow.
- No installed test corrupts that artifact after a successful read and proves both entrypoints refuse rather than serving cached authority.
- The in-process refusal tests prove exception type but do not prove that a failed installed workflow emits no successful calculation envelope and creates no work or calculation state.
- Known-good preservation is proved through the real publisher, but not through an external publisher subprocess. The existing direct workflow is sufficient unless S07 explicitly requires command-boundary output semantics.
- Source mutations make the development currency gate stale, and deletion of a legal source still permits direct artifact reads, but no installed test compares a real CLI/MCP result before and after mutation of the private post-build authoring tree.
- There is no top-level `tests/integration` tree. Installed behavioral tests currently live under `dev/packaging/tests` and carry the integration, entrypoint, and serial markers.
- `dev/packaging/python_cohort.py:910` still calls `_stamp_bundled_registry_records_into_build_tree`, whose documentation describes install-stable records beside the authored registry tree. The current distribution policy excludes that tree, so S07 should verify whether the stamp is now a development-only no-op or obsolete setup before treating it as installed evidence.

## Minimal implementation blueprint

Extend `dev/packaging/tests/test_installed_oracles.py`, the narrowest existing owner of installed CLI/MCP cohort behavior. Reusing its module fixture avoids a second wheel build for non-destructive source-isolation proof. Hostile installed-artifact cases must not leave the shared module virtual environment modified: either install the fixture's already-built wheel paths into a fresh per-case virtual environment, or restore the exact artifact bytes in a guaranteed finalizer before any other cohort test can run. A fresh per-case environment gives the stronger isolation claim.

Locate the installed artifact through an isolated interpreter and `importlib.resources`, not by assuming a platform-specific site-packages path. Establish a successful authority-dependent workflow first, then corrupt the artifact without updating `payload_sha256`; invoke real CLI and MCP work from fresh storage roots and require non-success, no success envelope, and no created work/calculation records. Repeat with the artifact absent. Keep the hostile environment outside the checkout and assert authoring inputs remain absent so refusal cannot be satisfied by fallback compilation.

For source isolation, mutate an authored registry or evidence file only inside the fixture's private `clean-repository` after cohort build and installation. Confirm the development currency identity changes, then rerun the already-installed CLI and MCP oracles with fresh storage roots. Compare the operative value, formula identifier, legal and source references, notices, and installed payload identity with the baseline. They must remain identical. A changed behavior is expected only after a valid republish, rebuild, and reinstall; do not imply that editing authoring inputs updates an existing installation.

Retain the existing publication-preservation tests as the transaction oracle. S07 should compose their evidence with the installed tests rather than duplicate candidate construction or atomic publication code in the packaging harness.

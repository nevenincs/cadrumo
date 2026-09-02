---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:6f3d4f7967ffdb510ae26b8c3cd2f29f8b9f2209757295ef80c45354d58b5475'
step_id: 'S11'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Move the MCP console script into the product distribution and assert it in the distribution smoke check

## Scope

- `pyproject.toml`

## Changes

R src/cadrumo-harness/src/cadrumo_harness -> src/cadrumo_harness
D src/cadrumo-harness/pyproject.toml
D src/cadrumo-harness/README.md
D src/cadrumo-harness/LICENSE
D src/cadrumo-harness/NOTICE
M pyproject.toml
M uv.lock
M dev/packaging/_smoke_common.py
M dev/packaging/acquire_homebrew.py
M dev/packaging/cohort_manifest.py
M dev/packaging/distribution_evidence_emit.py
M dev/packaging/installed_mcp_oracle.py
M dev/packaging/release_cohort.py
M dev/packaging/smoke_homebrew.py
M dev/packaging/uv_constraints.py
M dev/packaging/tests/test_installed_cli_resolution.py
M dev/quality/import_hygiene_scan.py
M dev/locales/_paths.py
M dev/agent_eval/_live_harness.py
M src/cadrumo_harness/tests/test_dependency_direction.py
M src/cadrumo_harness/tests/test_marketplace_generation.py
M src/cadrumo_harness/mcp/tests/test_command_policy_authority.py
M src/cadrumo_harness/mcp/tests/test_stdio_lifetime.py
M .github/workflows/agent-harness-eval.yml

## Notes

The smoke assertion this Step's action names is not added here: it belongs with the
smoke check itself, and the command surface it would probe cannot currently start
because of an unrelated import failure in the CLI's command-spec support module.

The directional gate keeps its import half and loses its metadata half. The import
assertion - that no module under the command tree reaches the agent package - still
holds and still has teeth. The metadata assertions did not survive the merge: one
forbade a published dependency edge between two distributions that are now one, and
another forbade a product console script pointing into the agent package, which is
precisely what the decision mandates.

The package rose two levels in the tree, so four modules computing the repository root
from their own file depth were resolving outside it. One of them was the directional
gate, which scanned an empty file set and passed on an empty assertion rather than
failing - a gate finding nothing to scan is indistinguishable from a gate finding no
violations.

The constraint export previously named the agent distribution deliberately, because as
a workspace member its resolution was the union of both distributions' third-party
closures. With one distribution the product's own closure is that whole surface, so the
coverage guard that asserted the union became tautological and is retired with the
helper that fed it.

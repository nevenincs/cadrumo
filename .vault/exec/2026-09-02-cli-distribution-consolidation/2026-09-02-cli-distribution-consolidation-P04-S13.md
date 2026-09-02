---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:0209300fbae9d97ce5da2dfb219783e7c699c0592cd8bc6945b9d72f7a3becbe'
step_id: 'S13'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Delete the host-extension channel artifacts and their acquisition lanes

## Scope

- `packaging/mcpb/build.py`

## Changes

D .github/workflows/packaging-claude.yml
D dev/packaging/acquire_claude_plugin.py
D dev/packaging/acquire_mcpb.py
D dev/packaging/desktop_capture.py
D dev/packaging/emit_real_client_evidence.py
D dev/packaging/marketplace_publish.py
D dev/packaging/smoke_desktop_client.py
D dev/packaging/smoke_mcpb.py
D dev/packaging/smoke_plugin_install.py
D dev/packaging/verify_distribution_identity.py
D dev/packaging/tests/test_claude_workflow.py
D dev/packaging/tests/test_desktop_capture.py
D dev/packaging/tests/test_emit_real_client_evidence.py
D dev/packaging/tests/test_marketplace_publish.py
D dev/packaging/tests/test_plugin_session_gate.py
D dev/packaging/tests/test_smoke_mcpb_resolution.py
D dev/packaging/tests/test_verify_distribution_identity.py
D packaging/marketplace/.claude-plugin/marketplace.json
D packaging/marketplace/.claude-plugin/supersedes.json
D packaging/marketplace/.gitignore
D packaging/marketplace/README.md
D packaging/mcpb/build.py
D packaging/mcpb/manifest.json
D packaging/mcpb/tests/test_build.py
D packaging/mcpb/tests/test_client_install.py
M dev/packaging/release_cohort.py
M dev/packaging/tests/test_installed_oracles.py
M justfile

## Notes

The artifact-kind members for the two host-extension channels are deliberately left in
place. The channel descriptor still declares those channels, and a parity gate requires
every kind to be surfaced by exactly one channel, so removing them here would break that
gate. They retire with the descriptor.

Two surfaces beyond the Step's literal scope had no subject left once the channels went:
the distribution-identity verifier, which checked identity text across the plugin,
marketplace and bundle manifests, and two oracle tests driving the marketplace plugin and
the real-client emitter.

`dev/packaging/publication_inputs.py` still names the retired capture command in a
refusal string. Nothing invokes that module now that the orchestrator is gone, and the
module retires with the launch-phase vocabulary, so the reference is left for that Step
rather than edited twice.

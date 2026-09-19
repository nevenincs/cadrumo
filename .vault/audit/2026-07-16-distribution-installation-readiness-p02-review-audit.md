---
tags:
  - '#audit'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:3e4c366bf6246a00ba895fb8f6d979c182d856b06af3b12fecfbd33b42677937'
related:
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
  - '[[2026-07-15-distribution-installation-readiness-plan]]'
---

# `distribution-installation-readiness` audit: `Installed tax and MCP phase code review`

## Scope

Current-state review of phase `W01.P02`: installed CLI and MCP tax-work oracles,
same-installation CLI resolution, cold-session profile health, installed-environment
isolation, and cohort evidence. Findings were re-read against the current working tree
after the S62 and S63 implementation landings.

## Resolved findings

### cold-session-repair-authority

S62 now treats master-key unlock and secret-store access failures as non-repairable
profile health states. The real encrypted file-provider regression proves a confirmed
repair request preserves the exact active pointer.

### direct-mcp-tool-bypass

S63 activates the modelo lifecycle toolset and invokes
`cadrumo_modelo_work_calculate` directly. The oracle now exercises the advertised
per-command MCP surface rather than only the generic `execute` tool.

### legal-reference-specificity

S63 requires the target observation to carry the exact LIS Article 29 legal reference
and the expected AEAT manual source, formula, revision, work-unit, and casilla identity.

### observation-resource-identity

S63 requires both the calculation envelope and returned resource contents to identify
`cadrumo://observations/{calculation_revision_id}` exactly.

### noncalculation-error-notices

S63 requires every non-calculation envelope to have success status and refuses warning
or error diagnostic notices.

### installed-path-regression

S64 now runs the complete grounded MCP itinerary from the installed server outside the
checkout with product scripts removed from `PATH`.

### invoked-cli-origin

S66 records the exact supervised `argv[0]` through payload-free production telemetry.
S65 requires one attestation for each of profile creation, work creation, calculation,
and observation retrieval; rejects missing, duplicate, or divergent attestations; and
binds the shared executable-path digest to the installed cohort.

### dormant-cohort-test

S65 enrolls the cohort module in configured pytest discovery and adds a dedicated
serial installed-cohort command to the packaging-smoke workflow.

### snapshot-evidence-identity

S65 builds one immutable source commit, records all three wheel digests, and binds the
installed direct URLs to those exact artifacts.

### oracle-evidence-not-retained

S65 writes the complete CLI and MCP oracle evidence, immutable source identity, wheel
digests, aggregate executable-path digest, and per-command executable attestations to
a stable evidence path. Packaging CI uploads that evidence under `if: always()` with a
14-day retention period.

## Open findings

None.

## Recommendations

1. Continue using the installed cohort oracle as the release claim boundary for the
   Python CLI and MCP server.
2. Preserve the exact per-command executable coverage and CI evidence upload when the
   packaging workflow evolves.

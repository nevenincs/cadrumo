---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:957fce2275460f8f5dfdc8a6fbdad8cb64d3668ddd9008d68ead68f36da3d845'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# `cli-action-envelope-hardening` audit: `S13 manifest action profile contract`

## Scope

Independent review of `W02.P04.S13`: the new
`ManifestActionProfile` record, its public `operator_surface` facade export,
and its production-import contract tests. The review checked the accepted
ADR/research/reference and the S13/S14/S15 plan boundary. It specifically
tested that the record retains one `(subject_leaf_key, condition_id,
scenario_id)` association to either an `ActionReference` or an explicit
`NoRecoveryOutcome`, uses the established canonical identity forms, and stays
free of predicate, runtime-evidence, argument-binding, localized-prose, and
CLI-command data.

The current change is limited to the strict declarative model and public
re-export. It performs no catalogue lookup or live command/input-schema
resolution (S14) and has no MCP projection (S15). The sole action field reuses
the canonical `ActionReference` rather than declaring a second action catalogue
or an independently authored command identity.

Verification passed: `uv run --no-sync pytest
src/cadrumo/application/operator_surface/tests/test_action_profiles.py` (10
passed); focused Ruff check and format check (clean); and focused BasedPyright
(0 errors, 0 warnings). The test module imports the production public facade
and action models directly, exercises both real outcome branches and invalid
shape rejection, and contains no fake, stub, mock, patch, or mirrored business
logic.

## Findings

No CRITICAL, HIGH, MEDIUM, or LOW S13-specific finding. The profile carries
the exact live-coverage tuple and exactly one declarative recovery alternative;
`extra="forbid"`, strict frozen validation, the namespaced-identity checks, and
the exclusive-outcome validator prevent the prohibited data and ambiguous
association shapes. S13 neither duplicates application predicate authority nor
reaches into the later catalogue-resolution or MCP-projection responsibilities.

## Recommendations

No S13 implementation change is recommended. Keep action-profile collection,
catalogue/live-schema resolution, binding sufficiency, and MCP transport work
within S14 and S15; do not grow this declaration with lookup, predicates,
evidence, values, presentation text, or command strings.

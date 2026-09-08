---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:40bdb838d4eb679623f18d7622299c1d591bd7e714d9df47d663ba6b49593832'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S224]]"
  - "[[2026-08-23-secure-storage-performance-hardening-command-spec-authority-adr]]"
  - "[[2026-09-04-reachability-burndown-reference]]"
---

# `reachability-burndown` audit: `S224 overview verb roster census withdrawal review`

## Scope

Independent review of W05.P12.S224, limited to deletion of the duplicate `EXPECTED_OVERVIEW_VERBS` roster assertion and `command_spec_nodes` import from the overview explain integration suite, retention of the canonical command-spec tests and six real CLI explain tests, the command-spec authority ADR, orphan-walker support-hop behavior, cadence guidance, and Step Record evidence.

## Findings

No critical, high, medium, or low findings.

The removed assertion was a hand-maintained seven-name duplicate of the production CommandSpec authority. The retained `test_overview_specs_match_the_independent_operator_path_set` is the owning exact-set gate, while its companion tests verify public/resolvable leaf targets and schemas plus runtime compilation of required and aliased options. Removing a second exact roster from an unrelated explain suite reduces synchronization surface without weakening the command-tree contract authorized by the accepted CommandSpec ADR.

All six explain tests remain. They execute the real CLI through `invoke_cached_cli` and cover required arguments, known-modelo rendering, registry-backed JSON schedule data, unknown-modelo refusal, help locality, and structured Modelo 721 behavior. These are materially protective behavioral tests; no production or integration behavior was removed.

The support-hop explanation is sound: once the dead `command_spec_nodes` projection edge is removed, the suite remains reachable through its shared CLI runner into the product entrypoint. The orphan detector's movement from 10 to 9 therefore reflects removal of the dead direct subject while preserving the suite through a live support edge, not an allowlist or path exception.

The Step Record accurately reports Ruff success, three canonical spec tests in the selected lane with six explain integration tests deselected there, a separate six-pass integration lane, and exact graph evidence of 60 unreachable modules, 307 exact unused symbols, 9 orphaned tests, and 2029/2090 reachable shipped modules. No named replacement roster or production/dev metastate was introduced.

## Recommendations

Approve W05.P12.S224. Keep overview membership owned by the canonical CommandSpec exact-set gate and CLI semantics owned by the behavioral integration suite; do not duplicate verb rosters across feature tests.

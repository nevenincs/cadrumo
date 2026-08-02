---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:0fc8c45d33c7f7d2167d31d30a85f3237dd0c455d9df92344342dc9170b7a592'
step_id: 'S04'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Record OP-9 as a named operator settings action removing the required_reviewers protection rule from BOTH the release and docs environments while keeping each environment and its branch_policy, and add a read-only forge inventory probe that reports each environment protection-rule set without mutating anything so the operator half is verifiable rather than assumed, gate: uv run --no-sync pytest dev/release/tests -q -k environment_inventory passes over fixture payloads covering a rule-present, a rule-absent, and an unreadable-environment response

## Scope

- `dev/release/environment_inventory.py`
- `dev/release/tests/test_environment_inventory.py`
- `RELEASING.md`

## Description

- Add the read-only forge environment inventory, one GET per environment, resolving `gh` through the same injection contract the readiness gate's blocker check already uses.
- Model the result as a three-way outcome: rule present, rule absent, or unreadable, with `rule_types = None` carrying the third case.
- Add eight behavioural tests driving real executable stubs through real subprocess calls, covering rule-present, rule-absent, non-zero exit, non-JSON output, absent tooling, the default environment pair, the parse layer's tolerance, and the module's own absence of a mutation path.
- Rewrite the runbook arming step that instructed the operator to add a required reviewer, and add an operator-actions section recording OP-9 with its verification command.
- Declare the module's S603 per-file exemption in the project lint configuration, alongside the identical existing entry for the readiness gate.

## Outcome

`uv run --no-sync pytest dev/release/tests -q` reports 220 passed. `ruff check dev/release/` and `ty check` both pass, and the runbook conformance gate reports 8 passed.

The runbook now tells the operator to remove the rule rather than to add it, names both environments, and states what must NOT be removed alongside it. The probe makes the result checkable: an obligation that leaves no commit is otherwise unverifiable from inside the repository, which is precisely how the two partial executions this campaign is closing went unrecorded.

## Notes

The design decision worth recording is the three-way outcome. The obvious shape is a boolean "does this environment carry a human gate", and it is wrong in a way that matters here: an environment with no protection rules and an environment whose rules could not be READ are opposite facts that a boolean renders identically. Since the probe exists to confirm an operator obligation, collapsing them would report an unreachable forge as a discharged obligation - the same false-clean shape as the partial executions it audits. `rule_types` is therefore `None` when undetermined and the empty tuple when genuinely rule-free, the renderer says `UNKNOWN` rather than `satisfied`, and the CLI exits non-zero on any unreadable environment.

One test exists purely to constrain future edits rather than to exercise behaviour: `test_the_module_exposes_no_mutation_path` scans the module for write verbs. An inventory that could also mutate would be standing authority over exactly the settings it audits, and the tempting future edit is a convenience helper that removes the rule while it is already there. The refusal is cheap now and unarguable later.

The S603 exemption is a declared per-file entry with a stated rationale, matching the existing entry for `dev/release/readiness.py` whose subprocess contract is identical. This is the project's established convention for the resolved-executable pattern that ruff's heuristic cannot see, not a lint skip: the contract is a resolved executable plus a fixed three-element argv.

Two adjustments were needed after the first run. The test module was missing the mandatory `hex_*` marker, which surfaced as an xdist worker crash rather than a readable error; running serially produced the real message. Recorded because the crash was actively misleading about its own cause. Second, `pyproject.toml` was checked for peer WIP before editing and was clean.

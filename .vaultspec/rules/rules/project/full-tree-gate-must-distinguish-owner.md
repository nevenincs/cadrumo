---
name: full-tree-gate-must-distinguish-owner
---

# Full tree gates must distinguish owner

## Rule

When a required full-tree gate is red in the shared factory worktree, always record the exact current failure signatures and distinguish owner-surface failures from unrelated peer churn before marking a feature step complete.

## Why

The `2026-06-11-ledger-hardening-close-audit-pass-2` found the C4 alias-retirement implementation green on focused lint, registry/operator tests, API-stub conformance, and CLI conformance while the mandated full `src/aeat` collect-only gate stayed red from support-module export splits owned by other campaigns. Without owner triage, a closeout pass either falsely claims green or opportunistically edits unrelated peer work. The rule preserves honesty without broadening the feature's ownership boundary.

## How

- Good: capture the full-tree gate output to a log, extract the import/error summaries, name the affected modules, and keep the plan step open when failures are outside the feature surface.
- Good: if the failing signatures are in the feature's touched files or contracts, fix them before closing the step and rerun the full-tree gate.
- Bad: marking a full-tree verification step complete because focused feature tests passed while the repository-wide gate still has untriaged collection errors.
- Bad: patching unrelated support modules just to make a closeout gate pass when those files belong to active peer campaigns.

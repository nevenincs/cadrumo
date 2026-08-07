# Full-tree gates must distinguish owner

When a required full-tree gate is red in this shared worktree, record the exact
current failure signatures and distinguish owner-surface failures from unrelated
peer churn before marking a feature step complete.

A closeout audit once found an implementation green on focused lint, registry and
CLI conformance tests while the mandated full-tree collect-only gate stayed red
from support-module export splits owned by other campaigns. Without owner triage,
a closeout either falsely claims green or opportunistically edits unrelated peer
work. This preserves honesty without broadening the feature's ownership boundary.

## How

- **Good:** capture the gate output to a log, extract the import and error
  summaries, name the affected modules, and keep the plan step open when failures
  are outside the feature surface.
- **Good:** if the failing signatures are in the feature's touched files or
  contracts, fix them before closing the step and re-run the full-tree gate.
- **Bad:** marking a full-tree verification step complete because focused feature
  tests passed while the repository-wide gate still has untriaged collection
  errors.
- **Bad:** patching unrelated support modules just to make a closeout gate pass
  when those files belong to active peer campaigns.

Companion: `aeat-quality-gates`.

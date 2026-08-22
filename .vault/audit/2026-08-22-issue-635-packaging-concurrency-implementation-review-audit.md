---
tags:
  - '#audit'
  - '#issue-635-packaging-concurrency'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:943e58ecbf1f7afe9e79cf50ada2ca13b1a5463ba42f08671e8c2ae0d96697b3'
related: []
---



# `issue-635-packaging-concurrency` audit: `Packaging quick concurrency implementation review`

## Scope

Fresh-context review of issue 635 implementation commit
`1088c30311aede2dd7b35bd2797c24c9a7e22c3c` against its parent. The review
covered the two changed files and the complete `packaging-quick.yml` workflow:
all three triggers, workflow-level concurrency expression contexts, per-ref
grouping, cancellation polarity, same-repository pull-request guards, runner
queue watchdog, three operating-system probes, timeouts, permissions,
artifact/evidence prohibitions, and the full-campaign separation.

`HEAD` was verified as the requested implementation commit and the worktree was
clean apart from this CLI-scaffolded audit. Actionlint accepted the changed
workflow and Git's whitespace check accepted the implementation diff. The
focused packaging-workflow integration file passed all four tests. A broader
watchdog selection passed 19 tests and reported one existing failure concerning
`ci-runner-probe.yml`'s `hang-windows` job; that workflow is unchanged by issue
635 and does not participate in the reviewed packaging concurrency group.

## Findings

No critical, high, medium, or low findings were identified. `github.workflow`,
`github.ref`, and `github.event_name` are valid workflow-concurrency contexts.
Pushes to main share one group and do not cancel its running member; a newer
arrival replaces only an older pending member, preserving GitHub's bound of one
running plus one pending. A manual dispatch follows the same non-cancelling
rule on its selected ref. Pull-request runs group by the pull-request merge ref
and set cancellation true, so a new revision supersedes its in-flight result.
The test pins both the group and complete conditional expression, so changing
the event polarity or ref grouping breaks the gate. No trigger, watchdog,
probe, timeout, permission, or evidence-honesty surface changed.

## Recommendations

No code remediation is recommended; issue 635 is safe to integrate. Closure
should follow one live post-integration observation, recorded with Actions run
IDs, event names, refs, head SHAs, creation/start/completion times, statuses,
and conclusions:

- Start two artifact-relevant main pushes close enough that the second becomes
  pending. The earlier in-progress run must finish without conclusion
  `cancelled`, the later run must start only after it releases the group, and
  the group must never show more than one running and one pending member.
- While a same-repository pull-request run is active, update that pull request.
  The older run must conclude `cancelled` and the newest revision must proceed.
- Dispatch the workflow manually on main while another main-ref quick run is
  active. The active run must not be cancelled; the dispatch must remain the
  sole pending member or replace an older pending member, then proceed after
  the active run finishes.

Those observations test GitHub's live scheduler behavior that static YAML,
actionlint, and repository tests can validate structurally but cannot execute.

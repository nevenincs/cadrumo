---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W05.P15.S51'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# W05.P15.S51 - Semgrep Include/Exclude Policy

## Scope

- `.semgrepignore`

## Work

Added a root Semgrep ignore policy for the existing `just audit-security`
target. The policy keeps production source under scan by default and excludes:

- colocated test modules and test package trees;
- explicit test-support fixture modules that intentionally avoid pytest
  collection naming;
- mirrored official registry/corpus data under `src/aeat/_data/`.

The change does not suppress production findings and does not alter the
`audit-security` command.

## Verification

- Semgrep documentation review: `.semgrepignore` uses gitignore-style pattern
  syntax and is read by Semgrep scans.
- `uvx --from semgrep semgrep --version`
- `just audit-security`

## Outcome

Semgrep 1.165.0 is available locally. `just audit-security` completed
successfully, scanned 890 tracked files, skipped 17,238 files via
`.semgrepignore`, and reported 11 remaining production findings. Those findings
remain visible for later policy and remediation rows rather than being hidden
by this S51 scope split.

## Notes

2026-06-04 blocker:

The separate project-regression rule lane was blocked before scanning:
`uvx --from semgrep semgrep scan --config .semgrep/rules/ --error src/aeat/`
reports invalid YAML in `.semgrep/rules/no-any-annotation.yml` at line 25.
That pre-existing rule-file defect is not resolved in this `.semgrepignore`
slice.

2026-06-05 follow-up:

The custom-rule loader blocker is resolved. `no-any-annotation.yml` now uses
block scalar Semgrep patterns for typed function signatures, and all custom
rule path includes/excludes are anchored for Semgrepignore v2 semantics.

Verification:

- `uvx --from semgrep semgrep scan --config .semgrep/rules/ --error src/aeat/ --metrics off`
- `just audit-security`

The project-regression rule lane now scans 891 tracked files with 7 custom
rules and reports 91 real findings. The production security lane still scans
891 tracked files with 323 stock rules and reports 11 findings. Both counts are
remaining remediation backlog, not configuration failures.

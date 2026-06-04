---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
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

The separate project-regression rule lane remains blocked before scanning:
`uvx --from semgrep semgrep scan --config .semgrep/rules/ --error src/aeat/`
reports invalid YAML in `.semgrep/rules/no-any-annotation.yml` at line 25.
That pre-existing rule-file defect is not resolved in this `.semgrepignore`
slice.

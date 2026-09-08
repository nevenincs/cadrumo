---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:10f111ea94ef914c5a0cd9944836fb05a9b2d960335cc0e0b0162bd537ab3a8f'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S188]]"
---

# `reachability-burndown` audit: `S188 code review`

## Scope

Independent review of `W05.P12.S188`: the complete governing plan, accepted Google service-account impersonation ADR, execution record, full impersonation implementation and focused tests, package export boundary, live CLI consumer, repository references, and focused diff. The initial selected focused suite was rerun independently: 27 passed and one live-gated test was deselected by the default marker policy. The corrected diff was re-reviewed; its focused Ruff invocation passes and repository search finds no surviving `describe_impersonation_target` reference under shipped source, documentation, or the ADR.

## Findings

### adr-contract-drift | high | The accepted ADR still requires the deleted public helper

The accepted Google service-account impersonation ADR explicitly listed `describe_impersonation_target(config)` as an implementation requirement and tied it to the operator's exact-SA-identity requirement. The implementation deleted that function and its export without initially amending the decision. The live CLI satisfies the user-visible requirement directly through `GoogleImpersonationConfig.target_principal`, so the deletion itself is technically coherent, but the initial S188 state could not be approved while the authoritative decision mandated the removed API.

Resolution: resolved on re-review. The ADR now names `GoogleImpersonationConfig.target_principal` as the canonical identity field, says operator surfaces read it directly, and explicitly retains no parallel accessor. The plan action and execution record include this decision amendment.

### dangling-cli-reference | medium | Shipped CLI documentation points at the removed function

The module docstring for the live Google credential-source CLI initially said `describe_impersonation_target` renders the exact service-account email. Repository search found no executable non-test caller, but that production documentation reference became invalid after deletion and falsely described how `show` works. The real implementation reads `selection.impersonation.target_principal` directly.

Resolution: resolved on re-review. The shipped CLI docstring now names the canonical `GoogleImpersonationConfig.target_principal` field and matches the executable `set` and `show` paths. Repository search finds no surviving removed-helper reference in shipped source, documentation, or the ADR.

### stale-cli-deferral | medium | The amended ADR still says the already-shipped CLI does not exist

The first amendment left later ADR sections describing the CLI, locale strings, persistence, factory dispatch, and live probe as deferred even though those surfaces had landed. That made the accepted decision internally inconsistent with both its revised Implementation section and inspected production code.

Resolution: resolved on final re-review. Considerations names the landed CLI's direct typed-config use; Constraints records the original deferral historically and names the landed `set|show` verbs; Rationale and Consequences recognize landed persistence, factory dispatch, locales, and live probe. The remaining optional ADC auto-remediation is accurately described as a future decision for the existing CLI, not as a missing CLI layer.

## Recommendations

No follow-up recommendation remains for S188. The public identity wrapper and wrapper-only assertions are removed, exact identity rendering has one canonical typed field consumed directly by the live CLI, credential resolution is unchanged, no executable consumer or stale reference remains, focused tests and Ruff pass, the exact reachability signal shrank from 344 to 343, and plan, ADR, execution record, and implementation agree.

Approved for S188 closure with no open findings.

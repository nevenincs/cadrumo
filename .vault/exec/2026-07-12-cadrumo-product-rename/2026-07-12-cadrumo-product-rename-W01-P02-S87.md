---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S87'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Remediate the authority-lock review and reopen contradicted downstream acceptance contracts

## Scope

- `.vault/adr/2026-07-12-cadrumo-cli-executable-adr.md`
- `.vault/plan/2026-07-12-cadrumo-product-rename-plan.md`
- `.vault/audit/2026-07-13-cadrumo-product-rename-authority-lock-audit.md`
- `.vault/exec/2026-07-12-cadrumo-product-rename/2026-07-12-cadrumo-product-rename-W01-P02-S87.md`

## Description

- Amend the superseding ADR to declare both operator overrides and the complete
  exact product, command, machine-identity, companion, and agency matrix.
- Refresh the ADR modified stamp and markdown hygiene through feature-scoped
  Vaultspec checks.
- Reopen every checked implementation or acceptance Step contradicted by direct
  live-file evidence under the binding `aeat` and CADRUMO contract.
- Preserve closed Steps whose lowercase `cadrumo` values are correct machine
  identifiers rather than human commands or display copy.
- Leave the independent audit at FAIL until a reviewer verifies this remediation.

## Outcome

The accepted ADR now explicitly overrides both the parent decision's title-case
display spelling and its human executable. It records CADRUMO as the display
name, `aeat` as the only human executable, the complete lowercase `cadrumo`
machine-identity family, `cadrumo-mcp`, `CADRUMO_`, both companion distribution
names, `cadrumo_data`, and AEAT as the Spanish authority.

The plan no longer claims completed behavior that the current tree does not
provide. The following 24 Steps are open again: `S25`, `S37` through `S40`,
`S43`, `S45`, `S48` through `S55`, `S57`, `S58`, `S62` through `S67`, and
`S78`. They cover the stale runtime CLI, installed-artifact probes, product copy
and generated integration surfaces, developer automation, locale authorities,
and the aggregate real-behavior gate.

## Notes

Read-only inspection preserved closed machine-identity Steps where the accepted
lowercase `cadrumo` contract is already true: distribution and extras metadata,
MCP resource and tool identifiers, client handshake, publication distribution
choices, `cadrumo-mcp` evaluation, release parsing, and compatibility absence.

The review audit is intentionally unchanged. Its findings are remediation input,
not self-resolving task state; independent re-review must decide whether the FAIL
verdict can be replaced.

## Remediation continuation: S86 independent review

### Description

- Reconcile the formal ADR graph with the ratified Stage-A accepted role and
  the single binding naming authority.
- Retire the reopened S90 and S93 exact-all-caps repair lanes without rewriting
  their historical execution evidence.
- Add a consumable sentence-prose name beside the unchanged identity-context
  display value and prove both through the real runtime authority.
- Correct the bounded S86 evidence claim and close S87, S90, and S93 only
  through the plan CLI.

### Outcome

The July 13 product-rename ADR remains accepted only for Stage-A release
surfaces and no longer participates in the supersession graph. The accepted CLI
ADR remains the single naming authority and continues to supersede the July 12
rename ADR. Its ratified tuple now has an explicit runtime projection:
`prose_name="Cadrumo"` for sentence prose and `display_name="CADRUMO"` for
identity contexts, with the `aeat`, `cadrumo-mcp`, lowercase machine-identity,
and AEAT authority boundaries unchanged.

S90 and S93 are closed as retired historical repair lanes, not re-executed
all-caps mandates. Their records retain the original outcomes and carry an
explicit retirement note. S87 closes only after the review findings are
remediated and focused evidence passes.

### Notes

The original Description and Outcome above remain historical evidence of the
earlier S87 execution. They are not current instructions and their exact-all-caps
premise is superseded by this continuation. Locale catalogues and the staged
marketplace README were not touched.

Six focused identity tests passed, and Ruff lint and format checks passed on
the identity authority and its test. Plan validation passed with the known
`PLAN022` ordering warning; ADR status retained only two unrelated pre-existing
quoting warnings; schema, frontmatter, and placeholder checks passed; and the
provider sync dry-run was unchanged. Feature-wide checks remain red on the
repository's pre-existing structural drift rather than an S87-owned failure.

## Bookkeeping correction from S94

Commit `03cd792be3` also cross-carried the S37 checkbox from open to closed in
the shared plan even though S37 was outside S87's declared scope and its owning
implementation had not yet committed. That closure was premature and was not
S87 evidence. The direct child commit `a4e56dcf83` subsequently delivered the
S37 implementation and refreshed execution evidence, and independent audit
`46363217dd` passed that installed-wheel behavior. S37 is therefore correctly
closed now, but its checkbox chronology begins in the S87 commit and is
disclosed rather than reassigned retroactively.

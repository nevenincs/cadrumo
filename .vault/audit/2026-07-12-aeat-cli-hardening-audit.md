---
tags:
  - '#audit'
  - '#aeat-cli-hardening'
date: '2026-07-12'
modified: '2026-07-12'
related:
  - "[[2026-05-08-aeat-cli-hardening-plan]]"
  - "[[2026-05-08-aeat-cli-hardening-adr]]"
  - "[[2026-05-08-aeat-cli-hardening-inventory-audit]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-06-12-residual-cli-hardening-triage-audit]]"
---

# `aeat-cli-hardening` audit: `legacy plan supersession reconciliation`

## Scope

Reconcile the May 2026 broad CLI hardening plan against the current entrypoint,
the accepted workflow redesign, and the residual-hardening closeout. Determine
whether its unchecked wave, issue, and action rows represent live product
work or a predecessor command architecture.

## Findings

### retired-command-architecture | low | residual rows belong to a superseded tracker

This plan describes a broad `setup` and `declaration` command tree, including
root `init`, `topic`, and generic compatibility-era surfaces. The accepted
workflow redesign replaces that shape with a restricted root containing
`config` and `app`, explicitly retiring historical roots rather than retaining
aliases. The current entrypoint implements that accepted routing with lazy
operational subtrees.

The plan's unchecked rows mix ten campaign headings with predecessor issue and
action ledger entries. They cannot be treated as independent open work because
many prescribe rejected operator verbs, while the surviving product outcomes
were delivered and verified in successor workflow-redesign and
operator-surface plans.

The later residual-hardening closeout records the successor plans as
implementation-complete, including their focused real-behaviour checks and
clean unchecked-row status. It separates historical execution-record curation
from active feature development. No current code or accepted ADR identifies an
unmet obligation that must be implemented under this plan's retired command
vocabulary.

## Recommendations

Mark the legacy rows resolved as superseded. Do not recreate the rejected root
verbs or restore `setup`/`declaration` as an operator command family. Track any
new CLI gap only in a current plan grounded in the accepted `config` and `app`
boundary.

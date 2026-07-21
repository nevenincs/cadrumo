---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s40-split-install'
date: '2026-07-13'
modified: '2026-07-17'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename-s40-split-install` audit: `Cadrumo product rename S40 split install audit`

## Scope

Independent formal review of commit
`21aa5a3304f988a8afc744150a3406f6b18fc53c` against the binding naming ADR,
`W03.P07.S40`, and campaign closure-honesty rules. The review covered root and
companion wheel names and globs, real installed `aeat` script identity and alias
absence, authority-owned `aeat_official`, the combined split-install sequence,
test and quality evidence, execution and plan truth, and path isolation.

## Findings

### checked-step-lacks-completed-split-install-acceptance | high | The required root-plus-two-companion sequence timed out but S40 is marked complete without a follow-up deferral

The execution record explicitly states that the combined real-wheel test timed
out before completion. That uncompleted lane is the distinctive S40 contract:
build the root, manuals, and official wheels; install all three into one fresh
environment; prove the slim advisory disappears; and run registry verification
cleanly through the installed `aeat` command. S35's byte ownership, namespace,
version, and cap checks do not execute that joined installed environment, and
the new isolated root-wheel test proves only the human-script boundary. Marking
S40 checked while calling the companion acceptance evidence incomplete hides a
required verification gap. The plan-closure rule requires an intentionally
deferred item to remain unchecked and name its follow-up campaign or blocker;
this record supplies neither a completed acceptance run nor a formal follow-up
reference.

## Recommendations

Verdict: **FAIL**. Reopen S40 until the combined real-wheel split-install lane
completes successfully under a justified bound, or formally defer it while
leaving the Step unchecked and naming the concrete follow-up owner.

The implemented naming and isolated identity proof are healthy. The lane uses
the `cadrumo` root wheel, both `cadrumo-data-*` companions and `cadrumo_data`
namespace, retains `aeat_official` only for authority corpus partitioning, and
invokes the sole human script as `aeat` or `aeat.exe`. The isolated real-wheel
test passed in a fresh pip environment and proved no `cadrumo` sibling alias.
Ruff lint, Ruff format, Ty, and scoped whitespace checks passed. The execution
record is commendably explicit about the timeout; the defect is the contradictory
plan closure. The three-path commit is otherwise isolated to its test, execution
record, and checkbox, with no production, documentation, or unrelated leakage.

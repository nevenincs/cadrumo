---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s58-regex-remediation'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename-s58-regex-remediation` audit: `Cadrumo product rename S58 regex remediation audit`

## Scope

Independent formal remediation review of commit
`6f3c60fb12a66f8d8d15131b28892d35d1fae7c8` against the binding naming ADR
and the prior S58 audit. The review covered closed former-product regex
families, preservation of the `aeat` human CLI and AEAT authority referent,
production-workflow evidence, sanitizer cross-carry, real-behaviour tests,
focused quality gates, execution truth, and exact commit isolation.

## Findings

### regex-families-remain-open-and-context-leaky | medium | Module subpaths evade the gate while valid CLI and authority uses after install verbs are rejected

The replacement classifier does not yet provide the closed contextual families
claimed by the execution record. A real former-package module invocation such
as `python -m aeat.cli check` returns no prohibited family because the
`python-module` expression accepts only whitespace or end-of-line after
`aeat`. Conversely, the distribution-install expression scans the entire
remainder of an install or add line for any standalone `aeat`, so valid
compound lines such as `uv add cadrumo && aeat --version` and
`pip install cadrumo && echo AEAT is the Spanish tax authority` are classified
as former distribution installation. These are direct violations of both
sides of the binding boundary: former Python package submodules must be
rejected, while the sole human CLI and external authority remain allowed by
referent and shell position.

## Recommendations

Verdict: **FAIL** until the module family covers the former import root and its
submodules and install/package expressions stop at shell argument boundaries so
subsequent allowed `aeat` CLI or AEAT authority uses are not consumed.

The remediation otherwise improves S58 materially. The execution Scope now
names the actual structural test and identifies production CI as unchanged
evidence. Static imports, common install forms, uv package selectors, former
distribution names, and former source paths have direct parametrized witnesses.
The committed production workflow still uses the exact two allowed `aeat`
registry commands and no `cadrumo` human executable. All twenty committed cases,
Ruff lint, Ruff format, Ty, and scoped whitespace checks passed. The commit
contains exactly the structural test and execution record; removal of stale
scaffold comments is accurately cross-carried as sanitizer output, with no
production CI, documentation, release, or unrelated path included.

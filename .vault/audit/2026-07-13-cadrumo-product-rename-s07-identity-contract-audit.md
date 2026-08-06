---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s07-identity-contract'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:203743980965acbf8b9ac2891c3055111c5c1128350861769891bdffcd772a1a'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename-s07-identity-contract` audit: `Cadrumo product rename S07 identity contract audit`

## Scope

Independent formal review of commit
`1e2f0ace0f45e9ba12904088a9528eaeeea09e59` against the binding naming ADR
and the `W01.P02.S07` contract. The review covered runtime immutability via
`setattr`, suppression and shortcut absence, contextual tuple values, former
alias rejection, real production-object tests, focused quality gates,
execution and plan truth, and commit path isolation.

## Findings

### tuple-test-pins-nonbinding-repository-value | high | The claimed binding-tuple proof expects a short repository name instead of the ADR's final owner-qualified repository

The binding ADR's final consolidated tuple names the repository as
`nevenincs/cadrumo`, but the test constructs its accepted external tuple with
`repository="cadrumo"`. That expectation makes the test pass against the
current runtime mismatch rather than detect it. The earlier ADR Constraints
use “repository identifier” for the short token, but the later status note is
the explicit final tuple and conflict-resolution authority. The test therefore
cannot support the record's claim that all six tests pin the binding contextual
identity tuple.

### alias-rejection-is-not-closed-over-the-identity-api | medium | The test forbids three guessed alias names but permits any other former-product export

The alias test checks that three specific names are absent and only requires
the four intended identity exports to be a subset of the broad core facade.
It does not require the defining identity module's `__all__` to equal its
closed intended surface or reject other former-product names. Adding, for
example, `AEAT_REPOSITORY`, `AEAT_DISTRIBUTION`, or another `Aeat*` identity
export to both module and facade would still satisfy every assertion. The
current production API is clean, but the durable test does not prove the
recorded absence-of-aliases contract.

## Recommendations

Verdict: **FAIL** until the tuple expectation follows the final binding
repository value (or the ADR and field explicitly distinguish the short
identifier) and the identity module's public surface is checked as a closed
contract rather than through a three-name blacklist.

The S07-specific immutability remediation is correct. Dynamic
`setattr(PRODUCT_IDENTITY, field_name, "Changed")` reaches the real frozen
`NamedTuple` instance, raises `AttributeError`, leaves the same object and value
intact, and requires no `type: ignore` or other suppression. The six tests use
real production objects and contain no fake, mock, stub, patch, monkeypatch,
skip, or xfail. Focused pytest, Ruff lint, Ruff format, Ty, and scoped whitespace
checks passed. The execution record accurately describes the mutation change
and later installed-package ownership. The commit is isolated to the S07 test,
its execution record, and its plan checkbox, with no implementation,
user-documentation, or unrelated-path leakage.

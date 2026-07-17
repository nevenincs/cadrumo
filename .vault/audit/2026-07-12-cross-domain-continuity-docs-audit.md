---
tags:
  - '#audit'
  - '#cross-domain-continuity-docs'
date: '2026-07-12'
modified: '2026-07-17'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity-docs` audit: `documentation-continuity-remediation`

## Scope

Review the S437 language-resolver and S443 annual-deadline documentation
corrections before closing their cross-domain continuity plan records. Confirm
that the docstrings describe the live Cadrumo implementation without changing
runtime behavior or reviving the retired product identity.

## Findings

### review-pass | low | No actionable findings

`W09.P43.S437` accurately describes the explicit registration from the
`cadrumo.application.user_profile` facade and no longer represents importing
the resolver as the registration mechanism. `W10.P50.S443` accurately records
that annual Modelo 100 windows use the tax-year key while their campaign close
date may fall in the next calendar year; the exact-match implementation does
not borrow a later window. Focused live-behaviour coverage passed for both the
facade import boundary and the 2020/2021 Modelo 100 following-year campaign
windows.

### docs-offline-propagation | medium | The developer docs builder still exports the retired offline setting

`docs/conf.py` now honours only `CADRUMO_DOCS_OFFLINE`, and the nitpicky test
uses that correct product-owned setting. However, strict and changed-page
builds in `dev/docs/build.py` still export `AEAT_DOCS_OFFLINE`. Those invocations
therefore no longer remove network-only intersphinx mappings, defeating the
documented offline-hermetic behaviour while the test remains green through its
separate environment construction. The new temporary
`CADRUMO_LOCAL_STORAGE_ROOT` is correct: the runtime derives its storage
substrate below that supplied root.

### docs-environment-migration-pass | low | All reviewed product controls now use the Cadrumo namespace

The current `docs/conf.py` consumer names and the `dev/docs/build.py`,
`dev/docs/serve.py`, and `test_docs_build.py` producers consistently use
`CADRUMO_DOCS_*`. Strict, changed-page, and serving paths now reach their
matching consumers. The Sphinx test supplies an isolated
`CADRUMO_LOCAL_STORAGE_ROOT`, which the runtime derives into its state
subdirectories; it does not alter authority-owned AEAT names or data.

### registry-id-nitpick-scope | low | The typed-ID ignore can also suppress a future real registry class

The current registry `*Id` declarations are PEP 695 aliases and no registry
class currently ends in `Id`; accepting both `cadrumo` and historical `aeat`
roots is therefore correct. However, the `\w+Id` portion of the
`docs/conf.py` expression also matches any future real class under the same
registry namespace whose name ends in `Id`. Because the rule applies to every
Python reference role, its unresolved class reference would be hidden rather
than red the docs gate. Limit the expression to the declared alias names, or
add a structural guard that rejects registry classes captured by the pattern.

### registry-id-nitpick-allowlist-pass | low | The narrowed typed-ID rule matches only the current aliases

The explicit alternation exactly covers the PEP 695 aliases declared in
`_ids.py` plus the core-owned `CasillaId` re-export. There are no current
registry classes ending in `Id`, and a future class with a new `*Id` name is
not in the allowlist, so its unresolved reference remains visible to the docs
gate. The `aeat` alternative only accepts historical reference text; no
supported `aeat` import path is introduced.

## Recommendations

Keep the focused documentation and deadline regressions in the pre-close gate.
Resolve the separate generated API cross-reference warnings before treating the
full documentation gate as green.

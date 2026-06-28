---
tags:
  - '#adr'
  - '#schema-hardening-coti'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-22-schema-hardening-coti-research]]'
---



# `schema-hardening-coti` adr: `quoted-fund-coti-warning-policy` | (**status:** `accepted`)

## Problem Statement

The broad optional/numeric typo-warning helper treats `coti` as an optional
token. In Modelo 100 2025, this hides near-role warnings between the new
`gp_fondos_coti` section and the general `gp_fondos` section.

Because the registry is derived from legal and regulatory sources, a source
section marker must not be erased by a global typo-warning rule without a
source-backed policy.

## Considerations

The official Modelo 100 2025 order creates a separate section for quoted funds
and quoted index SICAV operations. The committed registry mirrors this by
placing the quoted-fund rows under `gp_fondos_coti`.

Six current warning-exposed roles differ from their general-fund near roles by
the `coti` marker. Prior audits already recorded the section as a coherent
2025-only source family.

The same broad helper also handles unrelated tokens and numbers. This ADR only
decides the `coti` case.

## Constraints

No registry role may be renamed in this slice. Prior rename concerns, including
the related `irpf_perdida_fondos_coti_importe_obtenido` role, remain outside
scope.

The implementation must not normalize `gp_fondos_coti` and `gp_fondos` as the
same legal or source family.

Plan rows must be managed through `vaultspec-core vault plan`, not hand-edited.
Tests must exercise the real validator and committed registry.

## Implementation

Remove `coti` from the broad optional semantic-role token set.

Mark only the six current warning-exposed `gp_fondos_coti` roles as explicit
`intentional_singleton` entries with source-grounded reasons.

Add regression tests proving that unmarked `coti` roles are not axis siblings
and that committed reviewed rows are explicitly marked and warning-clean.

## Rationale

This follows the accepted broad-suppressor burn-down pattern: remove one broad
token only after source lookup confirms the token is legally or structurally
meaningful, then replace hidden suppression with explicit metadata for current
legitimate singletons.

## Consequences

The broad optional-token helper becomes narrower, but remains in place for
other unresolved tokens and all numeric stripping. The next optional/numeric
slices still need independent source lookup.

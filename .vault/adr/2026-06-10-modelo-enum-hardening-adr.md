---
tags:
  - '#adr'
  - '#modelo-enum-hardening'
date: '2026-06-10'
related:
  - '[[2026-06-10-modelo-enum-hardening-research]]'
---



# `modelo-enum-hardening` adr: `Modelo identifiers as a registry-bound core enum; regulatory values centralised` | (**status:** `accepted`)

## Problem Statement

Production code referenced AEAT modelo identifiers as bare three-digit string
literals across roughly 250 sites, and several regulatory leaf values (the IVA
general rate, LIRPF filing thresholds and deduction caps, an amortisation rate,
a maritime exemption fraction) were inlined as Python literals in feature
modules rather than read from a central authority. There was no closed
identifier type for modelos, so a typo or a retired code could not be caught at
a type boundary, and a regulatory value could drift silently when AEAT
publishes a new revision. This ADR records the decisions taken during the
in-session centralisation campaign and authorises the follow-on hardening
plan.

## Considerations

The `aeat-architecture-boundaries` rule mandates closed value sets as a
`StrEnum` in `core/`, and modelo ids are such a set. The `aeat-schema-central-config`
rule requires regulatory values to live in the central config or registry, not
as feature-module literals. The registry (`registry_modelo_codes()`) is the
runtime authority for which modelos are loadable, but it deliberately excludes
retired forms such as `M037` (suppressed by Orden HAC/1526/2024) which still
carry code-level support. Because `StrEnum` members compare and hash equal to
their string value, substituting a member for a bare string is
behaviour-preserving at any call site that accepts a `str`.

## Constraints

The enum must not break the domain invariant that `validate_modelo("037")`
raises and that no registry TOML exists for retired forms. Strict-pydantic
`str` fields accept `StrEnum` members (they are `str` instances), but a
`Literal["100"]` annotation pins the value, so a member substitution there
requires `Literal[Modelo.M100]`. No new domain behaviour is permitted: every
substitution must be behaviour-preserving or registry-grounded.

## Implementation

A `Modelo` `StrEnum` in `aeat.core` enumerates every modelo identifier the
codebase references. A registry-parity gate binds the registry-backed members
to `registry_modelo_codes()`; a documented `NON_REGISTRY_MODELOS` carve-out
(currently the retired `M037`) is excluded from that parity and pinned to its
`validate_modelo` `RegistrySnapshotError`. Production identifier sites reference
the enum, and an AST CI gate (`test_modelo_string_usage.py`) forbids bare code
strings in identifier positions while structurally excluding docstrings,
`Decimal()` percentages, and `Literal[...]` annotations. Regulatory leaf values
are centralised in `aeat.core.external_constants` with binding-provision
docstrings; dated rates prefer the registry-resolver pattern, a registry
parameter read with a leaf-constant fallback.

## Rationale

The enum gives modelo identifiers a single typed home, makes the
retired-versus-active distinction explicit rather than implicit, and lets a CI
gate enforce the convention so it cannot rot. Centralising regulatory values to
the registry or config with binding-provision grounding follows
`registry-calculation-legal-grounding` and stops silent drift when AEAT revises
a value.

## Consequences

Gains: typed modelo identifiers, an enforced no-bare-string convention, explicit
retired-code modelling, and a smaller surface for regulatory-value drift.
Honest costs: the sweep introduced an inconsistency between the member form
`Modelo.M###` and the string form `Modelo.M###.value`, which the follow-on plan
standardises; some `modelo: str` fields declared with `max_length=8` remain
string-typed pending per-field investigation; and a few false positives (a
digit-membership string, a regulatory article number that reads as a code)
require an allowlist entry in the gate. Pathways: a new modelo lands by adding a
registry directory plus an enum member, with the gate flagging an omission, and
the registry-resolver pattern is the template for further rate centralisation.

## Codification candidates


- **Rule slug:** `modelo-identifiers-use-core-enum`.
  **Rule:** Production code MUST reference AEAT modelo identifiers through the
  `aeat.core.Modelo` enum, never as bare three-digit string literals; the
  `test_modelo_string_usage.py` AST gate enforces this and any genuine
  exception is recorded in its allowlist with a reason.

---
name: binding-names-reserved-for-registry-input
trigger: always_on
---

# "binding" is reserved for the registry-data-input concept

## Rule

The term "binding" in module names, type names, and CLI surfaces is RESERVED for
the registry-data-input concept (`DataBindingDefinition` and its value carrier /
source resolvers). Account-scoping, parsing helpers, verification gates, and other
unrelated concepts MUST NOT be named "binding". When two concepts would share a
name, the non-registry-input one is renamed to what it actually does.

## Why

The discovery found "binding" was one strong core surrounded by overloaded
homonyms: two unrelated `_profile_binding.py` modules (an OAuth account-scoping
resolver vs the registry profile-fact resolver — a direct grep/refactor trap), a
`decimal_from_string` parser misfiled in a `_decimal_binding_value` module, and a
`legal_basis_binding` test concept that actually binds a tax RATE to its BOE
article (a verification gate). Reusing the word for unrelated ideas misleads every
reader and grep-driven refactor. Reserving it for the registry-data-input concept
keeps the vocabulary load-bearing. Recorded in ADR
`2026-06-14-bindings-interface-hardening-adr` (decision E); the homonyms were
renamed in wave W05 (`resolve_active_profile`/`_active_profile`, `_decimal_parsing`,
`test_legal_basis_rate_grounding`).

## How

- **Good:** the OAuth active-profile resolver lives in `_active_profile.py` as
  `resolve_active_profile`; the str→Decimal parser lives in `_decimal_parsing.py`;
  the rate-to-BOE gate is `test_legal_basis_rate_grounding.py`.
- **Good:** the registry profile-fact resolver KEEPS the "binding" name
  (`_profile_binding.py`, `ProfileSourcedBindingResult`) — "binding" is correct
  there.
- **Bad:** naming a new module `_*_binding.py` for an OAuth/session/identity
  scoping concern, a generic parser, or a verification gate.
- **Bad:** introducing an English/Spanish alias module over a binding type for
  "compatibility" (also barred by `aeat-architecture-boundaries` / no-shims).

## Source

ADR `2026-06-14-bindings-interface-hardening-adr` (decision E), research
`2026-06-14-bindings-interface-hardening-research` (cluster E). Companion to
`aeat-architecture-boundaries` (no shims/alias layers) and
`aeat-spanish-stem-naming` (domain naming discipline).

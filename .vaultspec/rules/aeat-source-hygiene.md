# AEAT source hygiene and reserved vocabulary

Keep source code free of project-management metadata. Do not encode waves,
phases, agent names, issue workflow, handover state, temporary migration labels,
or process history in production identifiers, comments, fixtures, schemas, or
public APIs. Use domain names that stay true after the current plan changes.

Do not land design-only implementation shells. Ship working behavior, executable
validation, and useful tests together.

Add code comments sparingly, and only for *why*. Never describe changes through
comments.

## "binding" is reserved

The term **binding** in module names, type names, and CLI surfaces is RESERVED
for the registry-data-input concept (`DataBindingDefinition`, its value carrier,
and its source resolvers). Account scoping, parsing helpers, verification gates,
and other unrelated concepts MUST NOT be named "binding"; when two concepts would
share the name, the non-registry-input one is renamed to what it actually does.

Reusing the word misleads every reader and every grep-driven refactor — two
unrelated `_profile_binding.py` modules once shipped side by side, one an OAuth
account-scoping resolver and one the registry profile-fact resolver.

## How

- **Good:** the OAuth resolver is `_active_profile.py`; the string-to-Decimal
  parser is `_decimal_parsing.py`; the rate-to-BOE gate is
  `test_legal_basis_rate_grounding.py`. The registry profile-fact resolver keeps
  the binding name — it is correct there.
- **Bad:** naming a new module `_*_binding.py` for a session, identity, parsing,
  or verification concern.

Source: ADR `2026-06-14-bindings-interface-hardening-adr` (decision E).
Companions: `aeat-spanish-stem-naming`, `aeat-architecture-boundaries`.

---
tags:
  - '#adr'
  - '#locale-scaffold-fstring'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-locale-scaffold-fstring-research]]"
---

# `locale-scaffold-fstring` adr: explicit f-string key expansion registry | (**status:** `accepted`)

## Problem Statement

The locale scaffold tool cannot enumerate concrete locale keys built via f-string
interpolation (`tr(f"wizard.setup.taxpayer-type.legal-entity-form.choices.{member.value.replace('_', '-')}.label")`).
It emits a namespace marker (`wizard.setup.*`) that the parity check validates weakly
(at least one entry exists under the prefix). When a new enum value is added to a
domain StrEnum — e.g. `LegalEntityForm.SAL` or `LegalEntityForm.SLL` in #208 — the
scaffold cannot insert the required locale entries, and `locales set` fails with "key
not found, run scaffold first". The only escape has been a structural-repair-exception
manual hand-edit, which recurred three times in the hu-locale campaign.

## Considerations

Two approaches were evaluated:

1. **AST-level enum resolution**: walk the AST, detect the enum type iterated in each
   comprehension, import it, enumerate its values. Rejected: creates a hard import
   dependency between the locale scanner and domain modules; fragile to circular imports
   and import errors during scan; cannot handle `replace('_', '-')` transforms cleanly.

2. **Explicit registration surface**: a dedicated `_fstring_registry.py` module in
   `src/aeat/locales/` declares a list of `FStringKeyRegistration` entries. Each entry
   carries the key template (a callable `(value) -> str`), the enumerable source
   (any `Iterable[str]`), and a human-readable description. The scaffold calls
   `get_registered_keys()` to expand all registrations into concrete keys before
   building the locale YAML.

Chosen: explicit registration surface.

## Constraints

- Edit only `src/aeat/locales/` for implementation. Do not touch production application
  code that uses `tr()`.
- No shims, no compatibility paths, no deprecation markers.
- The registration module may import from `src/aeat/` domain and core modules to
  resolve enum values — these are real imports at scaffold time, not AST introspection.

## Implementation

A `FStringKeyRegistration` dataclass in `src/aeat/locales/_fstring_registry.py` holds:
- `description: str` — human-readable name, for error messages only.
- `key_factory: Callable[[str], str]` — maps one iterable value to a dotted locale key.
- `values: Iterable[str]` — the bounded value set (enum `.value` sequences, frozensets).

`get_registered_keys() -> set[str]` iterates every registration and expands to concrete
keys.

`LocaleManager.get_codebase_keys()` in `manager.py` calls `get_registered_keys()` and
merges the result into the concrete key set. The scaffold then writes these keys as
placeholder entries for any locale that lacks them, exactly as it does for literal-key
sites.

The existing namespace-marker path (`get_codebase_namespaces()`) is retained unchanged.
The two paths are complementary: the registry produces concrete keys; the namespace
markers document the remaining open-ended f-string patterns (section suffix + question
ID, profile key, registry binding row_field) that cannot be statically expanded.

## Rationale

The explicit registration surface makes the contract visible: adding a new enum value
without updating the registration makes the gap observable immediately at scaffold time
(the key is absent from locale files) rather than at runtime (a missing translation
falls through to the key string). It also decouples the scanner from domain internals
and keeps the locale module self-contained.

The `_fstring_registry.py` module is the canonical location for all bounded-f-string
locale key declarations. Any future f-string `tr()` call with a known enumeration must
be registered here.

## Consequences

- Scaffold now produces concrete placeholder entries for every registered enum key.
  Adding a new enum value is no longer a structural-repair-exception event: scaffold
  inserts the placeholder and the operator translates it.
- A new test verifies that the registration covers every current enum member for each
  registered pattern. When an enum value is added without updating the registration,
  this test fails rather than silently missing locale entries.
- The existing namespace-marker parity check remains as the safety net for unregistered
  or open-ended f-string patterns.
- The three open-ended patterns (`wizard.setup.{suffix}.{qid}.prompt`,
  `profile.keys.{profile_key}`, `sheets.detalle.headers.{row_field}`) remain
  namespace-marker only; they require runtime context to enumerate and use `default=`
  fallbacks where appropriate.

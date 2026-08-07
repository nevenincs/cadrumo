# Modelo identifiers use the core Modelo enum

Production code MUST reference AEAT modelo identifiers through the
`cadrumo.core.Modelo` StrEnum, never as bare three-digit string literals. An AST
gate enforces this; a genuine non-identifier occurrence (a regulatory article
number, a digit-set membership test, a CLI command-name token) is recorded in
that gate's allowlist with a stated reason.

Use the **bare member** (`Modelo.M303`) in comparison, membership, and dict-key
positions; reserve **`.value`** for plain-`str` contracts (pydantic field values,
call arguments, parameter and CLI-option defaults, returns).

A modelo that is code-referenced but has no registry definition (a retired form)
is added to the enum and listed in `NON_REGISTRY_MODELOS`, which the
registry-parity gate excludes.

## Why

Bare literals meant a typo or a retired code could not be caught at a type
boundary. A `StrEnum` member compares, hashes, `str()`s and JSON-serialises
identically to its value, so the substitution is behaviour-preserving, and the
member-versus-`.value` split keeps stored and passed types clean across pydantic
round-trips. Registry-backed members are bound to the registry code set by a
parity gate, so a new registry modelo without a member fails loudly.

## How

- **Good:** `if unit.modelo != Modelo.M303:` and `{Modelo.M100: ...}` use bare
  members; `modelo=Modelo.M720.value` for a `str`-typed field, and
  `Literal[Modelo.M100]` for a pinned field.
- **Bad:** `if unit.modelo != "303":` or `{"347": ...}`; inventing a member for a
  code in neither the registry-bound set nor `NON_REGISTRY_MODELOS`; or silencing
  the gate with an allowlist entry for a real identifier.

Enforced by `src/cadrumo/core/tests/test_modelo_string_usage.py` and
`test_modelo.py`. Source: ADR `2026-06-10-modelo-enum-hardening-adr`.

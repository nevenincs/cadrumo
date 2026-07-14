---
name: modelo-identifiers-use-core-enum
---

# Modelo identifiers use the core Modelo enum

## Rule

Production code MUST reference AEAT modelo identifiers through the `cadrumo.core.Modelo`
StrEnum, never as bare three-digit string literals. The
`src/cadrumo/core/tests/test_modelo_string_usage.py` AST gate enforces this; a genuine
non-identifier occurrence (a regulatory article number, a digit-set membership test, a
CLI command-name token) is recorded in that gate's allowlist with a stated reason. Use
the bare member (`Modelo.M303`) in comparison, membership, and dict-key positions;
reserve `.value` (`Modelo.M303.value`) for plain-`str` contracts (pydantic field values,
call arguments, parameter/CLI-option defaults, returns). A modelo that is a
code-referenced identifier but has no registry definition (a retired form) is added to
the enum and listed in `cadrumo.core.NON_REGISTRY_MODELOS`, which the registry-parity
gate excludes.

## Why

`2026-06-10-modelo-enum-hardening-adr` and its research found ~250 sites using bare
three-digit literals, so a typo or retired code could not be caught at a type boundary.
One core `StrEnum` gives them a single typed home and makes the retired-vs-active
distinction explicit (suppressed M037 has no registry TOML); a `StrEnum` member
compares/hashes/`str()`s/JSON-serialises identically to its value, so the substitution
is behaviour-preserving and the member-vs-`.value` split keeps stored/passed types clean
across pydantic round-trips. Registry-backed members are bound to
`registry_modelo_codes()` by a parity gate, so a new registry modelo without a member
fails loudly.

## How

- **Good:** `if work_unit.modelo != Modelo.M303:` and `{Modelo.M100: ..., Modelo.M130:
  ...}` use bare members (hash as their value); `modelo=Modelo.M720.value` for a
  `str`-typed field and `modelo: Literal[Modelo.M100] = Modelo.M100` for a pinned field
  (`.value` for the plain-`str` contract, member inside `Literal[...]`). A retired
  identifier (`M037`) is an enum member listed in `NON_REGISTRY_MODELOS` and pinned by a
  test to raise from `validate_modelo`.
- **Bad:** `if work_unit.modelo != "303":` or `{"347": ..., "349": ...}` (AST gate
  fails); inventing a `Modelo.M<code>` for a code in neither the registry-bound set nor
  `NON_REGISTRY_MODELOS` (raises `AttributeError`); or silencing the gate with an
  allowlist entry for a real identifier instead of converting it — the allowlist is only
  for genuine non-modelo lookalikes, each with a stated reason.

## Source

ADR `2026-06-10-modelo-enum-hardening-adr` and research. Enforced by
`test_modelo_string_usage.py` (AST gate) and `test_modelo.py` (registry-parity plus
non-registry carve-out).

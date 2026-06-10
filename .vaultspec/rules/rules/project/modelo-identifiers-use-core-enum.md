---
name: modelo-identifiers-use-core-enum
---

# Modelo identifiers use the core Modelo enum

## Rule

Production code MUST reference AEAT modelo identifiers through the
`aeat.core.Modelo` StrEnum, never as bare three-digit string literals. The
`src/aeat/core/tests/test_modelo_string_usage.py` AST gate enforces this; a
genuine non-identifier occurrence (a regulatory article number, a digit-set
membership test, a CLI command-name token) is recorded in that gate's allowlist
with a stated reason. Use the bare member (`Modelo.M303`) in comparison,
membership, and dict-key positions; reserve `.value` (`Modelo.M303.value`) for
plain-`str` contracts (pydantic field values, call arguments, parameter /
CLI-option defaults, returns). A modelo that exists as a code-referenced
identifier but has no registry definition (a retired form) is added to the enum
and listed in `aeat.core.NON_REGISTRY_MODELOS`, which the registry-parity gate
excludes.

## Why

The `2026-06-10-modelo-enum-hardening-adr` decision and its research found
roughly 250 sites referencing modelo ids as bare three-digit string literals,
so a typo or a retired code could not be caught at a type boundary and the
closed set was scattered. Naming them through one core `StrEnum` gives the
identifiers a single typed home, makes the retired-versus-active distinction
explicit (the suppressed M037 censo simplificada is a code-referenced identifier
with no registry TOML), and lets the AST gate keep the convention from rotting.
Because a `StrEnum` member compares, hashes, `str()`-formats, and JSON-serialises
identically to its value, the substitution is behaviour-preserving; the
member-versus-`.value` split keeps stored and passed types clean across pydantic
round-trips. The enum's registry-backed members are bound to
`registry_modelo_codes()` by a parity gate, so a new registry modelo without a
matching enum member fails loudly.

## How

- **Good:** `if work_unit.modelo != Modelo.M303: ...` — comparison uses the bare
  member.
- **Good:** `_MODELO_APPLICABILITY_RULES = {Modelo.M100: ..., Modelo.M130: ...}`
  — dict keys are members (they hash as their string value).
- **Good:** `modelo=Modelo.M720.value` for a `str`-typed field value, and
  `modelo: Literal[Modelo.M100] = Modelo.M100` for a pinned field — `.value` for
  the plain-`str` contract, the member inside `Literal[...]`.
- **Good:** a retired identifier (`M037`) is an enum member listed in
  `NON_REGISTRY_MODELOS` and pinned by a test to raise from `validate_modelo`.
- **Bad:** `if work_unit.modelo != "303":` or `{"347": ..., "349": ...}` — bare
  string literals; the AST gate fails until they reference `Modelo`.
- **Bad:** inventing a `Modelo.M<code>` member for a code that is neither in the
  registry-bound set nor declared in `NON_REGISTRY_MODELOS` (e.g. a `Modelo.M037`
  reference before the carve-out existed) — it raises `AttributeError`.
- **Bad:** silencing the gate by adding an allowlist entry for a real identifier
  occurrence instead of converting it; the allowlist is only for genuine
  non-modelo lookalikes, each with a stated reason.

## Source

ADR `2026-06-10-modelo-enum-hardening-adr`; research
`2026-06-10-modelo-enum-hardening-research`. Enforced by
`src/aeat/core/tests/test_modelo_string_usage.py` (AST gate) and
`src/aeat/core/tests/test_modelo.py` (registry-parity plus non-registry
carve-out). Promoted per the `vaultspec-codify` discipline.

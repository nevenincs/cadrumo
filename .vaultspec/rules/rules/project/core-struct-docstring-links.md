---
name: core-struct-docstring-links
---

# Core-struct docstring cross-links

A module that imports a canonical core struct MUST cross-link that struct in at
least one docstring (the module docstring or any public symbol's docstring),
using a Sphinx role such as `:class:`ModeloRevision``.

## Why

The API documentation is only navigable if its docstrings form a graph that
steers a reader toward the canonical spine. A module that depends on a core
struct but never names it in a cross-reference is a dead end: a newcomer has no
thread to follow back to the authoritative definition. A baseline scan found
only 53% of module docstrings and 26% of documented public symbols carried any
cross-reference at all. The gate `test_docstring_core_struct_links.py` makes the
contract enforceable: it self-verifies the anchor set, recomputes the violation
worklist from the AST on every run, and fails with a precise
`module -> :class:`Struct`` enumeration. It is hard-cut with no stored baseline,
so coverage can only ratchet up to green; it carries the `docs` marker so it
runs in the documentation CI lane.

## How

- When a module imports a core-struct anchor (the spine: `ValidatedRegistryAuthority`,
  `RegistrySnapshot`, `ModeloDefinition`, `ModeloRevision`, `CasillaObservation`,
  `CalculationRevision`, `OutputSchema`, `SchemaEnvelope`, `SecureObjectRepository`),
  add a `:class:` (or `:meth:`/`:obj:`) cross-link in the docstring where the
  struct is genuinely used (a return type, a parameter, the operation performed).
  Write a true sentence describing the real relationship; do not fabricate.
- Upgrade existing plain-backtick mentions (``ModeloRevision``) to roles
  (`:class:`ModeloRevision``). The anchors are documented public symbols, so a
  bare `:class:`Name`` resolves through the build's missing-reference resolver;
  do not add a dotted path.
- Extend the `CORE_STRUCTS` mapping in the gate to bring more of the spine under
  enforcement. Each entry is pinned to a single canonical class definition, so
  the set cannot silently rot.
- Run the gate: `uv run --no-sync pytest -m docs src/aeat/tests/test_docstring_core_struct_links.py`.
  It must stay green. Do not satisfy it by sprinkling unrelated roles; the link
  must be semantically truthful and the `-n -W` build must still resolve it.

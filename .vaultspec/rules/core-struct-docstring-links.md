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
thread to follow back to the authoritative definition. Cross-reference coverage
started well below half of module docstrings and documented public symbols. The
gate `test_docstring_core_struct_links.py` makes the
contract enforceable: it self-verifies the anchor set, recomputes the violation
worklist from the AST on every run, and fails with a precise
`module -> :class:`Struct`` enumeration. It is hard-cut with no stored baseline,
so coverage can only ratchet up to green; it carries the `docs` marker so it
runs in the documentation CI lane.

## How

- When a module imports a core-struct anchor (the spine is the `CORE_STRUCTS`
  mapping in the gate, the authoritative list; it spans the registry
  authority and snapshots, the JSON contract envelopes, the secure storage
  primitives, the AEAT portal registry, the financial-input aggregates and their
  repositories, and the profile/deadline/filing records),
  add a `:class:` (or `:meth:`/`:obj:`) cross-link in the docstring where the
  struct is genuinely used (a return type, a parameter, the operation performed).
  Write a true sentence describing the real relationship. Do not fabricate.
- Upgrade existing plain-backtick mentions (``ModeloRevision``) to roles
  (`:class:`ModeloRevision``). The anchors are documented public symbols, so a
  bare `:class:`Name`` resolves through the build's missing-reference resolver.
  Do not add a dotted path.
- Extend the `CORE_STRUCTS` mapping in the gate to bring more of the spine under
  enforcement. Each entry is pinned to a single canonical class definition, so
  the set cannot silently rot.
- Choose anchors for navigability value, not raw import in-degree. An anchor is a
  type a newcomer must navigate to in order to work in an area: a central data or
  record aggregate, a domain authority or repository that owns access, or the
  primary closed-value enum that defines a domain. Do NOT anchor ubiquitous
  infrastructure learned once and never re-navigated (a base error such as
  `AeatError`, the `Settings` config aggregate), error subclasses (they are
  handled, not navigated to), secondary sub-dimension enums when the primary one
  is already anchored, or low-reach types only a couple of modules import.
  Linking those everywhere is noise that degrades the graph rather than enriching
  it. The 28-anchor set was curated on this basis from import in-degree plus a
  per-domain discovery pass; the high in-degree tail (errors, config, secondary
  enums) was deliberately excluded.
- Run the gate: `uv run --no-sync pytest -m docs src/aeat/tests/test_docstring_core_struct_links.py`.
  It MUST stay green. Do not satisfy it by sprinkling unrelated roles; the link
  MUST be semantically truthful and the `-n -W` build MUST still resolve it.

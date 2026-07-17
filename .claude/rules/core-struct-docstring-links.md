---
name: core-struct-docstring-links
trigger: always_on
---

# Core-struct docstring cross-links

A module that imports a canonical core struct MUST cross-link that struct in at
least one docstring (module or any public symbol), using a Sphinx role such as
`:class:`ModeloRevision``.

## Why

Docstrings must form a graph steering readers to the canonical spine; a module
depending on a core struct but never cross-referencing it is a dead end. The gate
`test_docstring_core_struct_links.py` self-verifies the anchor set, recomputes the AST
violation worklist every run, and fails with a precise `module -> :class:`Struct``
enumeration. It is hard-cut with no stored baseline (coverage only ratchets up) and
carries the `docs` marker for the documentation CI lane.

## How

- When a module imports a core-struct anchor (the spine is the `CORE_STRUCTS` mapping
  in the gate — the authoritative list, spanning the registry authority and snapshots,
  the JSON contract envelopes, the secure storage primitives, the AEAT portal registry,
  the financial-input aggregates and their repositories, and the profile/deadline/filing
  records), add a `:class:` (or `:meth:`/`:obj:`) cross-link where the struct is
  genuinely used. Write a true sentence; do not fabricate.
- Upgrade plain-backtick mentions to roles (``ModeloRevision`` → `:class:`ModeloRevision``);
  anchors are documented public symbols, so a bare `:class:`Name`` resolves through the
  build's missing-reference resolver — do not add a dotted path.
- Extend `CORE_STRUCTS` to bring more of the spine under enforcement; each entry is
  pinned to a single canonical class definition so the set cannot silently rot.
- Choose anchors for navigability, not raw import in-degree. An anchor is a type a
  newcomer must navigate to to work in an area: a central data/record aggregate, a
  domain authority/repository that owns access, or the primary closed-value enum
  defining a domain. Do NOT anchor ubiquitous infrastructure learned once and never
  re-navigated (a base error such as `CadrumoError`, the `Settings` config aggregate),
  error subclasses (handled, not navigated to), secondary sub-dimension enums when the
  primary is already anchored, or low-reach types only a couple of modules import. The
  28-anchor set was curated on this basis (import in-degree plus a per-domain discovery
  pass), the high in-degree tail (errors, config, secondary enums) deliberately excluded.
- Run `uv run --no-sync pytest -m docs
  src/cadrumo/tests/test_docstring_core_struct_links.py`; it MUST stay green. Do not
  satisfy it with unrelated roles — the link MUST be semantically truthful and the
  `-n -W` build MUST still resolve it.

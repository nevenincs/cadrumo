# Core-struct docstring cross-links

A module that imports a canonical core struct MUST cross-link that struct in at
least one docstring (module or any public symbol), using a Sphinx role such as
`:class:`ModeloRevision``.

Docstrings must form a graph steering readers to the canonical spine; a module
depending on a core struct but never cross-referencing it is a dead end. The
gate self-verifies its anchor set, recomputes the AST violation worklist every
run, and fails with a precise `module -> :class:`Struct`` enumeration. It is
hard-cut with no stored baseline — coverage only ratchets up — and carries the
`docs` marker.

## How

- The spine is the `CORE_STRUCTS` mapping in
  `src/cadrumo/tests/test_docstring_core_struct_links.py` — the authoritative
  list. Add a cross-link where the struct is genuinely used, and write a true
  sentence; do not fabricate.
- Upgrade plain-backtick mentions to roles. Anchors are documented public
  symbols, so a bare `:class:`Name`` resolves through the build's
  missing-reference resolver — do not add a dotted path.
- **Choose anchors for navigability, not import in-degree.** An anchor is a type
  a newcomer must navigate to: a central data or record aggregate, a domain
  authority or repository that owns access, or the primary closed-value enum
  defining a domain. Do NOT anchor ubiquitous infrastructure learned once and
  never re-navigated (a base error class, the config aggregate), error subclasses,
  secondary sub-dimension enums when the primary is already anchored, or
  low-reach types only a couple of modules import.
- Run `uv run --no-sync pytest -m docs
  src/cadrumo/tests/test_docstring_core_struct_links.py`; it MUST stay green. Do
  not satisfy it with unrelated roles — the link MUST be semantically truthful
  and the `-n -W` build MUST still resolve it.

"""Locale-catalogue maintenance facade for shared YAML translations.

Contributor tooling: it maintains the four runtime catalogues that ship under
``src/cadrumo/locales/`` but is not itself part of the distribution. The
catalogue YAML (``en``, ``es``, ``ca``, ``hu``) and the allowlist JSON stay in
the package because the renderer loads them at runtime; only the maintenance
code lives here.

The package keeps those catalogues in sync with codebase translation keys and
enforces inter-locale parity. The developer CLI (``python -m dev.locales``)
owns edits through ``set``, ``remove``, ``scaffold``, ``scaffold --check``, and
``audit`` commands; the catalogue YAML is CLI-maintained, not hand-edited.

Major declarations:

* :class:`LocaleManager` loads, scaffolds, checks, and audits the runtime locale
  catalogues.
* :class:`StrictUniqueKeyLoader` rejects duplicate YAML keys at parse time.
* :func:`catalogue_write_guard` serialises catalogue edits and refuses a write
  that would discard a change landed by another writer.
* :data:`LocaleNode` documents the recursive locale-tree shape consumers walk.

Every symbol this package defines is imported from the module that defines it;
this initialiser is an inert namespace marker and forwards nothing.
"""

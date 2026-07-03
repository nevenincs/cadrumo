"""``aeat-data``: the corpus source-binary companion for the ``aeat`` distribution.

The slim ``aeat`` runtime wheel excludes the corpus source binaries
(``_data/corpus/**/*.{pdf,xls,xlsx}``) that make up 94% of its weight. This
companion distribution ships exactly those binaries under a mirrored
``aeat_data/_data/corpus`` tree, so ``aeat.core.resources.resolve_corpus_binary``
resolves them at runtime when the ``aeat-cli[corpus-sources]`` extra is installed.

This package carries no importable logic. It exists only to root the bundled
``_data`` resource tree for ``importlib.resources.files("aeat_data")``, which the
runtime corpus-locator seam joins with ``_data`` to read a binary.
"""

from __future__ import annotations

__all__: list[str] = []

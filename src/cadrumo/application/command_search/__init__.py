"""Semantic-ish discovery search over the Cadrumo command surface.

The MCP console advertises only an orientation core by default; the
long-tail verb universe is reached through the ``search`` meta-tool. That search must bridge the operator's
natural vocabulary to the command's own tokens, which a naive token-substring
scorer cannot (it misses ``declare quarterly VAT`` -> ``modelo.work.calculate``
across the Spanish/English and concept/verb gaps). This package builds a small
FTS5 lexical index with Spanish stemming and diacritics folding over the
command corpus (command key, tool name, description, per-verb help, toolset) and
ranks by BM25, degrading to a pure-Python token scorer when SQLite FTS5 is
unavailable - the same lexical-first, degrade-cleanly posture as the corpus
grounding search.
"""

from __future__ import annotations

from ._index import CommandDoc, CommandHit, CommandIndex, build_command_index

__all__ = [
    "CommandDoc",
    "CommandHit",
    "CommandIndex",
    "build_command_index",
]

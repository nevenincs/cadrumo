"""Lexical discovery search over the Cadrumo command surface.

External command browsers may advertise only an orientation core by default; the
long-tail verb universe is reached through the ``search`` meta-tool. That
search must bridge the operator's natural vocabulary to the command's own
tokens, which a naive token-substring scorer cannot. This package builds a
small FTS5 lexical index with Spanish stemming and diacritics folding over the
command corpus (command key, tool name, description, per-verb help, toolset)
and ranks by per-column BM25, degrading to a pure-Python token scorer when
SQLite FTS5 is unavailable - the same lexical-only, degrade-cleanly posture as
the corpus grounding search. Curated outcome aliases carry the concept-phrased
queries the stemmer cannot bridge on its own.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()

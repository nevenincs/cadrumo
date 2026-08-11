"""Canonical rendering for extracted corpus sidecar units."""

from __future__ import annotations

from collections.abc import Iterable


def render_corpus_sidecar_text(units: Iterable[tuple[str | None, str]]) -> str:
    """Render titled text units exactly as the committed Markdown sidecar."""
    return "\n\n".join(f"# {title}\n\n{text}" if title else text for title, text in units)


__all__ = ["render_corpus_sidecar_text"]

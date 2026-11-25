"""Heading keys and unique block slugs shared by the form layout generator."""

from __future__ import annotations

from .column_vocabulary import SHARED_COLUMN_HEADING_KEY_PREFIX, SHARED_COLUMN_KEYS


def form_heading_key(modelo_id: str, *nodes: str) -> str:
    """Return a per-modelo heading key.

    Section and row keys are named by the official heading's own words rather
    than by position, so the same heading shares one translation across pages
    and editions, and a key never changes meaning when an edition reorders.
    """
    return ".".join(("modelo", "schema", modelo_id, "form", *nodes, "heading"))


def unnamed_section_form_heading_key(modelo_id: str, page_id: str, section_id: str) -> str:
    """Return the heading key of a section the design leaves unnamed, scoped to its page.

    An unnamed section holds what a page places outside its named parts, so it
    is a different part on every page; the page scope gives each one its own
    key, and the same page keeps that key in every edition.
    """
    return form_heading_key(modelo_id, "page", page_id, "section", section_id)


def column_form_heading_key(modelo_id: str, key: str) -> str:
    """Return the heading key of a column: the shared one for a shared column, else a per-modelo key."""
    if key in SHARED_COLUMN_KEYS:
        return f"{SHARED_COLUMN_HEADING_KEY_PREFIX}.{key}"
    return form_heading_key(modelo_id, "column", key)


def unique(base: str, used: set[str]) -> str:
    """Return a key unique among those used by appending a counter to the base."""
    candidate, counter = base, 2
    while candidate in used:
        candidate = f"{base}-{counter}"
        counter += 1
    used.add(candidate)
    return candidate

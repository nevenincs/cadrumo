"""Schema-independent integrity gate: every casilla legal_ref resolves to a
legal-catalogue entry.

This gate parses the registry TOML tree DIRECTLY (it does NOT instantiate
``ModeloRevision`` or load the binding/aggregation schema), so it keeps verifying
the legal-grounding data's referential integrity even while other parts of the
registry schema are mid-refactor and the full ``load_registry_tree`` path is
temporarily unable to load. It is the durable backstop for the legal-grounding
centralization campaign (audit ``2026-06-14-legal-grounding-centralization-audit``,
~6345 M100 casillas re-grounded): a casilla whose ``legal_refs`` cite a provision
absent from the legal catalogue is an ungrounded dangling reference, which this gate
fails loudly regardless of the rest of the registry's load state.
"""

from __future__ import annotations

import re

import pytest

from .....core.resources import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# A legal_ref is a provision key in one of these source families; bare-string axes
# (semantic roles, casilla numbers) never start with these prefixes.
_LEGAL_REF_PREFIXES = ("ley-", "rd-", "rdl-", "orden-", "dt-", "da-", "directiva-")

_LEGAL_ENTRY_RE = re.compile(r'^\[legal\."([^"]+)"\]', re.M)
_LEGAL_REFS_RE = re.compile(r"^legal_refs = (\[.*?\])", re.M)
_QUOTED_RE = re.compile(r'"([^"]+)"')


def _catalogue_entries() -> set[str]:
    legal_dir = bundled_path("registry", "aeat", "legal")
    entries: set[str] = set()
    for toml in legal_dir.glob("*.toml"):
        text = toml.read_text(encoding="utf-8", errors="replace")
        entries.update(_LEGAL_ENTRY_RE.findall(text))
    return entries


def _all_casilla_files():
    modelos_root = bundled_path("registry", "aeat", "modelos")
    return sorted(modelos_root.glob("*/revisions/*/casillas/*.toml"))


def test_legal_catalogue_is_non_empty() -> None:
    entries = _catalogue_entries()
    assert len(entries) > 100, f"legal catalogue suspiciously small: {len(entries)} entries"


def test_every_casilla_legal_ref_resolves_to_a_catalogue_entry() -> None:
    """No casilla may cite a legal provision absent from the legal catalogue."""
    entries = _catalogue_entries()
    dangling: dict[str, list[str]] = {}
    for f in _all_casilla_files():
        text = f.read_text(encoding="utf-8", errors="replace")
        refs: set[str] = set()
        for block in _LEGAL_REFS_RE.findall(text):
            for ref in _QUOTED_RE.findall(block):
                if ref.startswith(_LEGAL_REF_PREFIXES):
                    refs.add(ref)
        missing = sorted(r for r in refs if r not in entries)
        if missing:
            dangling[str(f.relative_to(bundled_path("registry", "aeat", "modelos")))] = missing
    assert not dangling, (
        "casilla legal_refs cite provisions absent from the legal catalogue "
        f"(dangling references): {dangling}"
    )

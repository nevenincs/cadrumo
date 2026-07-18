"""Catalogue-vs-source drift gate for the localized documentation.

The completeness gate (:mod:`dev.docs.tests.test_docs_localization`) reads each
committed ``.po`` and confirms its own entries are translated and non-fuzzy - but
it is blind to a source page that was edited or regenerated without a catalogue
re-sync. When that happens the catalogue stays internally complete (so the
completeness gate stays green) while it silently no longer describes the current
source: new source strings are absent from the catalogue, and removed source
strings linger as stale entries.

This gate closes that blind spot. It runs a fresh gettext POT extraction of the
current source into a temporary directory (never mutating the committed
``docs/locales/pot``) and asserts, per user-scope page and per target language,
that the freshly-extracted msgid set equals the committed catalogue's msgid set.
A non-empty symmetric difference is drift: the catalogue must be re-synced (run
``python -m dev.docs.i18n``) and the delta translated. It carries the
``integration`` marker because it runs a real Sphinx extraction.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from babel.messages.pofile import read_po

from dev.docs.i18n import TARGET_LANGUAGES, extract_pot, user_scope_source_pages

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCS = _REPO_ROOT / "docs"
_LOCALES = _DOCS / "locales"


def _msgid_set(path: Path) -> set[str] | None:
    """Return the non-header msgid set of a ``.pot``/``.po`` file, or None if absent."""
    if not path.is_file():
        return None
    with path.open("rb") as handle:
        catalogue = read_po(handle)
    return {message.id for message in catalogue if message.id}


@pytest.fixture(scope="module")
def fresh_pot(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Extract the current source POT templates once into a temporary directory.

    The extraction is language-independent (English is the msgid source), so it
    runs once for the whole module and every per-language check reads the same
    templates.
    """
    pot_dir = tmp_path_factory.mktemp("catalogue-drift-pot")
    extract_pot(_REPO_ROOT, out_dir=pot_dir)
    return pot_dir


@pytest.mark.parametrize("language", TARGET_LANGUAGES)
def test_catalogue_msgids_match_current_source(language: str, fresh_pot: Path) -> None:
    """Every page catalogue's msgid set equals the freshly-extracted source msgid set.

    A drift means the source page changed without a catalogue re-sync: source
    strings missing from the catalogue would silently fall back to English, and
    stale catalogue strings translate text the page no longer contains. The
    failure enumerates every drifted page with the count of source msgids absent
    from the catalogue and stale catalogue msgids, so the re-sync scope is read
    straight from the gate output.
    """
    pages = user_scope_source_pages(_DOCS)
    drift: list[str] = []
    for page in pages:
        source_ids = _msgid_set(fresh_pot / Path(page).with_suffix(".pot"))
        if source_ids is None:
            drift.append(f"{page}: no POT template extracted for the page")
            continue
        catalogue_ids = _msgid_set(_LOCALES / language / "LC_MESSAGES" / Path(page).with_suffix(".po"))
        if catalogue_ids is None:
            drift.append(f"{page}: catalogue missing")
            continue
        missing_from_catalogue = source_ids - catalogue_ids
        stale_in_catalogue = catalogue_ids - source_ids
        if missing_from_catalogue or stale_in_catalogue:
            drift.append(
                f"{page}: {len(missing_from_catalogue)} source msgid(s) absent from catalogue, "
                f"{len(stale_in_catalogue)} stale catalogue msgid(s)"
            )
    assert not drift, (
        f"{language}: {len(drift)} of {len(pages)} page(s) have drifted from source "
        f"(re-sync with `python -m dev.docs.i18n`, then translate the delta):\n  " + "\n  ".join(drift)
    )

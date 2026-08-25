"""Documentation localization completeness and language-set parity gates.

Two gates encode the operator's validity contract for the localized user
documentation: a page is valid only when every principal language is actually
present, and the docs language set must equal the runtime
:class:`~cadrumo.core.external_constants.OutputLanguage` set (minus English, the
msgid source) exactly - never a second hand-listed authority.

The completeness gate (:func:`test_every_user_page_is_fully_translated`) was
written to be RED until the Spanish, Catalan, and Hungarian catalogues were
translated, carrying no skip or xfail so it would fail honestly meanwhile. Those
translations have landed: all three catalogues now read 100% translated with zero
untranslated and zero fuzzy entries, and the gate passes. Its job from here is
the reverse of its original one - it holds that completeness rather than
announcing its absence, so a page added without translations, or an entry that
goes fuzzy on a msgid change, reds it again.

The silence it inverts is what makes it load-bearing: gettext falls back to
English for an untranslated segment without complaint, so a reader would simply
be served the wrong language with no signal anywhere. It is one parametrized test
per target language, so an incomplete language reports one failure enumerating
its incomplete pages rather than thousands of per-entry failures.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from babel.messages.pofile import read_po

from cadrumo.core import DirectoryEntryKind, scan_directory
from cadrumo.core.external_constants import OutputLanguage

from ..._paths import REPO_ROOT
from ..i18n import TARGET_LANGUAGES, user_scope_source_pages

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT
_DOCS = _REPO_ROOT / "docs"
_LOCALES = _DOCS / "locales"


def _catalogue_path(language: str, page: str) -> Path:
    """Return the ``.po`` catalogue path for one source page in one language."""
    return _LOCALES / language / "LC_MESSAGES" / Path(page).with_suffix(".po")


def _catalogue_counts(po_path: Path) -> tuple[int, int]:
    """Return the (untranslated, fuzzy) entry counts for one catalogue.

    The header entry (empty msgid) is ignored; every real message is counted as
    untranslated when it carries no translation string and as fuzzy when gettext
    marked it fuzzy after a source edit. Both count as "not present" for the
    all-languages completeness contract.

    Args:
        po_path: The ``.po`` catalogue to read.

    Returns:
        A ``(untranslated, fuzzy)`` count pair.
    """
    with po_path.open("rb") as handle:
        catalogue = read_po(handle)
    untranslated = 0
    fuzzy = 0
    for message in catalogue:
        if not message.id:
            continue
        if not message.string:
            untranslated += 1
        if message.fuzzy:
            fuzzy += 1
    return untranslated, fuzzy


@pytest.mark.parametrize("language", TARGET_LANGUAGES)
def test_every_user_page_is_fully_translated(language: str) -> None:
    """Every user-scope page has a complete catalogue with no untranslated or fuzzy entries.

    A page whose catalogue is missing, or carries any untranslated or fuzzy
    entry, fails the language. The failure enumerates every incomplete page with
    its untranslated and fuzzy counts, so whether it is sizing an initial
    translation pass or naming the one page that regressed, the gate output is
    the worklist.
    """
    pages = user_scope_source_pages(_DOCS)
    assert pages, f"no user-scope source pages found under {_DOCS}; this gate scanned nothing"
    failures: list[str] = []
    for page in pages:
        po_path = _catalogue_path(language, page)
        if not po_path.is_file():
            failures.append(f"{page}: catalogue missing at {po_path.relative_to(_REPO_ROOT).as_posix()}")
            continue
        untranslated, fuzzy = _catalogue_counts(po_path)
        if untranslated or fuzzy:
            failures.append(f"{page}: {untranslated} untranslated, {fuzzy} fuzzy")
    assert not failures, (
        f"{language}: {len(failures)} of {len(pages)} page catalogue(s) incomplete "
        f"(untranslated or fuzzy entries fall back to English silently):\n  " + "\n  ".join(failures)
    )


@pytest.mark.parametrize("language", TARGET_LANGUAGES)
def test_translations_introduce_no_machine_text_dashes(language: str) -> None:
    """No msgstr carries more em/en dashes than its msgid (operator house style).

    The English source is em-dash-ratcheted; a translation that introduces
    em or en dashes absent from its source segment is the canonical
    machine-generated-text marker the operator has barred from this corpus.
    Legitimate dashes present in the source stay representable, because the
    bound is the source's own count per entry, never zero.
    """
    dashes = ("—", "–")
    pages = user_scope_source_pages(_DOCS)
    assert pages, f"no user-scope source pages found under {_DOCS}; this gate scanned nothing"
    failures: list[str] = []
    for page in pages:
        po_path = _catalogue_path(language, page)
        if not po_path.is_file():
            continue
        with po_path.open("rb") as handle:
            catalogue = read_po(handle)
        for message in catalogue:
            if not message.id or not message.string:
                continue
            source = sum(str(message.id).count(dash) for dash in dashes)
            translated = sum(str(message.string).count(dash) for dash in dashes)
            if translated > source:
                excerpt = str(message.string)[:80].replace("\n", " ")
                failures.append(f"{page}: +{translated - source} ({excerpt}...)")
    assert not failures, (
        f"{language}: {len(failures)} msgstr(s) introduce em/en dashes absent from their msgid "
        f"(machine-text marker; rephrase with commas, parentheses, or colons):\n  " + "\n  ".join(failures)
    )


def _conf_language_config() -> dict[str, object]:
    """Evaluate ``docs/conf.py`` and return its language-switch configuration.

    Runs the ``docs/conf.py`` module-level code (never ``setup()``) in a
    subprocess so the accepted-language set and the default language are read from
    the real configuration, not re-derived here.

    Returns:
        A mapping with the default ``language`` and the accepted
        ``valid_languages`` set the config validates against.
    """
    conf = _DOCS / "conf.py"
    script = (
        "import json, runpy;"
        f"ns = runpy.run_path(r'{conf}');"
        "print('LANG_CONFIG=' + json.dumps({"
        "'language': ns['language'],"
        "'valid_languages': sorted(ns['_VALID_DOCS_LANGUAGES'])}))"
    )
    with tempfile.TemporaryDirectory(prefix="cadrumo-locale-parity-") as storage_root:
        env = {
            **os.environ,
            "CADRUMO_DOCS_PROJECT_ROOT": str(_REPO_ROOT),
            "CADRUMO_LOCAL_STORAGE_ROOT": storage_root,
        }
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    assert result.returncode == 0, result.stdout + result.stderr
    line = next(row for row in result.stdout.splitlines() if row.startswith("LANG_CONFIG="))
    return json.loads(line[len("LANG_CONFIG=") :])


def test_docs_target_languages_equal_output_language_minus_english() -> None:
    """The docs language set equals OutputLanguage members minus English, everywhere.

    Three surfaces must agree with the single language authority: the extraction
    target set, the committed catalogue trees on disk, and the accepted language
    set ``docs/conf.py`` validates against. English is the msgid source and has no
    catalogue; the three translation targets are exactly the remaining
    OutputLanguage members.
    """
    all_languages = {member.value for member in OutputLanguage}
    expected_targets = all_languages - {OutputLanguage.EN.value}

    assert set(TARGET_LANGUAGES) == expected_targets, (
        f"TARGET_LANGUAGES {sorted(TARGET_LANGUAGES)} must equal OutputLanguage minus English "
        f"{sorted(expected_targets)}"
    )

    committed_trees = {
        child.name for child in scan_directory(_LOCALES, select=DirectoryEntryKind.DIRECTORIES) if child.name != "pot"
    }
    assert committed_trees == expected_targets, (
        f"committed catalogue trees {sorted(committed_trees)} must equal the target languages "
        f"{sorted(expected_targets)}"
    )

    config = _conf_language_config()
    assert set(config["valid_languages"]) == all_languages, (
        f"conf.py accepts {config['valid_languages']}, which must equal the full OutputLanguage set "
        f"{sorted(all_languages)} (English is a valid build language, it is only excluded as a translation target)"
    )
    assert config["language"] == "en", "the default documentation build language must stay English"


@pytest.mark.parametrize("language", TARGET_LANGUAGES)
def test_no_orphan_catalogues(language: str) -> None:
    """No committed catalogue outlives its source page.

    The completeness and drift gates both iterate the current source page set, so
    a catalogue whose source page was later deleted or renamed would linger
    uncaught - translated (or half-translated) text for a page that no longer
    ships. This asserts every committed ``.po`` maps to a current user-scope
    source page, enumerating any orphan whose source is gone.
    """
    expected = {Path(page).with_suffix(".po").as_posix() for page in user_scope_source_pages(_DOCS)}
    assert expected, (
        f"no user-scope source pages found under {_DOCS}; every committed catalogue would read as "
        "an orphan, so an empty page set cannot be treated as a clean result"
    )
    lc_messages = _LOCALES / language / "LC_MESSAGES"
    present = {
        po.relative_to(lc_messages).as_posix() for po in scan_directory(lc_messages, pattern="*.po", recursive=True)
    }
    orphans = sorted(present - expected)
    assert not orphans, (
        f"{language}: {len(orphans)} orphan catalogue(s) whose source page no longer exists "
        f"(remove the catalogue or restore the source page):\n  " + "\n  ".join(orphans)
    )

"""Every label of the installation and reference areas is worded in each shipped language.

``tr`` does not raise on a missing key: it shows the last dotted segment as if
it were a word. A label nobody translated therefore renders something
English-looking in every language and nothing fails. This module reads the
keys the two areas actually call, and the acts, request members and reads they
label, and requires real wording for each in all four catalogues.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from cadrumo_client.contracts.installation_requests import INSTALLATION_ACT_CONTRACTS, InstallationAct

from ....core.config import override_settings
from ....core.directory_scan import scan_directory
from ..installation.acts import InstallationFamily, offered_acts
from ..installation.texts import act_label, act_summary, family_label, field_label
from ..reference.filters import filters_of
from ..reference.reads import ReferenceRead
from ..reference.texts import filter_label, read_label, read_summary

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LOCALES = ("en", "es", "ca", "hu")
_NAMESPACES = ("tui.installation.", "tui.reference.")
_TUI_PACKAGE = Path(__file__).resolve().parents[1]
_LOCALES_ROOT = Path(__file__).resolve().parents[3] / "locales"


def _called_keys() -> frozenset[str]:
    """Every literal key of the two namespaces a terminal-interface module passes to ``tr``."""
    keys: set[str] = set()
    for path in scan_directory(_TUI_PACKAGE, pattern="*.py", recursive=True):
        if "tests" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "tr"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and node.args[0].value.startswith(_NAMESPACES)
            ):
                keys.add(node.args[0].value)
    return frozenset(keys)


def _catalogue(locale: str) -> dict[str, object]:
    loaded = yaml.safe_load((_LOCALES_ROOT / locale / "common.yml").read_text(encoding="utf-8"))
    return {str(key): value for key, value in loaded.items()}


def _wording(catalogue: dict[str, object], dotted: str) -> str | None:
    node: object = catalogue
    for segment in dotted.split("."):
        if not isinstance(node, dict) or segment not in node:
            return None
        node = node[segment]
    return node if isinstance(node, str) else None


def test_the_scan_reads_the_real_areas() -> None:
    """A scan that parsed nothing would make every coverage test below pass."""
    keys = _called_keys()

    assert len(keys) >= 140
    assert "tui.installation.title" in keys and "tui.reference.title" in keys
    assert {key for key in keys if key.startswith("tui.installation.act.")} >= {
        f"tui.installation.act.{act.value}.label" for act in InstallationAct
    }


@pytest.mark.parametrize("locale", _LOCALES)
def test_every_called_key_is_worded_in_this_locale(locale: str) -> None:
    catalogue = _catalogue(locale)

    unworded = sorted(key for key in _called_keys() if not (_wording(catalogue, key) or "").strip())

    assert not unworded, f"{locale} has no wording for: {unworded}"


@pytest.mark.parametrize("locale", _LOCALES)
def test_no_catalogue_keeps_a_label_these_areas_no_longer_call(locale: str) -> None:
    catalogue = _catalogue(locale)
    called = _called_keys()

    def leaves(node: object, prefix: str) -> list[str]:
        if not isinstance(node, dict):
            return [prefix]
        return [leaf for key, value in node.items() for leaf in leaves(value, f"{prefix}.{key}")]

    tui = catalogue["tui"]
    assert isinstance(tui, dict)
    kept = leaves(tui["installation"], "tui.installation") + leaves(tui["reference"], "tui.reference")

    assert sorted(set(kept) - called) == []


@pytest.mark.parametrize("locale", _LOCALES)
def test_every_act_family_member_and_read_on_screen_has_its_own_words(locale: str) -> None:
    """An act with no wording is still offered, under its token; none of today's may be left that way."""
    with override_settings(cadrumo_output_language=locale):
        for act in INSTALLATION_ACT_CONTRACTS:
            assert act_label(act) != act.value, act
            assert act_summary(act).strip(), act
        for family in InstallationFamily:
            assert family_label(family).strip() and family_label(family) != family.value
        for offered in offered_acts():
            for field in offered.fields:
                assert field_label(field.name) != field.name, (offered.act, field.name)
        for read in ReferenceRead:
            assert read_label(read).strip() and read_summary(read).strip()
            for reference_filter in filters_of(read):
                assert filter_label(reference_filter.name) != reference_filter.name, (read, reference_filter.name)


def test_the_four_languages_do_not_share_one_wording() -> None:
    """A catalogue filled by copying another's text would pass every coverage test above."""
    catalogues = {locale: _catalogue(locale) for locale in _LOCALES}
    sentences = [
        key for key in _called_keys() if ".summary." in key or key.endswith((".summary", ".intro", ".question"))
    ]
    assert len(sentences) >= 30

    for key in sentences:
        wordings = {locale: _wording(catalogues[locale], key) for locale in _LOCALES}
        assert len(set(wordings.values())) == len(_LOCALES), (key, wordings)
